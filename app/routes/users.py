from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app import crud
from app.auth import ensure_user_access, get_current_user, public_user, require_roles
from app.database import get_database
from app.models import UserRole
from app.schemas import LeaveQuotaCreate, LeaveQuotaRead, UserCreate, UserRead, UserUpdate


router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    user: UserCreate,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(require_roles(UserRole.admin)),
) -> UserRead:
    _ = current_user
    return await crud.create_user(db, user)


@router.get("", response_model=List[UserRead])
async def list_users(
    role: Optional[UserRole] = Query(default=None),
    manager_id: Optional[str] = Query(default=None),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> List[UserRead]:
    if current_user["role"] == UserRole.employee.value:
        return [public_user(current_user)]
    if current_user["role"] == UserRole.manager.value:
        manager_id = str(current_user["_id"])
    return await crud.list_users(db, role=role, manager_id=manager_id)


@router.get("/me", response_model=UserRead)
async def get_me(current_user: dict = Depends(get_current_user)) -> UserRead:
    return public_user(current_user)


@router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> UserRead:
    target = await ensure_user_access(db, current_user, user_id)
    return public_user(target)


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: str,
    user: UserUpdate,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(require_roles(UserRole.admin)),
) -> UserRead:
    _ = current_user
    return await crud.update_user(db, user_id, user)


@router.get("/{user_id}/quotas", response_model=List[LeaveQuotaRead])
async def get_user_leave_quotas(
    user_id: str,
    year: Optional[int] = Query(default=None),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> List[LeaveQuotaRead]:
    await ensure_user_access(db, current_user, user_id)
    return await crud.get_user_leave_quotas(db, user_id, year=year)


@router.post("/{user_id}/quotas", response_model=LeaveQuotaRead, status_code=status.HTTP_201_CREATED)
async def create_user_leave_quota(
    user_id: str,
    quota: LeaveQuotaCreate,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(require_roles(UserRole.admin)),
) -> LeaveQuotaRead:
    _ = current_user
    quota.user_id = user_id
    return await crud.create_leave_quota(db, quota)
