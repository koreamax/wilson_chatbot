import logging

import grpc

from wilson_llm.generated import llm_pb2, llm_pb2_grpc
from wilson_llm.provider import NvidiaNimProvider
from wilson_llm.settings import get_settings

logger = logging.getLogger(__name__)


class LlmServicer(llm_pb2_grpc.LlmServiceServicer):
    """LlmService.Generate 구현 — 프로바이더 토큰 스트림을 TokenChunk로 흘린다.

    보안(security.md): 로그에는 추적 식별자만, 발화 원문(user_text)·system_prompt는 남기지 않는다.
    """

    def __init__(self, provider: NvidiaNimProvider) -> None:
        self._provider = provider

    async def Generate(self, request: llm_pb2.GenerateRequest, context: grpc.aio.ServicerContext):
        logger.info(
            "Generate 수신 trace_id=%s turn_id=%s context_chunks=%d",
            request.trace_id,
            request.turn_id,
            len(request.context_chunks),
        )
        try:
            async for token in self._provider.stream_tokens(
                request.system_prompt,
                request.user_text,
                list(request.context_chunks),
                request.language_code,
            ):
                yield llm_pb2.TokenChunk(text=token, done=False)
            yield llm_pb2.TokenChunk(text="", done=True)
        except Exception:
            # 내부 채널(③↔②)이므로 gRPC status로 실패를 알린다. 오케스트레이터가 이를 받아
            # 외부(BE)엔 ErrorFrame(ERROR_STAGE_LLM)으로 우아하게 변환한다.
            logger.exception(
                "LLM 생성 실패 trace_id=%s turn_id=%s", request.trace_id, request.turn_id
            )
            await context.abort(grpc.StatusCode.INTERNAL, "LLM 생성에 실패했습니다.")


async def serve() -> None:
    """Start the internal LLM gRPC(aio) server."""
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()

    if not settings.nvidia_api_key:
        # 키가 없으면 호출이 401로 실패한다. 조용히 넘기지 말고 크게 경고(실키는 로그에 안 남김).
        logger.error(
            "NVIDIA_API_KEY 미설정 — .env(로컬) 또는 K8s Secret에 키를 주입해야 생성이 동작합니다."
        )

    provider = NvidiaNimProvider(
        api_key=settings.nvidia_api_key,
        base_url=settings.nvidia_base_url,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        top_p=settings.llm_top_p,
        max_tokens=settings.llm_max_tokens,
    )

    server = grpc.aio.server()
    llm_pb2_grpc.add_LlmServiceServicer_to_server(LlmServicer(provider), server)
    server.add_insecure_port(f"{settings.grpc_host}:{settings.grpc_port}")
    await server.start()
    logger.info(
        "LLM gRPC(aio) 서버 시작 %s:%s model=%s", settings.grpc_host, settings.grpc_port, settings.llm_model
    )
    await server.wait_for_termination()
