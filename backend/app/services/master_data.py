from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from uuid import uuid4

from app.core.db import get_connection
from app.models.schemas import (
    DefectResponse,
    DefectUpsert,
    EquipmentResponse,
    EquipmentUpsert,
    MaintenanceScheduleResponse,
    PlantResponse,
    PlantUpsert,
    SensorResponse,
    UserResponse,
    UserUpsert,
    VendorResponse,
    VendorUpsert,
    WorkOrderResponse,
    WorkOrderUpsert,
)
from app.services.auth import auth_service


def _next_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "record"


def _derive_asset_id(payload: EquipmentUpsert) -> str:
    if payload.asset_id:
        return payload.asset_id
    return _slugify(payload.equipment_number or payload.name)


def _derive_line_id(area: str) -> str:
    slug = _slugify(area)
    return f"line-{slug[:24]}" if slug else "line-general"


class MasterDataService:
    def _list_rows(self, query: str) -> list[dict]:
        with closing(get_connection()) as connection:
            rows = connection.execute(query).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _execute_write(operation):
        try:
            return operation()
        except sqlite3.IntegrityError as error:
            raise ValueError(str(error)) from error

    def list_plants(self) -> list[PlantResponse]:
        rows = self._list_rows(
            """
            SELECT plant_id, name, description, location, latitude, longitude, address, organization
            FROM plants
            ORDER BY name
            """
        )
        return [PlantResponse(**row) for row in rows]

    def create_plant(self, payload: PlantUpsert) -> PlantResponse:
        plant_id = payload.plant_id or _next_id("plant")

        def operation() -> PlantResponse:
            with closing(get_connection()) as connection:
                connection.execute(
                    """
                    INSERT INTO plants (
                        plant_id, name, description, location, latitude, longitude, address, organization
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        plant_id,
                        payload.name,
                        payload.description,
                        payload.location,
                        payload.latitude,
                        payload.longitude,
                        payload.address,
                        payload.organization,
                    ),
                )
                connection.commit()
            return PlantResponse(plant_id=plant_id, **payload.model_dump(exclude={"plant_id"}))

        return self._execute_write(operation)

    def update_plant(self, plant_id: str, payload: PlantUpsert) -> PlantResponse:
        def operation() -> PlantResponse:
            with closing(get_connection()) as connection:
                cursor = connection.execute(
                    """
                    UPDATE plants
                    SET name = ?, description = ?, location = ?, latitude = ?, longitude = ?, address = ?, organization = ?
                    WHERE plant_id = ?
                    """,
                    (
                        payload.name,
                        payload.description,
                        payload.location,
                        payload.latitude,
                        payload.longitude,
                        payload.address,
                        payload.organization,
                        plant_id,
                    ),
                )
                connection.commit()
                if cursor.rowcount == 0:
                    raise LookupError(f"Plant '{plant_id}' was not found.")
            return PlantResponse(plant_id=plant_id, **payload.model_dump(exclude={"plant_id"}))

        return self._execute_write(operation)

    def delete_plant(self, plant_id: str) -> None:
        def operation() -> None:
            with closing(get_connection()) as connection:
                cursor = connection.execute("DELETE FROM plants WHERE plant_id = ?", (plant_id,))
                connection.commit()
                if cursor.rowcount == 0:
                    raise LookupError(f"Plant '{plant_id}' was not found.")

        self._execute_write(operation)

    def list_vendors(self) -> list[VendorResponse]:
        rows = self._list_rows(
            """
            SELECT vendor_id, name, vendor_type, contact_person, email, phone, address, sla_level, status
            FROM vendors
            ORDER BY name
            """
        )
        return [VendorResponse(**row) for row in rows]

    def create_vendor(self, payload: VendorUpsert) -> VendorResponse:
        vendor_id = payload.vendor_id or _next_id("vendor")

        def operation() -> VendorResponse:
            with closing(get_connection()) as connection:
                connection.execute(
                    """
                    INSERT INTO vendors (
                        vendor_id, name, vendor_type, contact_person, email, phone, address, sla_level, status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        vendor_id,
                        payload.name,
                        payload.vendor_type,
                        payload.contact_person,
                        payload.email,
                        payload.phone,
                        payload.address,
                        payload.sla_level,
                        payload.status,
                    ),
                )
                connection.commit()
            return VendorResponse(vendor_id=vendor_id, **payload.model_dump(exclude={"vendor_id"}))

        return self._execute_write(operation)

    def update_vendor(self, vendor_id: str, payload: VendorUpsert) -> VendorResponse:
        def operation() -> VendorResponse:
            with closing(get_connection()) as connection:
                cursor = connection.execute(
                    """
                    UPDATE vendors
                    SET name = ?, vendor_type = ?, contact_person = ?, email = ?, phone = ?, address = ?, sla_level = ?, status = ?
                    WHERE vendor_id = ?
                    """,
                    (
                        payload.name,
                        payload.vendor_type,
                        payload.contact_person,
                        payload.email,
                        payload.phone,
                        payload.address,
                        payload.sla_level,
                        payload.status,
                        vendor_id,
                    ),
                )
                connection.commit()
                if cursor.rowcount == 0:
                    raise LookupError(f"Vendor '{vendor_id}' was not found.")
            return VendorResponse(vendor_id=vendor_id, **payload.model_dump(exclude={"vendor_id"}))

        return self._execute_write(operation)

    def delete_vendor(self, vendor_id: str) -> None:
        def operation() -> None:
            with closing(get_connection()) as connection:
                cursor = connection.execute("DELETE FROM vendors WHERE vendor_id = ?", (vendor_id,))
                connection.commit()
                if cursor.rowcount == 0:
                    raise LookupError(f"Vendor '{vendor_id}' was not found.")

        self._execute_write(operation)

    def list_equipment(self) -> list[EquipmentResponse]:
        rows = self._list_rows(
            """
            SELECT
                equipment_id,
                asset_id,
                equipment_number,
                name,
                model,
                category,
                description,
                plant_id,
                area,
                status,
                manufacturer,
                serial_number,
                asset_tag,
                criticality,
                install_date,
                commissioning_date,
                maintenance_strategy,
                warranty_expiry,
                vendor_id
            FROM equipment
            ORDER BY equipment_number
            """
        )
        return [EquipmentResponse(**row) for row in rows]

    def create_equipment(self, payload: EquipmentUpsert) -> EquipmentResponse:
        equipment_id = payload.equipment_id or _next_id("eq")
        asset_id = _derive_asset_id(payload)

        def operation() -> EquipmentResponse:
            with closing(get_connection()) as connection:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO assets (asset_id, name, asset_type, plant_id, line_id)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        asset_id,
                        payload.name,
                        payload.category.lower().replace(" ", "-"),
                        payload.plant_id,
                        _derive_line_id(payload.area),
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO equipment (
                        equipment_id, asset_id, equipment_number, name, model, category, description, plant_id,
                        area, status, manufacturer, serial_number, asset_tag, criticality, install_date,
                        commissioning_date, maintenance_strategy, warranty_expiry, vendor_id
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        equipment_id,
                        asset_id,
                        payload.equipment_number,
                        payload.name,
                        payload.model,
                        payload.category,
                        payload.description,
                        payload.plant_id,
                        payload.area,
                        payload.status,
                        payload.manufacturer,
                        payload.serial_number,
                        payload.asset_tag,
                        payload.criticality,
                        payload.install_date,
                        payload.commissioning_date,
                        payload.maintenance_strategy,
                        payload.warranty_expiry,
                        payload.vendor_id,
                    ),
                )
                connection.commit()
            return EquipmentResponse(
                equipment_id=equipment_id,
                asset_id=asset_id,
                **payload.model_dump(exclude={"equipment_id", "asset_id"}),
            )

        return self._execute_write(operation)

    def update_equipment(self, equipment_id: str, payload: EquipmentUpsert) -> EquipmentResponse:
        asset_id = _derive_asset_id(payload)

        def operation() -> EquipmentResponse:
            with closing(get_connection()) as connection:
                current = connection.execute(
                    "SELECT asset_id FROM equipment WHERE equipment_id = ?",
                    (equipment_id,),
                ).fetchone()
                if current is None:
                    raise LookupError(f"Equipment '{equipment_id}' was not found.")

                existing_asset_id = current["asset_id"]
                connection.execute(
                    """
                    INSERT OR IGNORE INTO assets (asset_id, name, asset_type, plant_id, line_id)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        asset_id,
                        payload.name,
                        payload.category.lower().replace(" ", "-"),
                        payload.plant_id,
                        _derive_line_id(payload.area),
                    ),
                )
                connection.execute(
                    """
                    UPDATE assets
                    SET name = ?, asset_type = ?, plant_id = ?, line_id = ?
                    WHERE asset_id = ?
                    """,
                    (
                        payload.name,
                        payload.category.lower().replace(" ", "-"),
                        payload.plant_id,
                        _derive_line_id(payload.area),
                        asset_id,
                    ),
                )
                cursor = connection.execute(
                    """
                    UPDATE equipment
                    SET asset_id = ?, equipment_number = ?, name = ?, model = ?, category = ?, description = ?,
                        plant_id = ?, area = ?, status = ?, manufacturer = ?, serial_number = ?, asset_tag = ?,
                        criticality = ?, install_date = ?, commissioning_date = ?, maintenance_strategy = ?,
                        warranty_expiry = ?, vendor_id = ?
                    WHERE equipment_id = ?
                    """,
                    (
                        asset_id,
                        payload.equipment_number,
                        payload.name,
                        payload.model,
                        payload.category,
                        payload.description,
                        payload.plant_id,
                        payload.area,
                        payload.status,
                        payload.manufacturer,
                        payload.serial_number,
                        payload.asset_tag,
                        payload.criticality,
                        payload.install_date,
                        payload.commissioning_date,
                        payload.maintenance_strategy,
                        payload.warranty_expiry,
                        payload.vendor_id,
                        equipment_id,
                    ),
                )
                if asset_id != existing_asset_id:
                    connection.execute(
                        """
                        UPDATE telemetry SET asset_id = ? WHERE asset_id = ?
                        """,
                        (asset_id, existing_asset_id),
                    )
                    connection.execute(
                        """
                        UPDATE alerts SET asset_id = ? WHERE asset_id = ?
                        """,
                        (asset_id, existing_asset_id),
                    )
                connection.commit()
                if cursor.rowcount == 0:
                    raise LookupError(f"Equipment '{equipment_id}' was not found.")
            return EquipmentResponse(
                equipment_id=equipment_id,
                asset_id=asset_id,
                **payload.model_dump(exclude={"equipment_id", "asset_id"}),
            )

        return self._execute_write(operation)

    def delete_equipment(self, equipment_id: str) -> None:
        def operation() -> None:
            with closing(get_connection()) as connection:
                current = connection.execute(
                    "SELECT asset_id FROM equipment WHERE equipment_id = ?",
                    (equipment_id,),
                ).fetchone()
                if current is None:
                    raise LookupError(f"Equipment '{equipment_id}' was not found.")
                asset_id = current["asset_id"]
                connection.execute("DELETE FROM sensors WHERE equipment_id = ?", (equipment_id,))
                cursor = connection.execute("DELETE FROM equipment WHERE equipment_id = ?", (equipment_id,))
                if asset_id:
                    connection.execute("DELETE FROM alerts WHERE asset_id = ?", (asset_id,))
                    connection.execute("DELETE FROM telemetry WHERE asset_id = ?", (asset_id,))
                    connection.execute("DELETE FROM assets WHERE asset_id = ?", (asset_id,))
                connection.commit()
                if cursor.rowcount == 0:
                    raise LookupError(f"Equipment '{equipment_id}' was not found.")

        self._execute_write(operation)

    def list_sensors(self) -> list[SensorResponse]:
        rows = self._list_rows(
            """
            SELECT sensor_id, equipment_id, tag, name, sensor_type, unit, location, is_critical
            FROM sensors
            ORDER BY equipment_id, tag
            """
        )
        return [SensorResponse(**row) for row in rows]

    def list_users(self) -> list[UserResponse]:
        rows = self._list_rows(
            """
            SELECT user_id, full_name, email, role, plant_scope, status, last_login
            FROM users
            ORDER BY full_name
            """
        )
        return [UserResponse(**row) for row in rows]

    def create_user(self, payload: UserUpsert) -> UserResponse:
        user_id = payload.user_id or _next_id("user")
        password_hash = auth_service.hash_password(payload.password)

        def operation() -> UserResponse:
            with closing(get_connection()) as connection:
                connection.execute(
                    """
                    INSERT INTO users (user_id, full_name, email, role, plant_scope, status, last_login, password_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        payload.full_name,
                        payload.email,
                        payload.role,
                        payload.plant_scope,
                        payload.status,
                        payload.last_login,
                        password_hash,
                    ),
                )
                connection.commit()
            return UserResponse(user_id=user_id, **payload.model_dump(exclude={"user_id", "password"}))

        return self._execute_write(operation)

    def update_user(self, user_id: str, payload: UserUpsert) -> UserResponse:
        password_hash = auth_service.hash_password(payload.password) if payload.password else None

        def operation() -> UserResponse:
            with closing(get_connection()) as connection:
                cursor = connection.execute(
                    """
                    UPDATE users
                    SET full_name = ?, email = ?, role = ?, plant_scope = ?, status = ?, last_login = ?,
                        password_hash = COALESCE(?, password_hash)
                    WHERE user_id = ?
                    """,
                    (
                        payload.full_name,
                        payload.email,
                        payload.role,
                        payload.plant_scope,
                        payload.status,
                        payload.last_login,
                        password_hash,
                        user_id,
                    ),
                )
                connection.commit()
                if cursor.rowcount == 0:
                    raise LookupError(f"User '{user_id}' was not found.")
            return UserResponse(user_id=user_id, **payload.model_dump(exclude={"user_id", "password"}))

        return self._execute_write(operation)

    def delete_user(self, user_id: str) -> None:
        def operation() -> None:
            with closing(get_connection()) as connection:
                cursor = connection.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
                connection.commit()
                if cursor.rowcount == 0:
                    raise LookupError(f"User '{user_id}' was not found.")

        self._execute_write(operation)

    def list_maintenance_schedules(self) -> list[MaintenanceScheduleResponse]:
        rows = self._list_rows(
            """
            SELECT schedule_id, asset_name, schedule_type, cadence, next_due, owner, status
            FROM maintenance_schedules
            ORDER BY next_due, asset_name
            """
        )
        return [MaintenanceScheduleResponse(**row) for row in rows]

    def list_work_orders(self) -> list[WorkOrderResponse]:
        rows = self._list_rows(
            """
            SELECT
                work_order_id,
                title,
                asset_name,
                priority,
                work_type,
                requested_by,
                assignee,
                due_date,
                status,
                summary
            FROM work_orders
            ORDER BY due_date, title
            """
        )
        return [WorkOrderResponse(**row) for row in rows]

    def create_work_order(self, payload: WorkOrderUpsert) -> WorkOrderResponse:
        work_order_id = payload.work_order_id or _next_id("wo")

        def operation() -> WorkOrderResponse:
            with closing(get_connection()) as connection:
                connection.execute(
                    """
                    INSERT INTO work_orders (
                        work_order_id, title, asset_name, priority, work_type, requested_by,
                        assignee, due_date, status, summary
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        work_order_id,
                        payload.title,
                        payload.asset_name,
                        payload.priority,
                        payload.work_type,
                        payload.requested_by,
                        payload.assignee,
                        payload.due_date,
                        payload.status,
                        payload.summary,
                    ),
                )
                connection.commit()
            return WorkOrderResponse(work_order_id=work_order_id, **payload.model_dump(exclude={"work_order_id"}))

        return self._execute_write(operation)

    def update_work_order(self, work_order_id: str, payload: WorkOrderUpsert) -> WorkOrderResponse:
        def operation() -> WorkOrderResponse:
            with closing(get_connection()) as connection:
                cursor = connection.execute(
                    """
                    UPDATE work_orders
                    SET title = ?, asset_name = ?, priority = ?, work_type = ?, requested_by = ?,
                        assignee = ?, due_date = ?, status = ?, summary = ?
                    WHERE work_order_id = ?
                    """,
                    (
                        payload.title,
                        payload.asset_name,
                        payload.priority,
                        payload.work_type,
                        payload.requested_by,
                        payload.assignee,
                        payload.due_date,
                        payload.status,
                        payload.summary,
                        work_order_id,
                    ),
                )
                connection.commit()
                if cursor.rowcount == 0:
                    raise LookupError(f"Work order '{work_order_id}' was not found.")
            return WorkOrderResponse(work_order_id=work_order_id, **payload.model_dump(exclude={"work_order_id"}))

        return self._execute_write(operation)

    def delete_work_order(self, work_order_id: str) -> None:
        def operation() -> None:
            with closing(get_connection()) as connection:
                cursor = connection.execute("DELETE FROM work_orders WHERE work_order_id = ?", (work_order_id,))
                connection.commit()
                if cursor.rowcount == 0:
                    raise LookupError(f"Work order '{work_order_id}' was not found.")

        self._execute_write(operation)

    def list_defects(self) -> list[DefectResponse]:
        rows = self._list_rows(
            """
            SELECT defect_id, asset_name, defect_code, severity, status, discovered_on, description, owner
            FROM defects
            ORDER BY discovered_on DESC, defect_code
            """
        )
        return [DefectResponse(**row) for row in rows]

    def create_defect(self, payload: DefectUpsert) -> DefectResponse:
        defect_id = payload.defect_id or _next_id("df")

        def operation() -> DefectResponse:
            with closing(get_connection()) as connection:
                connection.execute(
                    """
                    INSERT INTO defects (
                        defect_id, asset_name, defect_code, severity, status, discovered_on, description, owner
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        defect_id,
                        payload.asset_name,
                        payload.defect_code,
                        payload.severity,
                        payload.status,
                        payload.discovered_on,
                        payload.description,
                        payload.owner,
                    ),
                )
                connection.commit()
            return DefectResponse(defect_id=defect_id, **payload.model_dump(exclude={"defect_id"}))

        return self._execute_write(operation)

    def update_defect(self, defect_id: str, payload: DefectUpsert) -> DefectResponse:
        def operation() -> DefectResponse:
            with closing(get_connection()) as connection:
                cursor = connection.execute(
                    """
                    UPDATE defects
                    SET asset_name = ?, defect_code = ?, severity = ?, status = ?, discovered_on = ?, description = ?, owner = ?
                    WHERE defect_id = ?
                    """,
                    (
                        payload.asset_name,
                        payload.defect_code,
                        payload.severity,
                        payload.status,
                        payload.discovered_on,
                        payload.description,
                        payload.owner,
                        defect_id,
                    ),
                )
                connection.commit()
                if cursor.rowcount == 0:
                    raise LookupError(f"Defect '{defect_id}' was not found.")
            return DefectResponse(defect_id=defect_id, **payload.model_dump(exclude={"defect_id"}))

        return self._execute_write(operation)

    def delete_defect(self, defect_id: str) -> None:
        def operation() -> None:
            with closing(get_connection()) as connection:
                cursor = connection.execute("DELETE FROM defects WHERE defect_id = ?", (defect_id,))
                connection.commit()
                if cursor.rowcount == 0:
                    raise LookupError(f"Defect '{defect_id}' was not found.")

        self._execute_write(operation)


master_data_service = MasterDataService()
