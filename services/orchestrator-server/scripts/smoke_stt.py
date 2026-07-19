"""라이브 STT 스모크 — .env의 AZURE_SPEECH_KEY로 Azure Speech에 실제 호출.

WAV(PCM) 또는 OGG-OPUS 파일 하나를 전사해 결과를 출력한다.
사용: PYTHONPATH=services/orchestrator-server/src \
      python services/orchestrator-server/scripts/smoke_stt.py <path-to-audio>
"""

import asyncio
import sys
from pathlib import Path

from wilson_orchestrator.adapters.stt_client import SttClient
from wilson_orchestrator.settings import get_settings


async def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("사용: smoke_stt.py <오디오 파일 경로(WAV/OGG)>")
    settings = get_settings()
    if not settings.azure_speech_key:
        raise SystemExit("AZURE_SPEECH_KEY 미설정 — .env에 키를 넣어주세요.")

    audio = Path(sys.argv[1]).read_bytes()
    client = SttClient(
        settings.azure_speech_key, settings.azure_speech_region, settings.language_code
    )
    print(f"region={settings.azure_speech_region} lang={settings.language_code} bytes={len(audio)}")
    try:
        text = await client.transcribe(audio, "wav")
    finally:
        await client.close()
    print("전사:", text)
    print("OK" if text else "EMPTY")


if __name__ == "__main__":
    asyncio.run(main())
