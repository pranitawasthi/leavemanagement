from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app import crud
from app.auth import get_current_user
from app.database import get_database
from app.models import LeaveStatus, UserRole
from app.schemas import LeaveRequestCreate, LeaveRequestRead, LeaveRequestUpdate


router = APIRouter(prefix="/leaves", tags=["leaves"])


async def ensure_leave_access(
    db: AsyncIOMotorDatabase,
    leave_id: str,
    current_user: dict,
) -> dict:
    leave = await db.leave_requests.find_one({"_id": crud.to_object_id(leave_id)})
    if not leave:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")

    if current_user["role"] == UserRole.admin.value:
        return leave
    if str(leave["user_id"]) == str(current_user["_id"]):
        return leave
    if current_user["role"] == UserRole.manager.value and leave["manager_id"] == current_user["_id"]:
        return leave

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access this leave request")


@router.post("", response_model=LeaveRequestRead, status_code=status.HTTP_201_CREATED)
async def create_leave_request(
    leave: LeaveRequestCreate,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> LeaveRequestRead:
    if current_user["role"] == UserRole.employee.value and leave.user_id != str(current_user["_id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employees can only request their own leave")
    if current_user["role"] == UserRole.manager.value and leave.user_id != str(current_user["_id"]):
        target = await db.users.find_one({"_id": crud.to_object_id(leave.user_id)})
        if not target or target.get("manager_id") != current_user["_id"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Managers can only create leave for themselves or their team")
    return await crud.create_leave_request(db, leave)


@router.get("", response_model=List[LeaveRequestRead])
async def list_leave_requests(
    user_id: Optional[str] = Query(default=None),
    manager_id: Optional[str] = Query(default=None),
    status_filter: Optional[LeaveStatus] = Query(default=None, alias="status"),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> List[LeaveRequestRead]:
    if current_user["role"] == UserRole.employee.value:
        user_id = str(current_user["_id"])
        manager_id = None
    elif current_user["role"] == UserRole.manager.value:
        manager_id = str(current_user["_id"])
    return await crud.list_leave_requests(
        db,
        user_id=user_id,
        manager_id=manager_id,
        status_filter=status_filter,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/{leave_id}", response_model=LeaveRequestRead)
async def get_leave_request(
    leave_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> LeaveRequestRead:
    await ensure_leave_access(db, leave_id, current_user)
    return await crud.get_leave_request(db, leave_id)


@router.patch("/{leave_id}", response_model=LeaveRequestRead)
async def update_leave_request(
    leave_id: str,
    update: LeaveRequestUpdate,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> LeaveRequestRead:
    leave = await ensure_leave_access(db, leave_id, current_user)
    if current_user["role"] == UserRole.manager.value and leave["user_id"] != current_user["_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Managers cannot edit team member requests")
    return await crud.update_leave_request(db, leave_id, update)
