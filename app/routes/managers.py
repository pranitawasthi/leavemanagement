from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app import crud
from app.auth import require_roles
from app.database import get_database
from app.models import LeaveStatus, UserRole
from app.schemas import LeaveDecision, LeaveRequestRead


router = APIRouter(prefix="/managers", tags=["managers"])


@router.get("/{manager_id}/leave-requests/pending", response_model=List[LeaveRequestRead])
async def list_pending_manager_leave_requests(
    manager_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(require_roles(UserRole.manager, UserRole.admin)),
) -> List[LeaveRequestRead]:
    if current_user["role"] == UserRole.manager.value and manager_id != str(current_user["_id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Managers can only view their own queue")
    return await crud.list_leave_requests(
        db,
        manager_id=manager_id,
        status_filter=LeaveStatus.pending,
    )


@router.get("/{manager_id}/leave-requests/history", response_model=List[LeaveRequestRead])
async def list_manager_leave_history(
    manager_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(require_roles(UserRole.manager, UserRole.admin)),
) -> List[LeaveRequestRead]:
    if current_user["role"] == UserRole.manager.value and manager_id != str(current_user["_id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Managers can only view their own history")
    return await crud.list_leave_requests(db, manager_id=manager_id)


@router.patch("/leave-requests/{leave_id}/approve", response_model=LeaveRequestRead)
async def approve_leave_request(
    leave_id: str,
    decision: LeaveDecision,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(require_roles(UserRole.manager, UserRole.admin)),
) -> LeaveRequestRead:
    if current_user["role"] == UserRole.manager.value and decision.manager_id != str(current_user["_id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Managers can only approve as themselves")
    return await crud.decide_leave_request(db, leave_id, decision, approved=True)


@router.patch("/leave-requests/{leave_id}/reject", response_model=LeaveRequestRead)
async def reject_leave_request(
    leave_id: str,
    decision: LeaveDecision,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(require_roles(UserRole.manager, UserRole.admin)),
) -> LeaveRequestRead:
    if current_user["role"] == UserRole.manager.value and decision.manager_id != str(current_user["_id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Managers can only reject as themselves")
    return await crud.decide_leave_request(db, leave_id, decision, approved=False)
