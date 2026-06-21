from fastapi import FastAPI
from app.routers import chat_router, document_router

app = FastAPI()

app.include_router(chat_router.router)
app.include_router(document_router.router)


@app.get("/")
def root():
    return {"message": "FastAPI RAG server is running"}
