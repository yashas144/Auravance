from fastapi import APIRouter, Depends, HTTPException, status

from app.models.schemas import (
    AuthenticatedUserResponse,
    DefectResponse,
    DefectUpsert,
    DeleteResponse,
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
from app.services.auth import ADMIN_ROLES, EDITOR_ROLES, MANAGEMENT_ROLES, auth_service, require_roles
from app.services.master_data import master_data_service

router = APIRouter()


def _handle_write(action):
    try:
        return action()
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.get("/plants", response_model=list[PlantResponse])
def list_plants(_: AuthenticatedUserResponse = Depends(auth_service.get_current_user)) -> list[PlantResponse]:
    return master_data_service.list_plants()


@router.post("/plants", response_model=PlantResponse, status_code=status.HTTP_201_CREATED)
def create_plant(
    payload: PlantUpsert,
    _: AuthenticatedUserResponse = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> PlantResponse:
    return _handle_write(lambda: master_data_service.create_plant(payload))


@router.put("/plants/{plant_id}", response_model=PlantResponse)
def update_plant(
    plant_id: str,
    payload: PlantUpsert,
    _: AuthenticatedUserResponse = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> PlantResponse:
    return _handle_write(lambda: master_data_service.update_plant(plant_id, payload))


@router.delete("/plants/{plant_id}", response_model=DeleteResponse)
def delete_plant(
    plant_id: str,
    _: AuthenticatedUserResponse = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> DeleteResponse:
    _handle_write(lambda: master_data_service.delete_plant(plant_id))
    return DeleteResponse(record_id=plant_id)


@router.get("/vendors", response_model=list[VendorResponse])
def list_vendors(_: AuthenticatedUserResponse = Depends(auth_service.get_current_user)) -> list[VendorResponse]:
    return master_data_service.list_vendors()


@router.post("/vendors", response_model=VendorResponse, status_code=status.HTTP_201_CREATED)
def create_vendor(
    payload: VendorUpsert,
    _: AuthenticatedUserResponse = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> VendorResponse:
    return _handle_write(lambda: master_data_service.create_vendor(payload))


@router.put("/vendors/{vendor_id}", response_model=VendorResponse)
def update_vendor(
    vendor_id: str,
    payload: VendorUpsert,
    _: AuthenticatedUserResponse = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> VendorResponse:
    return _handle_write(lambda: master_data_service.update_vendor(vendor_id, payload))


@router.delete("/vendors/{vendor_id}", response_model=DeleteResponse)
def delete_vendor(
    vendor_id: str,
    _: AuthenticatedUserResponse = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> DeleteResponse:
    _handle_write(lambda: master_data_service.delete_vendor(vendor_id))
    return DeleteResponse(record_id=vendor_id)


@router.get("/equipment", response_model=list[EquipmentResponse])
def list_equipment(_: AuthenticatedUserResponse = Depends(auth_service.get_current_user)) -> list[EquipmentResponse]:
    return master_data_service.list_equipment()


@router.post("/equipment", response_model=EquipmentResponse, status_code=status.HTTP_201_CREATED)
def create_equipment(
    payload: EquipmentUpsert,
    _: AuthenticatedUserResponse = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> EquipmentResponse:
    return _handle_write(lambda: master_data_service.create_equipment(payload))


@router.put("/equipment/{equipment_id}", response_model=EquipmentResponse)
def update_equipment(
    equipment_id: str,
    payload: EquipmentUpsert,
    _: AuthenticatedUserResponse = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> EquipmentResponse:
    return _handle_write(lambda: master_data_service.update_equipment(equipment_id, payload))


@router.delete("/equipment/{equipment_id}", response_model=DeleteResponse)
def delete_equipment(
    equipment_id: str,
    _: AuthenticatedUserResponse = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> DeleteResponse:
    _handle_write(lambda: master_data_service.delete_equipment(equipment_id))
    return DeleteResponse(record_id=equipment_id)


@router.get("/sensors", response_model=list[SensorResponse])
def list_sensors(_: AuthenticatedUserResponse = Depends(auth_service.get_current_user)) -> list[SensorResponse]:
    return master_data_service.list_sensors()


@router.get("/users", response_model=list[UserResponse])
def list_users(_: AuthenticatedUserResponse = Depends(require_roles(*ADMIN_ROLES))) -> list[UserResponse]:
    return master_data_service.list_users()


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserUpsert,
    _: AuthenticatedUserResponse = Depends(require_roles(*ADMIN_ROLES)),
) -> UserResponse:
    return _handle_write(lambda: master_data_service.create_user(payload))


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    payload: UserUpsert,
    _: AuthenticatedUserResponse = Depends(require_roles(*ADMIN_ROLES)),
) -> UserResponse:
    return _handle_write(lambda: master_data_service.update_user(user_id, payload))


@router.delete("/users/{user_id}", response_model=DeleteResponse)
def delete_user(
    user_id: str,
    _: AuthenticatedUserResponse = Depends(require_roles(*ADMIN_ROLES)),
) -> DeleteResponse:
    _handle_write(lambda: master_data_service.delete_user(user_id))
    return DeleteResponse(record_id=user_id)


@router.get("/maintenance-schedules", response_model=list[MaintenanceScheduleResponse])
def list_maintenance_schedules(
    _: AuthenticatedUserResponse = Depends(auth_service.get_current_user),
) -> list[MaintenanceScheduleResponse]:
    return master_data_service.list_maintenance_schedules()


@router.get("/work-orders", response_model=list[WorkOrderResponse])
def list_work_orders(_: AuthenticatedUserResponse = Depends(auth_service.get_current_user)) -> list[WorkOrderResponse]:
    return master_data_service.list_work_orders()


@router.post("/work-orders", response_model=WorkOrderResponse, status_code=status.HTTP_201_CREATED)
def create_work_order(
    payload: WorkOrderUpsert,
    _: AuthenticatedUserResponse = Depends(require_roles(*EDITOR_ROLES)),
) -> WorkOrderResponse:
    return _handle_write(lambda: master_data_service.create_work_order(payload))


@router.put("/work-orders/{work_order_id}", response_model=WorkOrderResponse)
def update_work_order(
    work_order_id: str,
    payload: WorkOrderUpsert,
    _: AuthenticatedUserResponse = Depends(require_roles(*EDITOR_ROLES)),
) -> WorkOrderResponse:
    return _handle_write(lambda: master_data_service.update_work_order(work_order_id, payload))


@router.delete("/work-orders/{work_order_id}", response_model=DeleteResponse)
def delete_work_order(
    work_order_id: str,
    _: AuthenticatedUserResponse = Depends(require_roles(*EDITOR_ROLES)),
) -> DeleteResponse:
    _handle_write(lambda: master_data_service.delete_work_order(work_order_id))
    return DeleteResponse(record_id=work_order_id)


@router.get("/defects", response_model=list[DefectResponse])
def list_defects(_: AuthenticatedUserResponse = Depends(auth_service.get_current_user)) -> list[DefectResponse]:
    return master_data_service.list_defects()


@router.post("/defects", response_model=DefectResponse, status_code=status.HTTP_201_CREATED)
def create_defect(
    payload: DefectUpsert,
    _: AuthenticatedUserResponse = Depends(require_roles(*EDITOR_ROLES)),
) -> DefectResponse:
    return _handle_write(lambda: master_data_service.create_defect(payload))


@router.put("/defects/{defect_id}", response_model=DefectResponse)
def update_defect(
    defect_id: str,
    payload: DefectUpsert,
    _: AuthenticatedUserResponse = Depends(require_roles(*EDITOR_ROLES)),
) -> DefectResponse:
    return _handle_write(lambda: master_data_service.update_defect(defect_id, payload))


@router.delete("/defects/{defect_id}", response_model=DeleteResponse)
def delete_defect(
    defect_id: str,
    _: AuthenticatedUserResponse = Depends(require_roles(*EDITOR_ROLES)),
) -> DeleteResponse:
    _handle_write(lambda: master_data_service.delete_defect(defect_id))
    return DeleteResponse(record_id=defect_id)
