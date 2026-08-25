import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file(BASE_DIR / ".env")


@dataclass(slots=True)
class Settings:
    app_name: str = os.getenv("AURAVANCE_APP_NAME", "Auravance Backend")
    app_version: str = os.getenv("AURAVANCE_APP_VERSION", "0.1.0")
    api_prefix: str = os.getenv("AURAVANCE_API_PREFIX", "/api/v1")
    demo_db_path: str = os.getenv(
        "AURAVANCE_DEMO_DB_PATH",
        str(BASE_DIR / "data" / "auravance_demo.db"),
    )
    simulator_interval_seconds: int = int(os.getenv("AURAVANCE_SIMULATOR_INTERVAL_SECONDS", "3"))
    model_registry_path: str = os.getenv(
        "AURAVANCE_MODEL_REGISTRY_PATH",
        str(BASE_DIR / "artifacts" / "models"),
    )
    anomaly_model_path: str = os.getenv(
        "AURAVANCE_ANOMALY_MODEL_PATH",
        str(BASE_DIR / "artifacts" / "models" / "anomaly_isolation_forest.joblib"),
    )
    failure_model_path: str = os.getenv(
        "AURAVANCE_FAILURE_MODEL_PATH",
        str(BASE_DIR / "artifacts" / "models" / "failure_gradient_boosting.joblib"),
    )
    rul_model_path: str = os.getenv(
        "AURAVANCE_RUL_MODEL_PATH",
        str(BASE_DIR / "artifacts" / "models" / "rul_gradient_boosting.joblib"),
    )
    raw_data_root: str = os.getenv(
        "AURAVANCE_RAW_DATA_ROOT",
        str(BASE_DIR / "data" / "raw"),
    )
    interim_data_root: str = os.getenv(
        "AURAVANCE_INTERIM_DATA_ROOT",
        str(BASE_DIR / "data" / "interim"),
    )
    processed_data_root: str = os.getenv(
        "AURAVANCE_PROCESSED_DATA_ROOT",
        str(BASE_DIR / "data" / "processed"),
    )
    feature_data_root: str = os.getenv(
        "AURAVANCE_FEATURE_DATA_ROOT",
        str(BASE_DIR / "data" / "features"),
    )
    knowledge_raw_root: str = os.getenv(
        "AURAVANCE_KNOWLEDGE_RAW_ROOT",
        str(BASE_DIR / "knowledge" / "raw"),
    )
    knowledge_processed_root: str = os.getenv(
        "AURAVANCE_KNOWLEDGE_PROCESSED_ROOT",
        str(BASE_DIR / "knowledge" / "processed"),
    )
    knowledge_chunks_root: str = os.getenv(
        "AURAVANCE_KNOWLEDGE_CHUNKS_ROOT",
        str(BASE_DIR / "knowledge" / "chunks"),
    )
    rag_response_model: str = os.getenv(
        "AURAVANCE_RAG_RESPONSE_MODEL",
        "gpt-4.1-mini",
    )
    rag_embedding_model: str = os.getenv(
        "AURAVANCE_RAG_EMBEDDING_MODEL",
        "text-embedding-3-small",
    )
    rag_embedding_dimensions: int = int(
        os.getenv("AURAVANCE_RAG_EMBEDDING_DIMENSIONS", "1536")
    )
    rag_retrieval_limit: int = int(os.getenv("AURAVANCE_RAG_RETRIEVAL_LIMIT", "5"))
    rag_generation_temperature: float = float(
        os.getenv("AURAVANCE_RAG_GENERATION_TEMPERATURE", "0.2")
    )
    auth_secret_key: str = os.getenv(
        "AURAVANCE_AUTH_SECRET_KEY",
        "auravance-dev-secret-change-me",
    )
    auth_token_ttl_hours: int = int(os.getenv("AURAVANCE_AUTH_TOKEN_TTL_HOURS", "12"))


settings = Settings()
