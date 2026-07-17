import asyncio

from wilson_llm.grpc_server import serve


if __name__ == "__main__":
    asyncio.run(serve())
