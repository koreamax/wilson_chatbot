"""proto/wilson/{dialogue,rag,llm}/v1 → wilson_orchestrator.generated 스텁 생성.

오케스트레이터는 DialogueService(서버) + RagService·LlmService(클라이언트) 스텁이 모두
필요하다. rag/llm-server와 동일 규칙: 생성물을 flat으로 두고 grpc 스텁의 형제 import를
상대 import로 패치한다. 생성물은 체크인한다.
사용:  python services/orchestrator-server/scripts/gen_proto.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# scripts/ -> orchestrator-server -> services -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = (
    REPO_ROOT
    / "services"
    / "orchestrator-server"
    / "src"
    / "wilson_orchestrator"
    / "generated"
)

# (proto 파일 경로, pb2 모듈 stem)
PROTOS = [
    (REPO_ROOT / "proto" / "wilson" / "dialogue" / "v1" / "dialogue.proto", "dialogue"),
    (REPO_ROOT / "proto" / "wilson" / "rag" / "v1" / "rag.proto", "rag"),
    (REPO_ROOT / "proto" / "wilson" / "llm" / "v1" / "llm.proto", "llm"),
]


def _patch_grpc_imports(grpc_file: Path, stem: str) -> None:
    text = grpc_file.read_text(encoding="utf-8")
    needle = f"\nimport {stem}_pb2 as {stem}__pb2\n"
    replacement = f"\nfrom . import {stem}_pb2 as {stem}__pb2\n"
    patched = text.replace(needle, replacement)
    if patched == text:
        raise RuntimeError(
            f"{stem}_pb2_grpc.py에서 예상한 'import {stem}_pb2' 라인을 찾지 못했습니다. "
            "grpcio-tools 출력 형식을 확인하십시오."
        )
    grpc_file.write_text(patched, encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "__init__.py").write_text(
        '"""proto/wilson/*에서 생성된 gRPC 스텁 (gen_proto.py로 재생성). 손대지 않는다."""\n',
        encoding="utf-8",
    )

    for proto_file, stem in PROTOS:
        if not proto_file.exists():
            raise SystemExit(f"proto 파일을 찾을 수 없습니다: {proto_file}")
        cmd = [
            sys.executable,
            "-m",
            "grpc_tools.protoc",
            f"-I{proto_file.parent}",
            f"--python_out={OUT_DIR}",
            f"--grpc_python_out={OUT_DIR}",
            str(proto_file),
        ]
        subprocess.run(cmd, check=True)
        _patch_grpc_imports(OUT_DIR / f"{stem}_pb2_grpc.py", stem)

    print(f"생성 완료: {OUT_DIR}")


if __name__ == "__main__":
    main()
