import logging

from wilson_rag.config.settings import get_settings
from wilson_rag.infrastructure.chroma_client import create_chroma_client, wait_for_chroma
from wilson_rag.repository import ChromaRepository


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    client = create_chroma_client(settings)
    wait_for_chroma(client, settings.chroma_connect_timeout_seconds)

    repository = ChromaRepository(client)
    repository.ensure_required_collections()
    logging.info("Required Chroma collections are ready: %s", repository.collection_names())


if __name__ == "__main__":
    main()
