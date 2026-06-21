from fastapi import APIRouter
from app.services.chat_service import ChatService

router = APIRouter(
    prefix="/chat",
    tags=["chat"]
)

chat_service = ChatService()


@router.post("/")
def chat(message: str):
    return chat_service.chat(message)
