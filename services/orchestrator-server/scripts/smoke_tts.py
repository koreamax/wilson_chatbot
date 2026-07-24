"""라이브 TTS 스모크 — .env의 AZURE_SPEECH_KEY(STT와 동일)로 Azure TTS에 실제 호출.

한국어 한 문장을 합성해 mp3로 저장한다.
사용: PYTHONPATH=services/orchestrator-server/src \
      python services/orchestrator-server/scripts/smoke_tts.py [출력경로.mp3]
"""

import asyncio
import sys
from pathlib import Path

from wilson_orchestrator.adapters.tts_client import TtsClient
from wilson_orchestrator.settings import get_settings

_TEXT = "안녕하세요, 저는 윌슨이에요. 천천히 말씀해 주세요."


async def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tts_out.mp3")
    settings = get_settings()
    if not settings.azure_speech_key:
        raise SystemExit("AZURE_SPEECH_KEY 미설정 — .env에 키를 넣어주세요.")

    client = TtsClient(
        settings.azure_speech_key,
        settings.azure_speech_region,
        settings.tts_voice,
        settings.tts_output_format,
    )
    print(f"region={settings.azure_speech_region} voice={settings.tts_voice}")
    try:
        audio = await client.synthesize(_TEXT)
    finally:
        await client.close()
    out.write_bytes(audio)
    print(f"저장: {out} ({len(audio)} bytes)")
    print("OK" if audio else "EMPTY")


if __name__ == "__main__":
    asyncio.run(main())
