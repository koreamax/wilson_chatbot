from dataclasses import dataclass


@dataclass(frozen=True)
class DialogueTurn:
    trace_id: str
    target_user_id: str
    session_id: str
    turn_id: str
    audio_payload: bytes
    audio_format: str
    language_code: str


class DialoguePipeline:
    async def converse(self, turn: DialogueTurn):
        """STT → RAG → LLM → TTS pipeline.

        반환은 gRPC StreamResponse 프레임 iterator가 된다.
        """
        raise NotImplementedError("대화 파이프라인 연결 필요")
