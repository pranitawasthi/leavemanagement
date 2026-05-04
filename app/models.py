from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, Optional

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field


class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: Any) -> Any:
        from pydantic_core import core_schema

        return core_schema.no_info_plain_validator_function(cls.validate)

    @classmethod
    def validate(cls, value: Any) -> ObjectId:
        if isinstance(value, ObjectId):
            return value
        if isinstance(value, str) and ObjectId.is_valid(value):
            return ObjectId(value)
        raise ValueError("Invalid ObjectId")


class MongoModel(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )


class UserRole(str, Enum):
    employee = "Employee"
    manager = "Manager"
    admin = "Admin"


class LeaveType(str, Enum):
    sick = "Sick"
    casual = "Casual"
    wfh = "WFH"
    comp_off = "Comp-off"


class LeaveStatus(str, Enum):
    pending = "Pending"
    approved = "Approved"
    rejected = "Rejected"


class AttendanceStatus(str, Enum):
    checked_in = "Checked-in"
    checked_out = "Checked-out"


class AuditAction(str, Enum):
    created = "Created"
    approved = "Approved"
    rejected = "Rejected"
    updated = "Updated"


class User(MongoModel):
    employee_id: str
    name: str
    email: str
    password_hash: str
    role: UserRole = UserRole.employee
    department: str
    manager_id: Optional[PyObjectId] = None
    job_title: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class LeaveQuota(MongoModel):
    user_id: PyObjectId
    year: int
    leave_type: LeaveType
    total_days: float
    used_days: float = 0
    pending_days: float = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class LeaveRequest(MongoModel):
    user_id: PyObjectId
    manager_id: PyObjectId
    leave_type: LeaveType
    start_date: date
    end_date: date
    total_days: float
    is_half_day: bool = False
    reason: str
    status: LeaveStatus = LeaveStatus.pending
    manager_comment: Optional[str] = None
    ai_parsed_from_text: Optional[str] = None
    ai_insight: Optional[Dict[str, Any]] = None
    reviewed_by: Optional[PyObjectId] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AttendanceRecord(MongoModel):
    user_id: PyObjectId
    manager_id: Optional[PyObjectId] = None
    work_date: date
    entry_time: datetime
    exit_time: Optional[datetime] = None
    status: AttendanceStatus = AttendanceStatus.checked_in
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AuditTrail(MongoModel):
    entity_type: str
    entity_id: PyObjectId
    actor_id: PyObjectId
    action: AuditAction
    before: Optional[Dict[str, Any]] = None
    after: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
