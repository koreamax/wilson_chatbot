from concurrent import futures
import logging

import grpc

from wilson_rag.config.settings import get_settings
from wilson_rag.infrastructure.chroma_client import create_chroma_client, wait_for_chroma
from wilson_rag.repository import ChromaRepository


def serve() -> None:
    """Start the RAG gRPC server.

    아직 RagService servicer 구현 전이지만, 실제 배포 시 ChromaDB 연결과
    필수 컬렉션 생성은 여기서 수행한다.
    """
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()

    chroma_client = create_chroma_client(settings)
    wait_for_chroma(chroma_client, settings.chroma_connect_timeout_seconds)
    repository = ChromaRepository(chroma_client)
    repository.ensure_required_collections()
    logging.info("ChromaDB connected. Collections: %s", repository.collection_names())

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    server.add_insecure_port(f"{settings.grpc_host}:{settings.grpc_port}")
    server.start()
    logging.info("RAG gRPC server listening on %s:%s", settings.grpc_host, settings.grpc_port)
    server.wait_for_termination()
