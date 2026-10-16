from __future__ import annotations
import re
from contextlib import closing

from fastapi import HTTPException

from app.core.config import settings
from app.core.db import fetch_knowledge_index_stats, get_connection
from app.models.schemas import DiagnosticEvidenceResponse, DiagnosticRequest, DiagnosticResponse, RagStatusResponse
from app.services.knowledge import knowledge_service
from app.services.openai_client import OpenAIRagError, generate_root_cause_analysis, has_openai_api_key
from app.services.prediction import prediction_service


ISSUE_PLAYBOOK = {
    "bearing_pattern": {
        "query_terms": ["bearing wear", "lubrication", "misalignment", "vibration", "temperature"],
        "likely_causes": [
            "Bearing wear pattern driven by rising vibration and heat.",
            "Lubrication degradation or shaft misalignment increasing rolling friction.",
        ],
        "recommended_actions": [
            "Inspect the bearing assembly, grease condition, and shaft alignment.",
            "Schedule corrective maintenance within the next operating shift if vibration continues rising.",
        ],
    },
    "pressure_instability": {
        "query_terms": ["pressure instability", "seal leak", "valve blockage", "pump cavitation", "outlet restriction"],
        "likely_causes": [
            "Pressure instability suggests valve leakage, seal degradation, or partial blockage.",
            "Process load variation may be amplifying the pressure swing beyond normal limits.",
        ],
        "recommended_actions": [
            "Inspect valve position, seals, strainers, and the discharge path for restriction or leakage.",
            "Compare the pressure pattern against the last stable operating run before shutdown planning.",
        ],
    },
    "vibration": {
        "query_terms": ["bearing wear", "vibration", "imbalance", "misalignment", "lubrication", "looseness"],
        "likely_causes": [
            "Rising vibration points to rolling-element bearing wear or a developing race defect.",
            "Imbalance, misalignment, or mechanical looseness may be amplifying the vibration level.",
        ],
        "recommended_actions": [
            "Inspect bearings, lubrication condition, and shaft alignment; check mounting bolts for looseness.",
            "Trend vibration closely and plan a bearing replacement if the level keeps rising.",
        ],
    },
    "pressure": {
        "query_terms": ["air leak", "pressure drop", "compressor duty cycle", "seal leak", "pneumatic panel pressure"],
        "likely_causes": [
            "Falling system pressure with sustained loading suggests an air leak downstream of the compressor.",
            "Worn seals, open drains, or a faulty valve may be letting pressure bleed off.",
        ],
        "recommended_actions": [
            "Survey fittings, hoses, drains, and valves for leaks while the system is pressurised.",
            "Compare compressor loaded time against normal duty cycle to confirm the leak rate.",
        ],
    },
    "current": {
        "query_terms": ["motor overload", "current draw", "mechanical drag", "power quality", "cooling fan"],
        "likely_causes": [
            "Motor overload or mechanical drag is increasing current draw.",
            "Power quality fluctuation or poor cooling may be stressing the drive train.",
        ],
        "recommended_actions": [
            "Check the driven load, coupling resistance, ventilation path, and cooling condition.",
            "Inspect the starter or drive event log before planning any controlled shutdown.",
        ],
    },
    "temperature": {
        "query_terms": ["overtemperature", "thermal stress", "cooling path", "air flow restriction", "duty cycle"],
        "likely_causes": [
            "Thermal stress suggests restricted cooling, airflow blockage, or elevated duty cycle.",
            "The asset may be operating beyond its normal temperature baseline for the current load.",
        ],
        "recommended_actions": [
            "Inspect the cooling path and verify the temperature reading against the recent baseline.",
            "Review the latest trend and operating state to confirm sustained thermal drift.",
        ],
    },
}

CAUSE_KEYWORDS = {
    "cause",
    "caused",
    "failure",
    "fault",
    "wear",
    "leak",
    "misalignment",
    "lubrication",
    "overload",
    "cavitation",
    "restriction",
    "contamination",
    "vibration",
    "pressure",
    "temperature",
}

ACTION_KEYWORDS = {
    "inspect",
    "check",
    "replace",
    "verify",
    "clean",
    "lubricate",
    "tighten",
    "monitor",
    "calibrate",
    "remove",
    "confirm",
    "review",
    "schedule",
}


def _split_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", normalized) if sentence.strip()]


def _normalize_sentence(sentence: str) -> str:
    trimmed = sentence.strip()
    if not trimmed:
        return ""
    return trimmed[0].upper() + trimmed[1:]


def _unique_sentences(sentences: list[str], limit: int) -> list[str]:
    seen = set()
    result = []
    for sentence in sentences:
        key = sentence.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(sentence)
        if len(result) >= limit:
            break
    return result


def _asset_context(asset_id: str) -> dict:
    with closing(get_connection()) as connection:
        equipment = connection.execute(
            """
            SELECT
                e.name,
                e.model,
                e.category,
                e.description,
                e.area,
                e.maintenance_strategy,
                v.name AS vendor_name
            FROM equipment e
            LEFT JOIN vendors v ON v.vendor_id = e.vendor_id
            WHERE e.asset_id = ?
            """,
            (asset_id,),
        ).fetchone()
        if equipment:
            return dict(equipment)

        asset = connection.execute(
            """
            SELECT name, asset_type AS category, plant_id, line_id
            FROM assets
            WHERE asset_id = ?
            """,
            (asset_id,),
        ).fetchone()
        return dict(asset) if asset else {}


def _build_retrieval_query(
    payload: DiagnosticRequest,
    prediction,
    context: dict,
    likely_causes: list[str],
) -> str:
    issue = ISSUE_PLAYBOOK.get(prediction.dominant_signal, ISSUE_PLAYBOOK["temperature"])
    query_parts = [
        payload.asset_id,
        context.get("name", ""),
        context.get("model", ""),
        context.get("category", ""),
        context.get("vendor_name", ""),
        context.get("description", ""),
        context.get("area", ""),
        context.get("maintenance_strategy", ""),
        prediction.dominant_signal,
        payload.symptom_summary,
        " ".join(issue["query_terms"]),
        " ".join(likely_causes),
    ]
    return " ".join(part for part in query_parts if part).strip()


def _extract_grounded_sentences(matches: list[dict]) -> tuple[list[str], list[str]]:
    cause_candidates: list[str] = []
    action_candidates: list[str] = []
    for match in matches:
        for sentence in _split_sentences(match["content"]):
            lowered = sentence.lower()
            if any(keyword in lowered for keyword in CAUSE_KEYWORDS):
                cause_candidates.append(_normalize_sentence(sentence))
            if any(keyword in lowered for keyword in ACTION_KEYWORDS):
                action_candidates.append(_normalize_sentence(sentence))
    return _unique_sentences(cause_candidates, 3), _unique_sentences(action_candidates, 3)


def _build_evidence(matches: list[dict]) -> list[DiagnosticEvidenceResponse]:
    evidence = []
    for match in matches:
        preview = match["content"][:280].strip()
        evidence.append(
            DiagnosticEvidenceResponse(
                title=match["title"],
                vendor=match["vendor"],
                source_path=match["source_path"],
                source_type=match["source_type"],
                chunk_index=match["chunk_index"],
                score=match.get("score", 0.0),
                excerpt=f"{preview}..." if len(match["content"]) > 280 else preview,
            )
        )
    return evidence


def _fallback_response(
    payload: DiagnosticRequest,
    prediction,
    matches: list[dict],
    evidence: list[DiagnosticEvidenceResponse],
    issue: dict,
    retrieval_query: str,
) -> DiagnosticResponse:
    grounded_causes, grounded_actions = _extract_grounded_sentences(matches)

    likely_causes = _unique_sentences(
        grounded_causes + issue["likely_causes"],
        4,
    )
    recommended_actions = _unique_sentences(
        grounded_actions + issue["recommended_actions"],
        4,
    )

    evidence_sources = list(dict.fromkeys(item.source_path for item in evidence))
    if not evidence_sources:
        evidence_sources = ["backend/knowledge/maintenance_playbook.md"]

    if evidence:
        top = evidence[0]
        grounded_summary = (
            f"Retrieved evidence from {top.title} ({top.vendor}) aligns with "
            f"the {prediction.dominant_signal} signal and supports a {prediction.anomaly_label} diagnosis."
        )
    else:
        grounded_summary = (
            f"No indexed manual snippet matched strongly, so the response falls back to the "
            f"{prediction.dominant_signal} diagnostic playbook."
        )

    mode = "local_fallback"
    if not has_openai_api_key():
        mode = "missing_openai_api_key"

    return DiagnosticResponse(
        asset_id=payload.asset_id,
        likely_causes=likely_causes,
        recommended_actions=recommended_actions,
        evidence_sources=evidence_sources,
        grounded_summary=grounded_summary,
        retrieval_query=retrieval_query,
        confidence="medium" if evidence else "low",
        generation_mode=mode,
        generation_model=None,
        evidence_snippets=evidence,
    )


class RagService:
    def status(self) -> RagStatusResponse:
        stats = fetch_knowledge_index_stats()
        return RagStatusResponse(
            openai_api_key_loaded=has_openai_api_key(),
            response_model=settings.rag_response_model,
            embedding_model=settings.rag_embedding_model,
            knowledge_documents=stats["documents"],
            knowledge_chunks=stats["chunks"],
            embedded_chunks=stats["embedded_chunks"],
        )

    def root_cause(self, payload: DiagnosticRequest) -> DiagnosticResponse:
        try:
            prediction = prediction_service.get_latest(payload.asset_id)
        except HTTPException as exc:
            raise exc

        issue = ISSUE_PLAYBOOK.get(prediction.dominant_signal, ISSUE_PLAYBOOK["temperature"])
        context = _asset_context(payload.asset_id)
        retrieval_query = _build_retrieval_query(payload, prediction, context, issue["likely_causes"])
        matches = knowledge_service.retrieve(retrieval_query, limit=settings.rag_retrieval_limit)
        evidence = _build_evidence(matches)
        evidence_sources = list(dict.fromkeys(item.source_path for item in evidence))
        if not evidence_sources:
            evidence_sources = ["backend/knowledge/maintenance_playbook.md"]

        generation_payload = {
            "asset_id": payload.asset_id,
            "symptom_summary": payload.symptom_summary,
            "recent_alert_ids": payload.recent_alert_ids,
            "prediction": {
                "dominant_signal": prediction.dominant_signal,
                "anomaly_label": prediction.anomaly_label,
                "anomaly_score": prediction.anomaly_score,
                "failure_probability_72h": prediction.failure_probability_72h,
                "estimated_rul_hours": prediction.estimated_rul_hours,
                "model_version": prediction.model_version,
            },
            "asset_context": context,
            "retrieval_query": retrieval_query,
            "playbook_defaults": issue,
            "evidence": [
                {
                    "title": item.title,
                    "vendor": item.vendor,
                    "source_path": item.source_path,
                    "source_type": item.source_type,
                    "chunk_index": item.chunk_index,
                    "score": item.score,
                    "excerpt": item.excerpt,
                }
                for item in evidence
            ],
        }

        if not evidence or not has_openai_api_key():
            return _fallback_response(payload, prediction, matches, evidence, issue, retrieval_query)

        try:
            generated = generate_root_cause_analysis(generation_payload)
        except OpenAIRagError:
            return _fallback_response(payload, prediction, matches, evidence, issue, retrieval_query)

        likely_causes = _unique_sentences(generated.get("likely_causes", []) + issue["likely_causes"], 4)
        recommended_actions = _unique_sentences(
            generated.get("recommended_actions", []) + issue["recommended_actions"],
            4,
        )
        grounded_summary = generated.get("grounded_summary") or (
            "Grounded analysis was generated from retrieved maintenance manual evidence."
        )

        return DiagnosticResponse(
            asset_id=payload.asset_id,
            likely_causes=likely_causes,
            recommended_actions=recommended_actions,
            evidence_sources=evidence_sources,
            grounded_summary=grounded_summary,
            retrieval_query=retrieval_query,
            confidence=generated.get("confidence", "medium"),
            generation_mode="openai_responses_rag",
            generation_model=settings.rag_response_model,
            evidence_snippets=evidence,
        )


rag_service = RagService()
