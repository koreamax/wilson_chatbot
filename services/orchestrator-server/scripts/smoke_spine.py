"""배선 스모크 — 외부 의존성(RAG/LLM/Chroma/NVIDIA) 없이 ③ 텍스트 스파인 왕복 검증.

가짜 RAG/LLM 클라이언트를 주입해 DialogueServicer→pipeline→프레임 조립을 실제 aio 서버로
띄우고, 텍스트를 오디오 바이트 자리에 실어 Converse를 호출한다. Metadata→Completion 프레임이
순서대로 오는지 확인한다(키·네트워크 불필요).

사용: PYTHONPATH=services/orchestrator-server/src \
      python services/orchestrator-server/scripts/smoke_spine.py
"""

import asyncio

import grpc

from wilson_orchestrator.adapters.rag_client import RagContext
from wilson_orchestrator.generated import dialogue_pb2, dialogue_pb2_grpc
from wilson_orchestrator.grpc_server import DialogueServicer
from wilson_orchestrator.pipeline import DialoguePipeline
from wilson_orchestrator.settings import Settings

_EXPECTED_ANSWER = "네, 어르신. 천천히 말씀해 주세요."


class _FakeStt:
    # STT를 대체 — 오디오 바이트를 텍스트로 그대로 돌려 배선만 검증(실제 Azure 호출 없음).
    async def transcribe(self, audio_payload: bytes, audio_format: str) -> str:
        return audio_payload.decode("utf-8")


class _FakeRag:
    async def build_context(self, **_kwargs) -> RagContext:
        return RagContext(chunk_texts=["복약 안내: 아침 8시, 저녁 7시"], fallback_used=False)


class _FakeLlm:
    async def stream_tokens(self, **_kwargs):
        for piece in ["네, ", "어르신. ", "천천히 ", "말씀해 주세요."]:
            yield piece


class _FakeTts:
    # TTS 대체 — 문장 텍스트를 그대로 바이트로 돌려 AudioChunk 배선만 검증(실제 Azure 호출 없음).
    async def synthesize(self, text: str) -> bytes:
        return text.encode("utf-8")


async def main() -> None:
    pipeline = DialoguePipeline(_FakeStt(), _FakeRag(), _FakeLlm(), _FakeTts(), Settings())

    server = grpc.aio.server()
    dialogue_pb2_grpc.add_DialogueServiceServicer_to_server(DialogueServicer(pipeline), server)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()

    async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
        stub = dialogue_pb2_grpc.DialogueServiceStub(channel)
        request = dialogue_pb2.AudioRequest(
            audio_payload="약 언제 먹어요?".encode("utf-8"),
            trace_id="t-1",
            target_user_id="user_1",
            session_id="s-1",
            turn_id="turn-1",
            audio_format="text",  # 스모크 브리지: _FakeStt이 오디오 자리 텍스트를 그대로 전사
            language_code="ko-KR",
        )
        frames = [frame async for frame in stub.Converse(request)]

    await server.stop(None)

    kinds = [frame.WhichOneof("payload") for frame in frames]
    audio_frames = [f for f in frames if f.WhichOneof("payload") == "audio_chunk"]
    print("frames :", kinds)
    print("stt    :", frames[0].metadata.stt_text)
    print("chunks :", [f.audio_chunk.sequence for f in audio_frames])
    print("answer :", frames[-1].completion.full_llm_response_text)

    assert kinds[0] == "metadata", kinds
    assert kinds[-1] == "completion", kinds
    assert len(audio_frames) >= 1, "AudioChunk 프레임이 없습니다"
    # 순번은 1..N으로 증가해야 한다.
    assert [f.audio_chunk.sequence for f in audio_frames] == list(range(1, len(audio_frames) + 1))
    assert frames[0].metadata.stt_text == "약 언제 먹어요?"
    assert frames[-1].completion.full_llm_response_text == _EXPECTED_ANSWER
    print("OK")


if __name__ == "__main__":
    asyncio.run(main())
