import asyncio
import json
import logging
import os
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.auth import get_current_user, require_roles
from app.crud import parse_stored_date, to_object_id
from app.database import get_database
from app.models import LeaveStatus, LeaveType, UserRole
from app.utils.date_calculator import calculate_leave_days

  
router = APIRouter(prefix="/ai", tags=["ai"])
logger = logging.getLogger(__name__)

GROQ_API_URL = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_TIMEOUT_SECONDS = int(os.getenv("GROQ_TIMEOUT_SECONDS", "20"))
 
SUPPORTED_LEAVE_TYPES = [leave_type.value for leave_type in LeaveType] 


class LeaveParserRequest(BaseModel):
    text: str = Field(min_length=5, max_length=1000)
    today: Optional[date] = None


class LeaveParserResponse(BaseModel):
    leave_type: Optional[LeaveType] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    reason: str
    working_days: float
    confidence: float = Field(ge=0, le=1)
    missing_fields: List[str] = Field(default_factory=list)
    source: str


class ApprovalInsightRequest(BaseModel):
    manager_id: str


class ApprovalInsightResponse(BaseModel):
    short_manager_summary: str
    possible_team_conflict: str
    leave_balance_impact: str
    approval_recommendation: str
    risk_level: str
    source: str


def extract_json_object(raw_text: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
    if not match:
        raise ValueError("AI response did not contain a JSON object")

    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("AI response JSON was not an object")
    return parsed


def normalize_leave_type(value: Optional[str]) -> Optional[LeaveType]:
    if not value:
        return None

    normalized = value.strip().lower().replace("_", "-")
    mapping = {
        "sick": LeaveType.sick,
        "sick leave": LeaveType.sick,
        "casual": LeaveType.casual,
        "casual leave": LeaveType.casual,
        "wfh": LeaveType.wfh,
        "work from home": LeaveType.wfh,
        "remote": LeaveType.wfh,
        "comp-off": LeaveType.comp_off,
        "comp off": LeaveType.comp_off,
        "compoff": LeaveType.comp_off,
    }
    return mapping.get(normalized)


def parse_optional_date(value: Any) -> Optional[date]:
    if not value:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            return None
    return None


def calculate_response_working_days(start_date: Optional[date], end_date: Optional[date]) -> float:
    if not start_date or not end_date:
        return 0.0
    try:
        return calculate_leave_days(start_date, end_date)
    except ValueError:
        return 0.0


async def call_groq_json(system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured")

    payload = {
        "model": GROQ_MODEL,
        "temperature": 0,
        "top_p": 1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    request = Request(
        GROQ_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "leave-management-app/0.1 Python urllib",
        },
        method="POST",
    )

    def execute_request() -> Dict[str, Any]:
        with urlopen(request, timeout=GROQ_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))

    try:
        response_payload = await asyncio.to_thread(execute_request)
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Groq API HTTP {exc.code}: {error_body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Groq API network error: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError("Groq API request timed out") from exc

    try:
        content = response_payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Groq API response did not include assistant content") from exc

    return extract_json_object(content)


def fallback_parse_leave_request(text: str, today: date) -> LeaveParserResponse:
    lowered = text.lower()
    leave_type = normalize_leave_type(text)

    if not leave_type:
        if any(term in lowered for term in ["fever", "sick", "doctor", "medical", "migraine"]):
            leave_type = LeaveType.sick
        elif any(term in lowered for term in ["wfh", "work from home", "remote"]):
            leave_type = LeaveType.wfh
        elif any(term in lowered for term in ["comp-off", "comp off", "compensatory"]):
            leave_type = LeaveType.comp_off
        elif any(term in lowered for term in ["family", "function", "personal", "wedding"]):
            leave_type = LeaveType.casual

    start_date = None
    end_date = None
    if "next monday" in lowered:
        days_until_monday = (7 - today.weekday()) % 7
        days_until_monday = 7 if days_until_monday == 0 else days_until_monday
        start_date = today + timedelta(days=days_until_monday)
        end_date = start_date
        if "tuesday" in lowered:
            end_date = start_date + timedelta(days=1)
    elif "tomorrow" in lowered:
        start_date = today + timedelta(days=1)
        end_date = start_date

    missing_fields = []
    if not leave_type:
        missing_fields.append("leave_type")
    if not start_date:
        missing_fields.append("start_date")
    if not end_date:
        missing_fields.append("end_date")

    return LeaveParserResponse(
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        reason=text,
        working_days=calculate_response_working_days(start_date, end_date),
        confidence=0.55 if not missing_fields else 0.3,
        missing_fields=missing_fields,
        source="fallback",
    )


def build_parser_system_prompt() -> str:
    return (
        "You parse employee leave requests into strict JSON. "
        "Return only a JSON object. Do not include markdown. "
        "Allowed leave_type values are: Sick, Casual, WFH, Comp-off. "
        "Use ISO date format YYYY-MM-DD. "
        "If a value is unknown, return null. "
        "Infer Casual for personal events, family functions, weddings, travel, or errands. "
        "Infer Sick for illness or medical issues. "
        "Infer WFH for remote or work-from-home requests. "
        "Infer Comp-off only when compensatory time off is mentioned."
    )


def build_parser_user_prompt(text: str, today: date) -> str:
    return json.dumps(
        {
            "today": today.isoformat(),
            "timezone": "Asia/Kolkata",
            "employee_text": text,
            "required_json_shape": {
                "leave_type": "Sick | Casual | WFH | Comp-off | null",
                "start_date": "YYYY-MM-DD | null",
                "end_date": "YYYY-MM-DD | null",
                "reason": "short normalized human reason",
                "confidence": "number from 0 to 1",
            },
        }
    )


def normalize_parser_response(ai_json: Dict[str, Any], original_text: str) -> LeaveParserResponse:
    leave_type = normalize_leave_type(ai_json.get("leave_type"))
    start_date = parse_optional_date(ai_json.get("start_date"))
    end_date = parse_optional_date(ai_json.get("end_date"))
    if start_date and end_date and end_date < start_date:
        start_date, end_date = end_date, start_date

    missing_fields = []
    if not leave_type:
        missing_fields.append("leave_type")
    if not start_date:
        missing_fields.append("start_date")
    if not end_date:
        missing_fields.append("end_date")

    confidence = ai_json.get("confidence", 0.75)
    if not isinstance(confidence, (int, float)):
        confidence = 0.75

    return LeaveParserResponse(
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        reason=str(ai_json.get("reason") or original_text),
        working_days=calculate_response_working_days(start_date, end_date),
        confidence=max(0.0, min(float(confidence), 1.0)),
        missing_fields=missing_fields,
        source="groq",
    )


def object_id_to_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def serialize_leave_for_prompt(leave: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": object_id_to_str(leave.get("_id")),
        "user_id": object_id_to_str(leave.get("user_id")),
        "manager_id": object_id_to_str(leave.get("manager_id")),
        "leave_type": leave.get("leave_type"),
        "start_date": leave.get("start_date"),
        "end_date": leave.get("end_date"),
        "total_days": leave.get("total_days"),
        "reason": leave.get("reason"),
        "status": leave.get("status"),
    }


def serialize_quota_for_prompt(quota: Dict[str, Any]) -> Dict[str, Any]:
    remaining_days = quota["total_days"] - quota["used_days"] - quota["pending_days"]
    return {
        "leave_type": quota["leave_type"],
        "total_days": quota["total_days"],
        "used_days": quota["used_days"],
        "pending_days": quota["pending_days"],
        "remaining_days": remaining_days,
    }


async def get_approval_context(
    db: AsyncIOMotorDatabase,
    leave_id: str,
    manager_id: str,
) -> Dict[str, Any]:
    leave_object_id = to_object_id(leave_id)
    manager_object_id = to_object_id(manager_id)
    leave = await db.leave_requests.find_one({"_id": leave_object_id})
    if not leave:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")
    if leave["manager_id"] != manager_object_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager cannot generate insight for this leave request",
        )

    employee = await db.users.find_one({"_id": leave["user_id"]})
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    request_start = parse_stored_date(leave["start_date"])
    request_end = parse_stored_date(leave["end_date"])
    quotas = await db.leave_quotas.find(
        {"user_id": leave["user_id"], "year": request_start.year}
    ).to_list(length=20)
    overlapping_leaves = await db.leave_requests.find(
        {
            "_id": {"$ne": leave["_id"]},
            "manager_id": leave["manager_id"],
            "status": {"$in": [LeaveStatus.pending.value, LeaveStatus.approved.value]},
            "start_date": {"$lte": request_end.isoformat()},
            "end_date": {"$gte": request_start.isoformat()},
        }
    ).to_list(length=50)

    teammate_ids = list({item["user_id"] for item in overlapping_leaves})
    teammate_lookup = {}
    if teammate_ids:
        teammates = await db.users.find({"_id": {"$in": teammate_ids}}).to_list(length=50)
        teammate_lookup = {teammate["_id"]: teammate for teammate in teammates}

    overlaps = []
    for overlap in overlapping_leaves:
        teammate = teammate_lookup.get(overlap["user_id"], {})
        overlaps.append(
            {
                **serialize_leave_for_prompt(overlap),
                "employee_name": teammate.get("name", "Unknown employee"),
                "department": teammate.get("department"),
            }
        )

    return {
        "leave": leave,
        "employee": employee,
        "quotas": quotas,
        "overlaps": overlaps,
    }


def build_approval_system_prompt() -> str:
    return (
        "You help managers review leave requests. "
        "Return only strict JSON. Do not include markdown. "
        "Be concise, deterministic, and advisory. "
        "Do not invent company policy. Base the answer only on the provided request, balances, and overlaps. "
        "approval_recommendation must be one of: Approve, Reject, Review manually."
    )


def build_approval_user_prompt(context: Dict[str, Any]) -> str:
    leave = context["leave"]
    employee = context["employee"]
    quotas = [serialize_quota_for_prompt(quota) for quota in context["quotas"]]

    return json.dumps(
        {
            "employee": {
                "id": object_id_to_str(employee["_id"]),
                "name": employee["name"],
                "department": employee["department"],
                "job_title": employee.get("job_title"),
            },
            "leave_request": serialize_leave_for_prompt(leave),
            "employee_leave_balances": quotas,
            "same_date_team_leaves": context["overlaps"],
            "required_json_shape": {
                "short_manager_summary": "one short sentence",
                "possible_team_conflict": "one short sentence",
                "leave_balance_impact": "one short sentence",
                "approval_recommendation": "Approve | Reject | Review manually",
                "risk_level": "low | medium | high",
            },
        }
    )


def fallback_approval_insight(context: Dict[str, Any]) -> ApprovalInsightResponse:
    leave = context["leave"]
    employee = context["employee"]
    overlaps = context["overlaps"]
    matching_quota = next(
        (quota for quota in context["quotas"] if quota["leave_type"] == leave["leave_type"]),
        None,
    )

    balance_impact = "No matching quota was found for this leave type."
    balance_ok = True
    if matching_quota:
        remaining = matching_quota["total_days"] - matching_quota["used_days"] - matching_quota["pending_days"]
        after_approval = remaining - leave["total_days"]
        balance_ok = leave["leave_type"] == LeaveType.wfh.value or after_approval >= 0
        balance_impact = (
            f"{leave['leave_type']} balance would move from {remaining:g} to {after_approval:g} day(s)."
        )

    has_conflict = len(overlaps) > 0
    risk_level = "low"
    recommendation = "Approve"
    if has_conflict and not balance_ok:
        risk_level = "high"
        recommendation = "Review manually"
    elif has_conflict or not balance_ok:
        risk_level = "medium"
        recommendation = "Review manually"

    conflict_text = "No team leave overlap found for these dates."
    if has_conflict:
        names = ", ".join(overlap["employee_name"] for overlap in overlaps[:3])
        conflict_text = f"{len(overlaps)} overlapping team leave request(s): {names}."

    return ApprovalInsightResponse(
        short_manager_summary=(
            f"{employee['name']} requested {leave['leave_type']} for {leave['total_days']:g} working day(s)."
        ),
        possible_team_conflict=conflict_text,
        leave_balance_impact=balance_impact,
        approval_recommendation=recommendation,
        risk_level=risk_level,
        source="fallback",
    )


def normalize_approval_response(ai_json: Dict[str, Any]) -> ApprovalInsightResponse:
    recommendation = str(ai_json.get("approval_recommendation") or "Review manually")
    if recommendation not in {"Approve", "Reject", "Review manually"}:
        recommendation = "Review manually"

    risk_level = str(ai_json.get("risk_level") or "medium").lower()
    if risk_level not in {"low", "medium", "high"}:
        risk_level = "medium"

    return ApprovalInsightResponse(
        short_manager_summary=str(ai_json.get("short_manager_summary") or "Review requested leave details."),
        possible_team_conflict=str(ai_json.get("possible_team_conflict") or "No conflict information available."),
        leave_balance_impact=str(ai_json.get("leave_balance_impact") or "Balance impact could not be determined."),
        approval_recommendation=recommendation,
        risk_level=risk_level,
        source="groq",
    )


async def save_ai_insight(
    db: AsyncIOMotorDatabase,
    leave_id: str,
    insight: ApprovalInsightResponse,
) -> None:
    await db.leave_requests.update_one(
        {"_id": to_object_id(leave_id)},
        {
            "$set": {
                "ai_insight": insight.model_dump(),
                "updated_at": datetime.utcnow(),
            }
        },
    )


@router.post("/parse-leave-request", response_model=LeaveParserResponse)
async def parse_leave_request(
    payload: LeaveParserRequest,
    current_user: dict = Depends(get_current_user),
) -> LeaveParserResponse:
    _ = current_user
    today = payload.today or date.today()

    try:
        ai_json = await call_groq_json(
            system_prompt=build_parser_system_prompt(),
            user_prompt=build_parser_user_prompt(payload.text, today),
        )
        return normalize_parser_response(ai_json, payload.text)
    except Exception as exc:
        logger.warning("Groq leave parser failed; using fallback parser: %s", exc)
        parsed = fallback_parse_leave_request(payload.text, today)
        parsed.source = f"fallback ({type(exc).__name__})"
        return parsed


@router.post("/approval-insight/{leave_id}", response_model=ApprovalInsightResponse)
async def generate_approval_insight(
    leave_id: str,
    payload: ApprovalInsightRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(require_roles(UserRole.manager, UserRole.admin)),
) -> ApprovalInsightResponse:
    if current_user["role"] == UserRole.manager.value and payload.manager_id != str(current_user["_id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Managers can only generate their own insights")
    context = await get_approval_context(db, leave_id, payload.manager_id)

    try:
        ai_json = await call_groq_json(
            system_prompt=build_approval_system_prompt(),
            user_prompt=build_approval_user_prompt(context),
        )
        insight = normalize_approval_response(ai_json)
    except Exception:
        insight = fallback_approval_insight(context)

    await save_ai_insight(db, leave_id, insight)
    return insight


