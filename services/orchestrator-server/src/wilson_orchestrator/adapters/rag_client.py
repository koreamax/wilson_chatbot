"""RAG 유닛(①) gRPC 클라이언트 — RagService.BuildContext 호출.

내부 채널(③→①). 검색 실패는 rag.md 폴백 원칙상 대화를 끊지 않는다 — 이 클라이언트는
실패를 예외로 전파하고, 파이프라인이 빈 컨텍스트 폴백으로 대화를 유지한다.
"""

from __future__ import annotations

from dataclasses import dataclass

import grpc

from wilson_orchestrator.generated import rag_pb2, rag_pb2_grpc

# 노인 대화 기본 검색 대상: 공용 지식 + 그 노인 개인 이력.
# guardian은 보호자 경로이자 ERD 미확정이라 이 스파인에서 검색하지 않는다(rag.md 권한 경계).
_DEFAULT_COLLECTIONS = (rag_pb2.STATIC_KNOWLEDGE, rag_pb2.ELDER)


@dataclass(frozen=True)
class RagContext:
    chunk_texts: list[str]
    fallback_used: bool


class RagClient:
    def __init__(self, target: str) -> None:
        self._channel = grpc.aio.insecure_channel(target)
        self._stub = rag_pb2_grpc.RagServiceStub(self._channel)

    async def build_context(
        self,
        *,
        trace_id: str,
        turn_id: str,
        target_user_id: str,
        session_id: str,
        query_text: str,
    ) -> RagContext:
        response = await self._stub.BuildContext(
            rag_pb2.BuildContextRequest(
                trace_id=trace_id,
                turn_id=turn_id,
                target_user_id=target_user_id,
                session_id=session_id,
                query_text=query_text,
                collections=list(_DEFAULT_COLLECTIONS),
            )
        )
        return RagContext(
            chunk_texts=[chunk.text for chunk in response.chunks],
            fallback_used=response.fallback_used,
        )

    async def close(self) -> None:
        await self._channel.close()
