from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app import crud
from app.database import get_database
from app.models import LeaveStatus
from app.schemas import LeaveRequestCreate, LeaveRequestRead, LeaveRequestUpdate


router = APIRouter(prefix="/leaves", tags=["leaves"])


@router.post("", response_model=LeaveRequestRead, status_code=status.HTTP_201_CREATED)
async def create_leave_request(
    leave: LeaveRequestCreate,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> LeaveRequestRead:
    return await crud.create_leave_request(db, leave)


@router.get("", response_model=List[LeaveRequestRead])
async def list_leave_requests(
    user_id: Optional[str] = Query(default=None),
    manager_id: Optional[str] = Query(default=None),
    status_filter: Optional[LeaveStatus] = Query(default=None, alias="status"),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> List[LeaveRequestRead]:
    return await crud.list_leave_requests(
        db,
        user_id=user_id,
        manager_id=manager_id,
        status_filter=status_filter,
    )


@router.get("/{leave_id}", response_model=LeaveRequestRead)
async def get_leave_request(
    leave_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> LeaveRequestRead:
    return await crud.get_leave_request(db, leave_id)


@router.patch("/{leave_id}", response_model=LeaveRequestRead)
async def update_leave_request(
    leave_id: str,
    update: LeaveRequestUpdate,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> LeaveRequestRead:
    return await crud.update_leave_request(db, leave_id, update)
