from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app import crud
from app.database import get_database
from app.schemas import (
    ApprovalInsight,
    ApprovalInsightRequest,
    LeaveRequestParseInput,
    ParsedLeaveRequest,
)


router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/parse-leave-request", response_model=ParsedLeaveRequest)
async def parse_leave_request(
    payload: LeaveRequestParseInput,
) -> ParsedLeaveRequest:
    return await crud.parse_leave_request_text(payload.text)


@router.post("/approval-insight/{leave_id}", response_model=ApprovalInsight)
async def generate_approval_insight(
    leave_id: str,
    payload: ApprovalInsightRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> ApprovalInsight:
    # manager_id is accepted now so this endpoint can be locked down when auth is added.
    _ = payload.manager_id
    return await crud.generate_approval_insight(db, leave_id)
