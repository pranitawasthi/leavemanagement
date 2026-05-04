from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import AttendanceStatus, AuditAction, LeaveStatus, LeaveType, UserRole


class APIMessage(BaseModel):
    message: str


class UserBase(BaseModel):
    employee_id: str
    name: str
    email: EmailStr
    role: UserRole = UserRole.employee
    department: str
    manager_id: Optional[str] = None
    job_title: Optional[str] = None
    is_active: bool = True


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    department: Optional[str] = None
    manager_id: Optional[str] = None
    job_title: Optional[str] = None
    is_active: Optional[bool] = None


class UserRead(UserBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class LeaveQuotaBase(BaseModel):
    user_id: str
    year: int
    leave_type: LeaveType
    total_days: float = Field(ge=0)
    used_days: float = Field(default=0, ge=0)
    pending_days: float = Field(default=0, ge=0)


class LeaveQuotaCreate(LeaveQuotaBase):
    pass


class LeaveQuotaRead(LeaveQuotaBase):
    id: str
    remaining_days: float
    created_at: datetime
    updated_at: datetime


class LeaveRequestBase(BaseModel):
    leave_type: LeaveType
    start_date: date
    end_date: date
    is_half_day: bool = False
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("end_date")
    @classmethod
    def end_date_must_not_precede_start_date(cls, value: date, info: Any) -> date:
        start_date = info.data.get("start_date")
        if start_date and value < start_date:
            raise ValueError("end_date cannot be before start_date")
        return value

    @field_validator("is_half_day")
    @classmethod
    def half_day_must_be_single_date(cls, value: bool, info: Any) -> bool:
        start_date = info.data.get("start_date")
        end_date = info.data.get("end_date")
        if value and start_date and end_date and start_date != end_date:
            raise ValueError("Half-day leave must start and end on the same date")
        return value


class LeaveRequestCreate(LeaveRequestBase):
    user_id: str
    manager_id: Optional[str] = None
    ai_parsed_from_text: Optional[str] = None


class LeaveRequestUpdate(BaseModel):
    leave_type: Optional[LeaveType] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_half_day: Optional[bool] = None
    reason: Optional[str] = Field(default=None, min_length=3, max_length=500)


class LeaveDecision(BaseModel):
    manager_id: str
    manager_comment: Optional[str] = Field(default=None, max_length=500)


class LeaveRequestRead(BaseModel):
    id: str
    user_id: str
    manager_id: str
    leave_type: LeaveType
    start_date: date
    end_date: date
    total_days: float
    is_half_day: bool = False
    reason: str
    status: LeaveStatus
    manager_comment: Optional[str] = None
    ai_parsed_from_text: Optional[str] = None
    ai_insight: Optional[Dict[str, Any]] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class AttendanceRecordRead(BaseModel):
    id: str
    user_id: str
    manager_id: Optional[str] = None
    work_date: date
    entry_time: datetime
    exit_time: Optional[datetime] = None
    status: AttendanceStatus
    created_at: datetime
    updated_at: datetime


class AuditTrailRead(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    actor_id: str
    action: AuditAction
    before: Optional[Dict[str, Any]] = None
    after: Optional[Dict[str, Any]] = None
    created_at: datetime


class LeaveRequestParseInput(BaseModel):
    text: str = Field(min_length=5, max_length=1000)


class ParsedLeaveRequest(BaseModel):
    leave_type: Optional[LeaveType] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    reason: Optional[str] = None
    confidence: float = Field(ge=0, le=1)
    missing_fields: List[str] = Field(default_factory=list)


class ApprovalInsightRequest(BaseModel):
    manager_id: str


class ApprovalInsight(BaseModel):
    summary: str
    conflicts: List[str]
    risk_level: str
    recommendation: str
