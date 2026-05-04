from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.crud import serialize_document
from app.auth import get_current_user, require_roles
from app.database import get_database
from app.models import AttendanceStatus, UserRole
from app.schemas import AttendanceRecordRead


router = APIRouter(prefix="/attendance", tags=["attendance"])


def serialize_attendance(record: dict) -> dict:
    return serialize_document(record)


@router.post("/punch", response_model=AttendanceRecordRead)
async def punch_attendance(
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> AttendanceRecordRead:
    if current_user["role"] == UserRole.admin.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins do not punch attendance in this simulation",
        )

    today = date.today().isoformat()
    now = datetime.utcnow()
    query = {"user_id": current_user["_id"], "work_date": today}
    existing = await db.attendance_records.find_one(query)

    if not existing:
        document = {
            "user_id": current_user["_id"],
            "manager_id": current_user.get("manager_id"),
            "work_date": today,
            "entry_time": now,
            "exit_time": None,
            "status": AttendanceStatus.checked_in.value,
            "created_at": now,
            "updated_at": now,
        }
        result = await db.attendance_records.insert_one(document)
        document["_id"] = result.inserted_id
        return serialize_attendance(document)

    if existing.get("exit_time"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Attendance is already completed for today",
        )

    await db.attendance_records.update_one(
        {"_id": existing["_id"]},
        {
            "$set": {
                "exit_time": now,
                "status": AttendanceStatus.checked_out.value,
                "updated_at": now,
            }
        },
    )
    updated = await db.attendance_records.find_one({"_id": existing["_id"]})
    return serialize_attendance(updated)


@router.get("/me", response_model=List[AttendanceRecordRead])
async def list_my_attendance(
    work_date: Optional[date] = Query(default=None),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> List[AttendanceRecordRead]:
    query = {"user_id": current_user["_id"]}
    if work_date:
        query["work_date"] = work_date.isoformat()
    records = await db.attendance_records.find(query).sort("work_date", -1).to_list(length=60)
    return [serialize_attendance(record) for record in records]


@router.get("/team", response_model=List[AttendanceRecordRead])
async def list_team_attendance(
    work_date: Optional[date] = Query(default=None),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(require_roles(UserRole.manager, UserRole.admin)),
) -> List[AttendanceRecordRead]:
    query = {}
    if current_user["role"] == UserRole.manager.value:
        query["manager_id"] = current_user["_id"]
    if work_date:
        query["work_date"] = work_date.isoformat()

    records = await db.attendance_records.find(query).sort("entry_time", -1).to_list(length=300)
    return [serialize_attendance(record) for record in records]
