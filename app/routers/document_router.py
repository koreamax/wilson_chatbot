from fastapi import APIRouter
from app.services.rag_service import RagService

router = APIRouter(
    prefix="/documents",
    tags=["documents"]
)

rag_service = RagService()


@router.post("/upload")
def upload_document():
    return rag_service.upload_document()
