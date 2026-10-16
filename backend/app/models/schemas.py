from datetime import datetime

from pydantic import BaseModel, Field


class DeleteResponse(BaseModel):
    status: str = "deleted"
    record_id: str


class AssetCreate(BaseModel):
    asset_id: str
    name: str
    asset_type: str
    plant_id: str
    line_id: str


class AssetResponse(AssetCreate):
    pass


class PlantResponse(BaseModel):
    plant_id: str
    name: str
    description: str
    location: str
    latitude: str
    longitude: str
    address: str
    organization: str


class PlantUpsert(BaseModel):
    plant_id: str | None = None
    name: str
    description: str
    location: str
    latitude: str
    longitude: str
    address: str
    organization: str


class VendorResponse(BaseModel):
    vendor_id: str
    name: str
    vendor_type: str
    contact_person: str
    email: str
    phone: str
    address: str
    sla_level: str
    status: str


class VendorUpsert(BaseModel):
    vendor_id: str | None = None
    name: str
    vendor_type: str
    contact_person: str
    email: str
    phone: str
    address: str
    sla_level: str
    status: str


class EquipmentResponse(BaseModel):
    equipment_id: str
    asset_id: str | None = None
    equipment_number: str
    name: str
    model: str
    category: str
    description: str
    plant_id: str
    area: str
    status: str
    manufacturer: str
    serial_number: str
    asset_tag: str
    criticality: str
    install_date: str
    commissioning_date: str
    maintenance_strategy: str
    warranty_expiry: str
    vendor_id: str


class EquipmentUpsert(BaseModel):
    equipment_id: str | None = None
    asset_id: str | None = None
    equipment_number: str
    name: str
    model: str
    category: str
    description: str
    plant_id: str
    area: str
    status: str
    manufacturer: str
    serial_number: str
    asset_tag: str
    criticality: str
    install_date: str
    commissioning_date: str
    maintenance_strategy: str
    warranty_expiry: str
    vendor_id: str


class SensorResponse(BaseModel):
    sensor_id: str
    equipment_id: str
    tag: str
    name: str
    sensor_type: str
    unit: str
    location: str
    is_critical: bool


class UserResponse(BaseModel):
    user_id: str
    full_name: str
    email: str
    role: str
    plant_scope: str
    status: str
    last_login: str


class UserUpsert(BaseModel):
    user_id: str | None = None
    full_name: str
    email: str
    role: str
    plant_scope: str
    status: str
    last_login: str
    password: str | None = None


class AuthenticatedUserResponse(BaseModel):
    user_id: str
    full_name: str
    email: str
    role: str
    plant_scope: str
    status: str
    last_login: str


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: str
    user: AuthenticatedUserResponse


class MaintenanceScheduleResponse(BaseModel):
    schedule_id: str
    asset_name: str
    schedule_type: str
    cadence: str
    next_due: str
    owner: str
    status: str


class WorkOrderResponse(BaseModel):
    work_order_id: str
    title: str
    asset_name: str
    priority: str
    work_type: str
    requested_by: str
    assignee: str
    due_date: str
    status: str
    summary: str


class WorkOrderUpsert(BaseModel):
    work_order_id: str | None = None
    title: str
    asset_name: str
    priority: str
    work_type: str
    requested_by: str
    assignee: str
    due_date: str
    status: str
    summary: str


class DefectResponse(BaseModel):
    defect_id: str
    asset_name: str
    defect_code: str
    severity: str
    status: str
    discovered_on: str
    description: str
    owner: str


class DefectUpsert(BaseModel):
    defect_id: str | None = None
    asset_name: str
    defect_code: str
    severity: str
    status: str
    discovered_on: str
    description: str
    owner: str


class TelemetryMetrics(BaseModel):
    temperature_c: float | None = None
    vibration_rms: float | None = None
    pressure_bar: float | None = None
    current_a: float | None = None


class TelemetryIngestRequest(BaseModel):
    timestamp: datetime
    asset_id: str
    metrics: TelemetryMetrics
    source: str = "api"
    source_context: dict[str, str | float | None] = Field(default_factory=dict)


class TelemetryIngestResponse(BaseModel):
    status: str
    asset_id: str
    received_at: datetime


class TelemetryBatchIngestRequest(BaseModel):
    readings: list[TelemetryIngestRequest] = Field(min_length=1, max_length=500)


class TelemetryBatchIngestResponse(BaseModel):
    status: str
    accepted: int
    asset_ids: list[str]
    received_at: datetime


class TelemetryRecord(BaseModel):
    asset_id: str
    timestamp: datetime
    temperature_c: float | None = None
    vibration_rms: float | None = None
    pressure_bar: float | None = None
    current_a: float | None = None
    source: str | None = None
    source_context: dict[str, str | float | None] = Field(default_factory=dict)


class PredictionResponse(BaseModel):
    asset_id: str
    anomaly_score: float = Field(ge=0.0, le=1.0)
    anomaly_label: str
    failure_probability_72h: float = Field(ge=0.0, le=1.0)
    estimated_rul_hours: float = Field(gt=0.0)
    model_version: str
    dominant_signal: str
    anomaly_model_version: str | None = None
    failure_model_version: str | None = None
    rul_model_version: str | None = None


class AnomalyModelStatusResponse(BaseModel):
    loaded: bool
    artifact_exists: bool
    model_version: str
    algorithm: str
    trained_at: str | None = None
    source_dataset: str | None = None
    feature_names: list[str] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    fallback_active: bool
    detail: str


class PredictionModelsStatusResponse(BaseModel):
    anomaly: AnomalyModelStatusResponse
    failure: AnomalyModelStatusResponse
    rul: AnomalyModelStatusResponse
    # Every equipment profile (pump, compressor, motor) with its three models.
    profiles: dict[str, dict[str, AnomalyModelStatusResponse]] = Field(default_factory=dict)


class IngestTargetResponse(BaseModel):
    asset_id: str
    asset_type: str
    profile: str


class DiagnosticRequest(BaseModel):
    asset_id: str
    symptom_summary: str
    recent_alert_ids: list[str] = Field(default_factory=list)


class DiagnosticEvidenceResponse(BaseModel):
    title: str
    vendor: str
    source_path: str
    source_type: str
    chunk_index: int
    score: float
    excerpt: str


class DiagnosticResponse(BaseModel):
    asset_id: str
    likely_causes: list[str]
    recommended_actions: list[str]
    evidence_sources: list[str]
    grounded_summary: str | None = None
    retrieval_query: str | None = None
    confidence: str | None = None
    generation_mode: str | None = None
    generation_model: str | None = None
    evidence_snippets: list[DiagnosticEvidenceResponse] = Field(default_factory=list)


class RagStatusResponse(BaseModel):
    openai_api_key_loaded: bool
    response_model: str
    embedding_model: str
    knowledge_documents: int
    knowledge_chunks: int
    embedded_chunks: int


class AlertResponse(BaseModel):
    alert_id: str
    asset_id: str
    severity: str
    message: str
    status: str
    created_at: datetime


class DatasetArtifactResponse(BaseModel):
    artifact_type: str
    file_path: str
    row_count: int | None = None
    metadata: dict = Field(default_factory=dict)
    created_at: str


class DatasetResponse(BaseModel):
    dataset_id: str
    name: str
    source: str
    raw_path: str
    extracted_path: str | None = None
    processed_path: str | None = None
    status: str
    record_count: int = 0
    notes: str | None = None
    last_synced_at: str
    artifacts: list[DatasetArtifactResponse] = Field(default_factory=list)


class KnowledgeDocumentResponse(BaseModel):
    document_id: str
    title: str
    vendor: str
    source_type: str
    source_path: str
    processed_path: str
    chunk_path: str
    page_count: int = 0
    chunk_count: int = 0
    status: str
    notes: str | None = None
    created_at: str
    updated_at: str


class KnowledgeSearchResultResponse(BaseModel):
    document_id: str
    title: str
    vendor: str
    source_path: str
    source_type: str
    chunk_index: int
    score: float
    content_preview: str
