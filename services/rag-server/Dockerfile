FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY services/rag-server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/rag-server/src ./src
COPY proto ./proto

ENV PYTHONPATH=/app/src
EXPOSE 50052

CMD ["python", "-m", "wilson_rag.main"]
