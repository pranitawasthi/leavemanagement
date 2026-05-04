from typing import List

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app import crud
from app.database import get_database
from app.models import LeaveStatus
from app.schemas import LeaveDecision, LeaveRequestRead


router = APIRouter(prefix="/managers", tags=["managers"])


@router.get("/{manager_id}/leave-requests/pending", response_model=List[LeaveRequestRead])
async def list_pending_manager_leave_requests(
    manager_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> List[LeaveRequestRead]:
    return await crud.list_leave_requests(
        db,
        manager_id=manager_id,
        status_filter=LeaveStatus.pending,
    )


@router.get("/{manager_id}/leave-requests/history", response_model=List[LeaveRequestRead])
async def list_manager_leave_history(
    manager_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> List[LeaveRequestRead]:
    return await crud.list_leave_requests(db, manager_id=manager_id)


@router.patch("/leave-requests/{leave_id}/approve", response_model=LeaveRequestRead)
async def approve_leave_request(
    leave_id: str,
    decision: LeaveDecision,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> LeaveRequestRead:
    return await crud.decide_leave_request(db, leave_id, decision, approved=True)


@router.patch("/leave-requests/{leave_id}/reject", response_model=LeaveRequestRead)
async def reject_leave_request(
    leave_id: str,
    decision: LeaveDecision,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> LeaveRequestRead:
    return await crud.decide_leave_request(db, leave_id, decision, approved=False)
