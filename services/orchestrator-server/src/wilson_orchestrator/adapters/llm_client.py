"""LLM 유닛(②) gRPC 클라이언트 — LlmService.Generate 토큰 스트림 수신.

내부 채널(③→②). 서버는 실패 시 gRPC status(INTERNAL)로 abort하므로, 스트림 도중
grpc.aio.AioRpcError가 올라온다 — 파이프라인이 이를 ErrorFrame(ERROR_STAGE_LLM)으로 변환한다.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import grpc

from wilson_orchestrator.generated import llm_pb2, llm_pb2_grpc


class LlmClient:
    def __init__(self, target: str) -> None:
        self._channel = grpc.aio.insecure_channel(target)
        self._stub = llm_pb2_grpc.LlmServiceStub(self._channel)

    async def stream_tokens(
        self,
        *,
        trace_id: str,
        turn_id: str,
        system_prompt: str,
        user_text: str,
        context_chunks: list[str],
        language_code: str,
    ) -> AsyncIterator[str]:
        stream = self._stub.Generate(
            llm_pb2.GenerateRequest(
                trace_id=trace_id,
                turn_id=turn_id,
                system_prompt=system_prompt,
                user_text=user_text,
                context_chunks=context_chunks,
                language_code=language_code,
            )
        )
        async for chunk in stream:
            if chunk.done:
                break
            if chunk.text:
                yield chunk.text

    async def close(self) -> None:
        await self._channel.close()
