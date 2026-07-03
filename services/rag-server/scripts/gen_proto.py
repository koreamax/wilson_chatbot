"""proto/wilson/rag/v1/rag.proto → wilson_rag.generated 스텁 생성.

레포에 코드젠 규칙이 없어 rag-server 안에 최소 규칙을 세운다.
- 생성물은 `src/wilson_rag/generated/`에 flat으로 둔다(rag_pb2.py, rag_pb2_grpc.py).
- grpc_tools가 만드는 `import rag_pb2`(절대)는 패키지 밖에선 깨지므로
  `from . import rag_pb2`(상대)로 패치해 wilson_rag 패키지 안에서 임포트되게 한다.
- 생성물은 레포에 체크인한다. 런타임은 grpcio + protobuf만 있으면 되고
  grpcio-tools(빌드 도구)는 requirements-dev.txt로 분리한다.

사용:  python services/rag-server/scripts/gen_proto.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# scripts/ -> rag-server -> services -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
PROTO_DIR = REPO_ROOT / "proto" / "wilson" / "rag" / "v1"
PROTO_FILE = PROTO_DIR / "rag.proto"
OUT_DIR = REPO_ROOT / "services" / "rag-server" / "src" / "wilson_rag" / "generated"


def _patch_grpc_imports(grpc_file: Path) -> None:
    """생성된 grpc 스텁의 형제 임포트를 상대 임포트로 바꾼다."""
    text = grpc_file.read_text(encoding="utf-8")
    patched = text.replace(
        "\nimport rag_pb2 as rag__pb2\n",
        "\nfrom . import rag_pb2 as rag__pb2\n",
    )
    if patched == text:
        raise RuntimeError(
            "rag_pb2_grpc.py에서 예상한 'import rag_pb2' 라인을 찾지 못했습니다. "
            "grpcio-tools 출력 형식이 바뀌었을 수 있으니 패치 규칙을 확인하십시오."
        )
    grpc_file.write_text(patched, encoding="utf-8")


def main() -> None:
    if not PROTO_FILE.exists():
        raise SystemExit(f"proto 파일을 찾을 수 없습니다: {PROTO_FILE}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "__init__.py").write_text(
        '"""proto/wilson/rag/v1에서 생성된 gRPC 스텁 (gen_proto.py로 재생성).\n\n'
        "이 디렉터리의 *_pb2.py / *_pb2_grpc.py는 손으로 수정하지 않는다.\n"
        '"""\n',
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
    _patch_grpc_imports(OUT_DIR / "rag_pb2_grpc.py")
    print(f"생성 완료: {OUT_DIR}")


if __name__ == "__main__":
    main()
