from fastapi import APIRouter, Depends, Query

from app.models.schemas import AuthenticatedUserResponse, KnowledgeDocumentResponse, KnowledgeSearchResultResponse
from app.services.auth import auth_service
from app.services.knowledge import knowledge_service

router = APIRouter()


@router.get("/documents", response_model=list[KnowledgeDocumentResponse])
def list_documents(_: AuthenticatedUserResponse = Depends(auth_service.get_current_user)) -> list[KnowledgeDocumentResponse]:
    return knowledge_service.list_documents()


@router.get("/search", response_model=list[KnowledgeSearchResultResponse])
def search_knowledge(
    q: str = Query(..., min_length=2),
    limit: int = Query(5, ge=1, le=10),
    _: AuthenticatedUserResponse = Depends(auth_service.get_current_user),
) -> list[KnowledgeSearchResultResponse]:
    return knowledge_service.search(q, limit=limit)
