import time
from typing import Any

import chromadb

from wilson_rag.config.settings import Settings


def create_chroma_client(settings: Settings):
    return chromadb.HttpClient(
        host=settings.chroma_host,
        port=settings.chroma_port,
        ssl=settings.chroma_ssl,
        tenant=settings.chroma_tenant,
        database=settings.chroma_database,
    )


def wait_for_chroma(client: Any, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            client.heartbeat()
            return
        except Exception as exc:  # chromadb raises different transport errors by version
            last_error = exc
            time.sleep(1)

    raise RuntimeError("ChromaDB에 연결할 수 없습니다.") from last_error
