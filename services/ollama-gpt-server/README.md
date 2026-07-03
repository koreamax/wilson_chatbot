# Ollama GPT 서버

역할:

- RAG 컨텍스트와 사용자 발화를 받아 Ollama 모델에 전달
- 토큰 스트림을 내부 gRPC 스트림으로 오케스트레이터에 전달
- OpenAI 폴백은 MVP 이후로 미룬다
