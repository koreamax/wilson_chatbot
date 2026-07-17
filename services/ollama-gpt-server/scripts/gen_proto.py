"""proto/wilson/llm/v1/llm.proto → wilson_llm.generated 스텁 생성.

rag-server와 동일 규칙: 생성물을 flat으로 두고 grpc 스텁의 형제 import를 상대 import로 패치.
사용:  python services/ollama-gpt-server/scripts/gen_proto.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# scripts/ -> ollama-gpt-server -> services -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
PROTO_DIR = REPO_ROOT / "proto" / "wilson" / "llm" / "v1"
PROTO_FILE = PROTO_DIR / "llm.proto"
OUT_DIR = REPO_ROOT / "services" / "ollama-gpt-server" / "src" / "wilson_llm" / "generated"


def _patch_grpc_imports(grpc_file: Path) -> None:
    text = grpc_file.read_text(encoding="utf-8")
    patched = text.replace(
        "\nimport llm_pb2 as llm__pb2\n",
        "\nfrom . import llm_pb2 as llm__pb2\n",
    )
    if patched == text:
        raise RuntimeError(
            "llm_pb2_grpc.py에서 예상한 'import llm_pb2' 라인을 찾지 못했습니다. "
            "grpcio-tools 출력 형식을 확인하십시오."
        )
    grpc_file.write_text(patched, encoding="utf-8")


def main() -> None:
    if not PROTO_FILE.exists():
        raise SystemExit(f"proto 파일을 찾을 수 없습니다: {PROTO_FILE}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "__init__.py").write_text(
        '"""proto/wilson/llm/v1에서 생성된 gRPC 스텁 (gen_proto.py로 재생성). 손대지 않는다."""\n',
        encoding="utf-8",
    )

    cmd = [
        sys.executable,
        "-m",
        "grpc_tools.protoc",
        f"-I{PROTO_DIR}",
        f"--python_out={OUT_DIR}",
        f"--grpc_python_out={OUT_DIR}",
        str(PROTO_FILE),
    ]
    subprocess.run(cmd, check=True)
    _patch_grpc_imports(OUT_DIR / "llm_pb2_grpc.py")
    print(f"생성 완료: {OUT_DIR}")


if __name__ == "__main__":
    main()
