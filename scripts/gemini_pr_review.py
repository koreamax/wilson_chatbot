import json
import os
import pathlib
import urllib.error
import urllib.parse
import urllib.request


def require_first_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value

    joined_names = ", ".join(names)
    raise RuntimeError(
        f"{joined_names} 중 사용 가능한 값이 없습니다. "
        "GitHub 저장소의 Settings > Secrets and variables > Actions에 "
        "GEMINI_API_KEY 또는 GOOGLE_API_KEY secret을 등록했는지 확인하세요. "
        "fork PR이면 pull_request 이벤트에서는 repository secret을 받을 수 없습니다."
    )


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} 환경변수가 비어 있습니다.")
    return value


GEMINI_API_KEY = require_first_env("GEMINI_API_KEY", "GOOGLE_API_KEY")
GITHUB_TOKEN = require_env("GITHUB_TOKEN")
GITHUB_REPOSITORY = require_env("GITHUB_REPOSITORY")
PR_NUMBER = require_env("PR_NUMBER")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
PR_DIFF_PATH = os.getenv("PR_DIFF_PATH", "pr.diff")
MAX_DIFF_CHARS = int(os.getenv("MAX_DIFF_CHARS", "30000"))


def format_http_error(error: urllib.error.HTTPError, body: str) -> RuntimeError:
    detail = body
    try:
        parsed = json.loads(body)
        detail = json.dumps(parsed, ensure_ascii=False, indent=2)
        message = parsed.get("error", {}).get("message", "")
    except json.JSONDecodeError:
        message = body

    hint = ""
    if error.code == 403 and "unregistered callers" in message:
        hint = (
            "\n\n해결 방법:\n"
            "1. GitHub Actions secret이 실제 실행 저장소에 등록됐는지 확인하세요.\n"
            "   - PR 체크가 koreamax/wilson_chatbot에서 돌면, 그 저장소 secret에 넣어야 합니다.\n"
            "   - fork 저장소 secret에만 넣으면 upstream PR 체크에서는 읽을 수 없습니다.\n"
            "2. Google AI Studio에서 새 Auth API key를 생성해서 GEMINI_API_KEY로 다시 등록하세요.\n"
            "   - 2026-06-19 이후 Gemini API는 제한 없는 Standard API key 요청을 거부할 수 있습니다.\n"
            "   - 기존 Standard key를 계속 쓰려면 Gemini API 전용으로 제한하거나 Auth key로 교체해야 합니다.\n"
            "3. secret 이름은 GEMINI_API_KEY 또는 GOOGLE_API_KEY여야 합니다.\n"
        )
    elif error.code == 403:
        hint = (
            "\n\n확인할 것:\n"
            "- Gemini API key가 유효한지 확인하세요.\n"
            "- 해당 key가 Generative Language API/Gemini API 사용 권한을 가지고 있는지 확인하세요.\n"
            "- API key에 IP 또는 referrer 제한을 걸었다면 GitHub Actions runner에서 차단될 수 있습니다.\n"
        )

    return RuntimeError(f"HTTP {error.code}: {detail}{hint}")


def post_json(url: str, payload: dict, headers: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        url=url,
        data=data,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            body = response.read().decode("utf-8")
            if not body:
                return {}
            return json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise format_http_error(e, body) from e


def call_gemini(prompt: str) -> str:
    # Google generateContent REST 예시는 API key를 query parameter로 전달한다.
    # https://ai.google.dev/api/generate-content
    encoded_key = urllib.parse.quote(GEMINI_API_KEY, safe="")
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/"
        f"models/{GEMINI_MODEL}:generateContent?key={encoded_key}"
    )

    headers = {
        "Content-Type": "application/json",
    }

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": prompt,
                    }
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 4096,
        },
    }

    response = post_json(url, payload, headers)

    candidates = response.get("candidates", [])
    if not candidates:
        return (
            "## 🤖 Gemini PR Code Review\n\n"
            "Gemini 응답에 candidates가 없습니다.\n\n"
            f"```json\n{json.dumps(response, ensure_ascii=False, indent=2)}\n```"
        )

    parts = candidates[0].get("content", {}).get("parts", [])

    texts = []
    for part in parts:
        if "text" in part:
            texts.append(part["text"])

    result = "\n".join(texts).strip()

    if not result:
        return (
            "## 🤖 Gemini PR Code Review\n\n"
            "Gemini 응답은 왔지만 텍스트 결과가 비어 있습니다."
        )

    return result


def post_pr_comment(body: str) -> None:
    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/issues/{PR_NUMBER}/comments"

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Content-Type": "application/json",
    }

    post_json(url, {"body": body}, headers)


def main() -> None:
    diff_path = pathlib.Path(PR_DIFF_PATH)

    if not diff_path.exists():
        post_pr_comment(
            "## 🤖 Gemini PR Code Review\n\n"
            "`pr.diff` 파일을 찾지 못해서 리뷰를 실행하지 못했습니다."
        )
        return

    diff = diff_path.read_text(encoding="utf-8", errors="replace")

    if not diff.strip():
        post_pr_comment(
            "## 🤖 Gemini PR Code Review\n\n"
            "변경된 코드 diff가 없어서 리뷰할 내용이 없습니다."
        )
        return

    truncated = False
    if len(diff) > MAX_DIFF_CHARS:
        diff = diff[:MAX_DIFF_CHARS]
        truncated = True

    prompt = f"""
너는 FastAPI/Python 프로젝트를 리뷰하는 시니어 백엔드 개발자다.

아래 PR diff를 보고 코드리뷰를 해라.

리뷰 기준:
1. 실제 버그 가능성
2. 보안 문제
3. 예외 처리 부족
4. FastAPI 라우터/서비스/레포지토리 구조 문제
5. DB 연결, 환경변수, secret 노출 위험
6. RAG/ChromaDB 관련 저장 경로 또는 대용량 파일 관리 문제
7. 가독성/유지보수성
8. 테스트 필요 여부
9. GitHub에 올라가면 안 되는 파일이 포함됐는지 여부

출력 형식:
## 🤖 Gemini PR Code Review

### 핵심 요약
- ...

### 꼭 확인해야 할 문제
- 파일명:
  - 문제:
  - 이유:
  - 수정 제안:

### 개선하면 좋은 점
- ...

### 테스트 추천
- ...

### 결론
- 승인 가능 / 수정 후 승인 권장 / 위험함 중 하나로 판단

주의:
- 확실하지 않은 내용은 "추정"이라고 적어라.
- 코드에 없는 내용을 지어내지 마라.
- 한국어로 작성해라.
- 단순 스타일 지적보다 실제 문제 가능성이 높은 것 위주로 리뷰해라.

PR diff:
```diff
{diff}
```
"""

    review = call_gemini(prompt)

    if truncated:
        review += "\n\n> ⚠️ diff가 너무 길어서 일부만 분석했습니다."

    post_pr_comment(review)


if __name__ == "__main__":
    main()
