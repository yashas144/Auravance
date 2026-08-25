from fastapi import APIRouter, Depends, Query

from app.models.schemas import AuthenticatedUserResponse, DiagnosticRequest, DiagnosticResponse, KnowledgeSearchResultResponse, RagStatusResponse
from app.services.auth import auth_service
from app.services.knowledge import knowledge_service
from app.services.rag import rag_service

router = APIRouter()


@router.get("/status", response_model=RagStatusResponse)
def get_rag_status(_: AuthenticatedUserResponse = Depends(auth_service.get_current_user)) -> RagStatusResponse:
    return rag_service.status()


@router.post("/root-cause", response_model=DiagnosticResponse)
def run_root_cause_analysis(
    payload: DiagnosticRequest,
    _: AuthenticatedUserResponse = Depends(auth_service.get_current_user),
) -> DiagnosticResponse:
    return rag_service.root_cause(payload)


@router.get("/retrieve", response_model=list[KnowledgeSearchResultResponse])
def retrieve_diagnostic_evidence(
    q: str = Query(..., min_length=2),
    limit: int = Query(5, ge=1, le=10),
    _: AuthenticatedUserResponse = Depends(auth_service.get_current_user),
) -> list[KnowledgeSearchResultResponse]:
    return knowledge_service.search(q, limit=limit)
