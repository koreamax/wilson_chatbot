class MetricsPublisher:
    async def publish_analysis_result(self, turn_id: str, payload: dict) -> None:
        raise NotImplementedError("인지 지표 MQ publish 연결 필요")
