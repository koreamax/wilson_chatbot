import asyncio
import logging

from wilson_orchestrator.grpc_server import serve


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(serve())
