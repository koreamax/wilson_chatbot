# Orchestrator 서버

역할:

- Spring Boot 백엔드가 호출하는 유일한 외부 gRPC 진입점
- `DialogueService.Converse` 수신
- STT → RAG → LLM → TTS 순서 조율
- STT 완료 후 치매/음성/감정 분석을 비동기로 트리거하고 MQ로 publish

이 서버는 수신용 REST router를 만들지 않는다.
