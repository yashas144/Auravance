from app.core.db import fetch_datasets
from app.models.schemas import DatasetResponse


def list_datasets() -> list[DatasetResponse]:
    return [DatasetResponse.model_validate(dataset) for dataset in fetch_datasets()]
