from datetime import date, datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models import AuditAction, LeaveStatus, LeaveType, UserRole
from app.schemas import (
    ApprovalInsight,
    LeaveDecision,
    LeaveQuotaCreate,
    LeaveRequestCreate,
    LeaveRequestUpdate,
    ParsedLeaveRequest,
    UserCreate,
    UserUpdate,
)
from app.utils.date_calculator import calculate_leave_days


def to_object_id(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid ObjectId: {value}",
        )
    return ObjectId(value)


def serialize_document(document: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if document is None:
        return None

    serialized = dict(document)
    if "_id" in serialized:
        serialized["id"] = str(serialized.pop("_id"))

    for key, value in list(serialized.items()):
        if isinstance(value, ObjectId):
            serialized[key] = str(value)
        elif isinstance(value, dict):
            serialized[key] = serialize_document(value)
        elif isinstance(value, list):
            serialized[key] = [
                serialize_document(item) if isinstance(item, dict) else str(item) if isinstance(item, ObjectId) else item
                for item in value
            ]

    return serialized


def parse_stored_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(value).date()


async def create_audit_trail(
    db: AsyncIOMotorDatabase,
    entity_type: str,
    entity_id: ObjectId,
    actor_id: ObjectId,
    action: AuditAction,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    audit_document = {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "actor_id": actor_id,
        "action": action.value,
        "before": before,
        "after": after,
        "created_at": datetime.utcnow(),
    }
    result = await db.audit_trails.insert_one(audit_document)
    audit_document["_id"] = result.inserted_id
    return serialize_document(audit_document)


async def create_user(db: AsyncIOMotorDatabase, user: UserCreate) -> Dict[str, Any]:
    user_document = user.model_dump()
    user_document["manager_id"] = to_object_id(user.manager_id) if user.manager_id else None
    user_document["role"] = user.role.value
    user_document["created_at"] = datetime.utcnow()
    user_document["updated_at"] = datetime.utcnow()

    result = await db.users.insert_one(user_document)
    user_document["_id"] = result.inserted_id
    return serialize_document(user_document)


async def get_user(db: AsyncIOMotorDatabase, user_id: str) -> Dict[str, Any]:
    user = await db.users.find_one({"_id": to_object_id(user_id)})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return serialize_document(user)


async def list_users(
    db: AsyncIOMotorDatabase,
    role: Optional[UserRole] = None,
    manager_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {}
    if role:
        query["role"] = role.value
    if manager_id:
        query["manager_id"] = to_object_id(manager_id)

    users = await db.users.find(query).sort("name", 1).to_list(length=200)
    return [serialize_document(user) for user in users]


async def update_user(db: AsyncIOMotorDatabase, user_id: str, user: UserUpdate) -> Dict[str, Any]:
    update_data = user.model_dump(exclude_unset=True)
    if "manager_id" in update_data:
        update_data["manager_id"] = to_object_id(update_data["manager_id"]) if update_data["manager_id"] else None
    if "role" in update_data and update_data["role"]:
        update_data["role"] = update_data["role"].value
    update_data["updated_at"] = datetime.utcnow()

    await db.users.update_one({"_id": to_object_id(user_id)}, {"$set": update_data})
    return await get_user(db, user_id)


async def create_leave_quota(db: AsyncIOMotorDatabase, quota: LeaveQuotaCreate) -> Dict[str, Any]:
    quota_document = quota.model_dump()
    quota_document["user_id"] = to_object_id(quota.user_id)
    quota_document["leave_type"] = quota.leave_type.value
    quota_document["created_at"] = datetime.utcnow()
    quota_document["updated_at"] = datetime.utcnow()

    result = await db.leave_quotas.insert_one(quota_document)
    quota_document["_id"] = result.inserted_id
    serialized = serialize_document(quota_document)
    serialized["remaining_days"] = quota.total_days - quota.used_days - quota.pending_days
    return serialized


async def get_user_leave_quotas(db: AsyncIOMotorDatabase, user_id: str, year: Optional[int] = None) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {"user_id": to_object_id(user_id)}
    if year:
        query["year"] = year

    quotas = await db.leave_quotas.find(query).sort("leave_type", 1).to_list(length=20)
    serialized_quotas = []
    for quota in quotas:
        serialized = serialize_document(quota)
        serialized["remaining_days"] = quota["total_days"] - quota["used_days"] - quota["pending_days"]
        serialized_quotas.append(serialized)
    return serialized_quotas


async def get_matching_quota(
    db: AsyncIOMotorDatabase,
    user_id: ObjectId,
    leave_type: LeaveType,
    year: int,
) -> Dict[str, Any]:
    quota = await db.leave_quotas.find_one(
        {"user_id": user_id, "leave_type": leave_type.value, "year": year}
    )
    if not quota:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Leave quota does not exist for this user, year, and leave type",
        )
    return quota


async def create_leave_request(db: AsyncIOMotorDatabase, leave: LeaveRequestCreate) -> Dict[str, Any]:
    user_id = to_object_id(leave.user_id)
    user = await db.users.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not user.get("manager_id"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User does not have a manager")

    total_days = calculate_leave_days(leave.start_date, leave.end_date)
    if total_days <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Leave request must include at least one working day",
        )

    quota = await get_matching_quota(db, user_id, leave.leave_type, leave.start_date.year)
    remaining_days = quota["total_days"] - quota["used_days"] - quota["pending_days"]
    if leave.leave_type != LeaveType.wfh and total_days > remaining_days:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient leave balance")

    now = datetime.utcnow()
    leave_document = {
        "user_id": user_id,
        "manager_id": user["manager_id"],
        "leave_type": leave.leave_type.value,
        "start_date": leave.start_date.isoformat(),
        "end_date": leave.end_date.isoformat(),
        "total_days": total_days,
        "reason": leave.reason,
        "status": LeaveStatus.pending.value,
        "manager_comment": None,
        "ai_parsed_from_text": leave.ai_parsed_from_text,
        "ai_insight": None,
        "reviewed_by": None,
        "reviewed_at": None,
        "created_at": now,
        "updated_at": now,
    }

    result = await db.leave_requests.insert_one(leave_document)
    leave_document["_id"] = result.inserted_id

    await db.leave_quotas.update_one(
        {"_id": quota["_id"]},
        {"$inc": {"pending_days": total_days}, "$set": {"updated_at": now}},
    )
    await create_audit_trail(
        db,
        "leave_request",
        result.inserted_id,
        user_id,
        AuditAction.created,
        after=serialize_document(leave_document),
    )

    return serialize_document(leave_document)


async def list_leave_requests(
    db: AsyncIOMotorDatabase,
    user_id: Optional[str] = None,
    manager_id: Optional[str] = None,
    status_filter: Optional[LeaveStatus] = None,
) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {}
    if user_id:
        query["user_id"] = to_object_id(user_id)
    if manager_id:
        query["manager_id"] = to_object_id(manager_id)
    if status_filter:
        query["status"] = status_filter.value

    leaves = await db.leave_requests.find(query).sort("created_at", -1).to_list(length=200)
    return [serialize_document(leave) for leave in leaves]


async def get_leave_request(db: AsyncIOMotorDatabase, leave_id: str) -> Dict[str, Any]:
    leave = await db.leave_requests.find_one({"_id": to_object_id(leave_id)})
    if not leave:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")
    return serialize_document(leave)


async def update_leave_request(
    db: AsyncIOMotorDatabase,
    leave_id: str,
    update: LeaveRequestUpdate,
) -> Dict[str, Any]:
    existing = await db.leave_requests.find_one({"_id": to_object_id(leave_id)})
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")
    if existing["status"] != LeaveStatus.pending.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending requests can be edited")

    update_data = update.model_dump(exclude_unset=True)
    if "leave_type" in update_data and update_data["leave_type"]:
        update_data["leave_type"] = update_data["leave_type"].value

    old_total_days = existing["total_days"]
    new_leave_type = LeaveType(update_data.get("leave_type", existing["leave_type"]))
    new_start_date = parse_stored_date(update_data.get("start_date", existing["start_date"]))
    new_end_date = parse_stored_date(update_data.get("end_date", existing["end_date"]))
    new_total_days = calculate_leave_days(new_start_date, new_end_date)

    if "start_date" in update_data and update_data["start_date"]:
        update_data["start_date"] = update_data["start_date"].isoformat()
    if "end_date" in update_data and update_data["end_date"]:
        update_data["end_date"] = update_data["end_date"].isoformat()
    update_data["total_days"] = new_total_days
    update_data["updated_at"] = datetime.utcnow()

    await db.leave_requests.update_one({"_id": existing["_id"]}, {"$set": update_data})

    old_quota = await get_matching_quota(
        db,
        existing["user_id"],
        LeaveType(existing["leave_type"]),
        parse_stored_date(existing["start_date"]).year,
    )
    await db.leave_quotas.update_one(
        {"_id": old_quota["_id"]},
        {"$inc": {"pending_days": -old_total_days}, "$set": {"updated_at": datetime.utcnow()}},
    )

    new_quota = await get_matching_quota(db, existing["user_id"], new_leave_type, new_start_date.year)
    await db.leave_quotas.update_one(
        {"_id": new_quota["_id"]},
        {"$inc": {"pending_days": new_total_days}, "$set": {"updated_at": datetime.utcnow()}},
    )

    updated = await get_leave_request(db, leave_id)
    await create_audit_trail(
        db,
        "leave_request",
        existing["_id"],
        existing["user_id"],
        AuditAction.updated,
        before=serialize_document(existing),
        after=updated,
    )
    return updated


async def decide_leave_request(
    db: AsyncIOMotorDatabase,
    leave_id: str,
    decision: LeaveDecision,
    approved: bool,
) -> Dict[str, Any]:
    leave_object_id = to_object_id(leave_id)
    manager_object_id = to_object_id(decision.manager_id)

    leave = await db.leave_requests.find_one({"_id": leave_object_id})
    if not leave:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")
    if leave["status"] != LeaveStatus.pending.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Leave request is already decided")
    if leave["manager_id"] != manager_object_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Manager cannot decide this request")

    quota = await get_matching_quota(
        db,
        leave["user_id"],
        LeaveType(leave["leave_type"]),
        parse_stored_date(leave["start_date"]).year,
    )
    now = datetime.utcnow()
    new_status = LeaveStatus.approved if approved else LeaveStatus.rejected

    quota_increment = {"pending_days": -leave["total_days"]}
    if approved and leave["leave_type"] != LeaveType.wfh.value:
        quota_increment["used_days"] = leave["total_days"]

    await db.leave_quotas.update_one(
        {"_id": quota["_id"]},
        {"$inc": quota_increment, "$set": {"updated_at": now}},
    )

    await db.leave_requests.update_one(
        {"_id": leave_object_id},
        {
            "$set": {
                "status": new_status.value,
                "manager_comment": decision.manager_comment,
                "reviewed_by": manager_object_id,
                "reviewed_at": now,
                "updated_at": now,
            }
        },
    )

    updated = await get_leave_request(db, leave_id)
    await create_audit_trail(
        db,
        "leave_request",
        leave_object_id,
        manager_object_id,
        AuditAction.approved if approved else AuditAction.rejected,
        before=serialize_document(leave),
        after=updated,
    )
    return updated


async def parse_leave_request_text(text: str) -> ParsedLeaveRequest:
    lowered = text.lower()
    leave_type: Optional[LeaveType] = None

    if "sick" in lowered or "fever" in lowered or "medical" in lowered:
        leave_type = LeaveType.sick
    elif "wfh" in lowered or "work from home" in lowered or "remote" in lowered:
        leave_type = LeaveType.wfh
    elif "comp" in lowered or "comp-off" in lowered or "comp off" in lowered:
        leave_type = LeaveType.comp_off
    elif "casual" in lowered or "personal" in lowered:
        leave_type = LeaveType.casual

    missing_fields = []
    if not leave_type:
        missing_fields.append("leave_type")

    return ParsedLeaveRequest(
        leave_type=leave_type,
        start_date=None,
        end_date=None,
        reason=text,
        confidence=0.45 if leave_type else 0.2,
        missing_fields=missing_fields + ["start_date", "end_date"],
    )


async def generate_approval_insight(db: AsyncIOMotorDatabase, leave_id: str) -> ApprovalInsight:
    leave = await db.leave_requests.find_one({"_id": to_object_id(leave_id)})
    if not leave:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")

    quota = await get_matching_quota(
        db,
        leave["user_id"],
        LeaveType(leave["leave_type"]),
        parse_stored_date(leave["start_date"]).year,
    )
    overlapping_team_leaves = await db.leave_requests.find(
        {
            "manager_id": leave["manager_id"],
            "_id": {"$ne": leave["_id"]},
            "status": {"$in": [LeaveStatus.pending.value, LeaveStatus.approved.value]},
            "start_date": {"$lte": leave["end_date"]},
            "end_date": {"$gte": leave["start_date"]},
        }
    ).to_list(length=50)

    remaining_after_approval = quota["total_days"] - quota["used_days"] - leave["total_days"]
    conflicts = []
    if overlapping_team_leaves:
        conflicts.append(f"{len(overlapping_team_leaves)} team leave request(s) overlap this period.")
    if leave["leave_type"] != LeaveType.wfh.value and remaining_after_approval < 0:
        conflicts.append("Employee does not have enough quota for this request.")

    risk_level = "low"
    if len(conflicts) >= 2:
        risk_level = "high"
    elif conflicts:
        risk_level = "medium"

    recommendation = "Approve" if risk_level == "low" else "Review coverage before approving"
    insight = ApprovalInsight(
        summary=f"{leave['leave_type']} request for {leave['total_days']} working day(s).",
        conflicts=conflicts,
        risk_level=risk_level,
        recommendation=recommendation,
    )

    await db.leave_requests.update_one(
        {"_id": leave["_id"]},
        {"$set": {"ai_insight": insight.model_dump(), "updated_at": datetime.utcnow()}},
    )
    return insight
