from __future__ import annotations

from contextlib import closing

from app.core.db import get_connection
from app.models.schemas import AssetCreate, AssetResponse


class AssetsService:
    def list_assets(self) -> list[AssetResponse]:
        with closing(get_connection()) as connection:
            rows = connection.execute(
                """
                SELECT asset_id, name, asset_type, plant_id, line_id
                FROM assets
                ORDER BY asset_id
                """
            ).fetchall()
        return [AssetResponse(**dict(row)) for row in rows]

    def create_asset(self, payload: AssetCreate) -> AssetResponse:
        with closing(get_connection()) as connection:
            connection.execute(
                """
                INSERT INTO assets (asset_id, name, asset_type, plant_id, line_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    payload.asset_id,
                    payload.name,
                    payload.asset_type,
                    payload.plant_id,
                    payload.line_id,
                ),
            )
            connection.commit()
        return AssetResponse(**payload.model_dump())


assets_service = AssetsService()
