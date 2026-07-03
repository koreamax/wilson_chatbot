import sys

from wilson_rag.config.settings import get_settings
from wilson_rag.infrastructure.chroma_client import create_chroma_client
from wilson_rag.repository import ChromaRepository


def main() -> None:
    settings = get_settings()
    client = create_chroma_client(settings)
    client.heartbeat()

    repository = ChromaRepository(client)
    if not repository.has_required_collections():
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(1)
