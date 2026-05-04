import asyncio
from datetime import date, datetime, timedelta
from typing import Any, Dict, List

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from app.auth import hash_password
from app.database import MONGODB_DB_NAME, MONGODB_URI
from app.models import AuditAction, LeaveStatus, LeaveType, UserRole
from app.utils.date_calculator import calculate_leave_days


CURRENT_MONTH_START = date(2026, 5, 1)
NEXT_MONTH_START = date(2026, 6, 1)


MANAGERS = [
    {
        "employee_id": "MGR-001",
        "name": "Aarav Mehta",
        "email": "aarav.mehta@company.com",
        "department": "Engineering",
        "job_title": "Engineering Manager",
    },
    {
        "employee_id": "MGR-002",
        "name": "Neha Kapoor",
        "email": "neha.kapoor@company.com", 
        "department": "Product",
        "job_title": "Product Manager",
    },
    {
        "employee_id": "MGR-003",
        "name": "Rohan Iyer",
        "email": "rohan.iyer@company.com",
        "department": "Operations",
        "job_title": "Operations Manager",
    },
]
 
MASTER_ADMIN = {
    "employee_id": "ADM-001",
    "name": "Maya Fernandes",
    "email": "admin@company.com",
    "department": "Administration",
    "job_title": "Master Admin",
}
 
DEMO_PASSWORDS = {
    UserRole.admin.value: "Admin@123",
    UserRole.manager.value: "Manager@123", 
    UserRole.employee.value: "Employee@123",
}


EMPLOYEES = [
    ("EMP-001", "Isha Sharma", "isha.sharma@company.com", "Engineering", "Frontend Engineer", 0),
    ("EMP-002", "Kabir Singh", "kabir.singh@company.com", "Engineering", "Backend Engineer", 0),
    ("EMP-003", "Meera Nair", "meera.nair@company.com", "Engineering", "QA Engineer", 0),
    ("EMP-004", "Dev Patel", "dev.patel@company.com", "Engineering", "DevOps Engineer", 0),
    ("EMP-005", "Ananya Rao", "ananya.rao@company.com", "Engineering", "Data Engineer", 0),
    ("EMP-006", "Vivaan Gupta", "vivaan.gupta@company.com", "Engineering", "Full Stack Engineer", 0),
    ("EMP-007", "Tara Menon", "tara.menon@company.com", "Engineering", "Mobile Engineer", 0),
    ("EMP-008", "Sahil Verma", "sahil.verma@company.com", "Product", "Product Analyst", 1),
    ("EMP-009", "Priya Kulkarni", "priya.kulkarni@company.com", "Product", "UX Designer", 1),
    ("EMP-010", "Nikhil Bansal", "nikhil.bansal@company.com", "Product", "Product Designer", 1),
    ("EMP-011", "Riya Chatterjee", "riya.chatterjee@company.com", "Product", "Business Analyst", 1),
    ("EMP-012", "Arjun Sethi", "arjun.sethi@company.com", "Product", "Technical Writer", 1),
    ("EMP-013", "Sneha Joshi", "sneha.joshi@company.com", "Product", "Customer Researcher", 1),
    ("EMP-014", "Karan Malhotra", "karan.malhotra@company.com", "Operations", "People Ops Specialist", 2),
    ("EMP-015", "Pooja Reddy", "pooja.reddy@company.com", "Operations", "Finance Associate", 2),
    ("EMP-016", "Aditya Das", "aditya.das@company.com", "Operations", "IT Support Engineer", 2),
    ("EMP-017", "Naina Bose", "naina.bose@company.com", "Operations", "Admin Coordinator", 2),
    ("EMP-018", "Manav Khanna", "manav.khanna@company.com", "Operations", "Recruiter", 2),
    ("EMP-019", "Leela Thomas", "leela.thomas@company.com", "Operations", "Payroll Specialist", 2),
    ("EMP-020", "Harsh Agarwal", "harsh.agarwal@company.com", "Operations", "Office Experience Lead", 2),
]


QUOTA_TEMPLATE = {
    LeaveType.sick: 10,
    LeaveType.casual: 12,
    LeaveType.wfh: 24,
    LeaveType.comp_off: 6,
} 


LEAVE_REQUEST_BLUEPRINTS = [
    (0, LeaveType.sick, date(2026, 5, 5), date(2026, 5, 5), "Down with fever and body ache.", LeaveStatus.approved, "Take care and update the team async."),
    (1, LeaveType.casual, date(2026, 5, 7), date(2026, 5, 8), "Family function out of town.", LeaveStatus.pending, None),
    (2, LeaveType.wfh, date(2026, 5, 11), date(2026, 5, 11), "Internet maintenance work at home requires presence.", LeaveStatus.approved, "Approved. Please stay available on Slack."),
    (3, LeaveType.comp_off, date(2026, 5, 12), date(2026, 5, 12), "Comp-off for weekend deployment support.", LeaveStatus.approved, "Thanks for the weekend release support."),
    (4, LeaveType.casual, date(2026, 5, 14), date(2026, 5, 15), "Personal travel plans.", LeaveStatus.rejected, "Two critical sprint reviews are planned for these dates."),
    (5, LeaveType.sick, date(2026, 5, 18), date(2026, 5, 19), "Doctor advised rest for throat infection.", LeaveStatus.pending, None),
    (6, LeaveType.wfh, date(2026, 5, 20), date(2026, 5, 20), "Need focused time for mobile release fixes.", LeaveStatus.approved, "Approved for focused work."),
    (7, LeaveType.casual, date(2026, 5, 6), date(2026, 5, 6), "Parent-teacher meeting at school.", LeaveStatus.approved, "Approved."),
    (8, LeaveType.wfh, date(2026, 5, 13), date(2026, 5, 13), "Waiting for appliance repair visit.", LeaveStatus.pending, None),
    (9, LeaveType.sick, date(2026, 5, 21), date(2026, 5, 21), "Migraine and rest day.", LeaveStatus.approved, "Approved. Hope you feel better."),
    (10, LeaveType.casual, date(2026, 5, 25), date(2026, 5, 26), "Attending cousin's wedding.", LeaveStatus.pending, None),
    (11, LeaveType.comp_off, date(2026, 5, 28), date(2026, 5, 28), "Comp-off against late-night customer webinar.", LeaveStatus.rejected, "Please use this after the launch handoff is complete."),
    (12, LeaveType.wfh, date(2026, 5, 29), date(2026, 5, 29), "Need to work remotely due to minor home renovation.", LeaveStatus.approved, "Approved."),
    (13, LeaveType.casual, date(2026, 5, 8), date(2026, 5, 8), "Bank appointment and document work.", LeaveStatus.approved, "Approved."),
    (14, LeaveType.sick, date(2026, 5, 15), date(2026, 5, 15), "Dental procedure appointment.", LeaveStatus.pending, None),
    (15, LeaveType.wfh, date(2026, 5, 22), date(2026, 5, 22), "Working from home due to commute disruption.", LeaveStatus.rejected, "Ops onboarding session needs in-office support."),
    (16, LeaveType.casual, date(2026, 5, 27), date(2026, 5, 27), "Personal errand and family commitment.", LeaveStatus.approved, "Approved."),
    (17, LeaveType.comp_off, date(2026, 5, 11), date(2026, 5, 11), "Comp-off for Saturday interview drive.", LeaveStatus.approved, "Approved. Thanks for helping with hiring."),
    (18, LeaveType.sick, date(2026, 5, 19), date(2026, 5, 20), "Medical tests and recovery time.", LeaveStatus.pending, None),
    (19, LeaveType.wfh, date(2026, 5, 26), date(2026, 5, 26), "Home internet provider visit during work hours.", LeaveStatus.approved, "Approved."),
    (0, LeaveType.casual, date(2026, 6, 2), date(2026, 6, 3), "Short trip with family.", LeaveStatus.pending, None),
    (1, LeaveType.wfh, date(2026, 6, 4), date(2026, 6, 4), "Need remote day for apartment inspection.", LeaveStatus.approved, "Approved."),
    (2, LeaveType.sick, date(2026, 6, 5), date(2026, 6, 5), "Follow-up medical consultation.", LeaveStatus.pending, None),
    (3, LeaveType.casual, date(2026, 6, 8), date(2026, 6, 9), "Friend's wedding travel.", LeaveStatus.approved, "Approved, please hand over deployment notes."),
    (4, LeaveType.wfh, date(2026, 6, 10), date(2026, 6, 10), "Working remotely after late evening travel.", LeaveStatus.rejected, "Client workshop requires in-person attendance."),
    (8, LeaveType.casual, date(2026, 6, 12), date(2026, 6, 12), "Family appointment.", LeaveStatus.pending, None),
    (9, LeaveType.comp_off, date(2026, 6, 15), date(2026, 6, 15), "Comp-off for design sprint weekend prep.", LeaveStatus.approved, "Approved."),
    (13, LeaveType.sick, date(2026, 6, 16), date(2026, 6, 17), "Viral infection recovery.", LeaveStatus.approved, "Approved. Rest well."),
    (15, LeaveType.casual, date(2026, 6, 18), date(2026, 6, 19), "Personal travel.", LeaveStatus.pending, None),
    (19, LeaveType.comp_off, date(2026, 6, 22), date(2026, 6, 22), "Comp-off for office move weekend support.", LeaveStatus.rejected, "Please coordinate a different date due to payroll closure."),
]


def now() -> datetime:
    return datetime.utcnow()


def build_manager_documents() -> List[Dict[str, Any]]:
    timestamp = now()
    return [
        {
            "_id": ObjectId(),
            "employee_id": manager["employee_id"],
            "name": manager["name"],
            "email": manager["email"],
            "password_hash": hash_password(DEMO_PASSWORDS[UserRole.manager.value]),
            "role": UserRole.manager.value,
            "department": manager["department"],
            "manager_id": None,
            "job_title": manager["job_title"],
            "is_active": True,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        for manager in MANAGERS
    ]


def build_admin_document() -> Dict[str, Any]:
    timestamp = now()
    return {
        "_id": ObjectId(),
        "employee_id": MASTER_ADMIN["employee_id"],
        "name": MASTER_ADMIN["name"],
        "email": MASTER_ADMIN["email"],
        "password_hash": hash_password(DEMO_PASSWORDS[UserRole.admin.value]),
        "role": UserRole.admin.value,
        "department": MASTER_ADMIN["department"],
        "manager_id": None,
        "job_title": MASTER_ADMIN["job_title"],
        "is_active": True,
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def build_employee_documents(manager_documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    timestamp = now()
    employees = []
    for employee_id, name, email, department, job_title, manager_index in EMPLOYEES:
        employees.append(
            {
                "_id": ObjectId(),
                "employee_id": employee_id,
                "name": name,
                "email": email,
                "password_hash": hash_password(DEMO_PASSWORDS[UserRole.employee.value]),
                "role": UserRole.employee.value,
                "department": department,
                "manager_id": manager_documents[manager_index]["_id"],
                "job_title": job_title,
                "is_active": True,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
        )
    return employees


def build_quota_documents(users: List[Dict[str, Any]], year: int) -> List[Dict[str, Any]]:
    timestamp = now()
    quotas = []
    for user in users:
        for leave_type, total_days in QUOTA_TEMPLATE.items():
            quotas.append(
                {
                    "_id": ObjectId(),
                    "user_id": user["_id"],
                    "year": year,
                    "leave_type": leave_type.value,
                    "total_days": float(total_days),
                    "used_days": 0.0,
                    "pending_days": 0.0,
                    "created_at": timestamp,
                    "updated_at": timestamp,
                }
            )
    return quotas


def review_timestamp(start_date: date) -> datetime:
    submitted_on = datetime.combine(start_date - timedelta(days=7), datetime.min.time())
    return submitted_on + timedelta(days=2, hours=10, minutes=30)


def build_leave_documents(
    employee_documents: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    leave_documents = []
    for index, leave_type, start_date, end_date, reason, status, manager_comment in LEAVE_REQUEST_BLUEPRINTS:
        employee = employee_documents[index]
        created_at = datetime.combine(start_date - timedelta(days=8), datetime.min.time()) + timedelta(hours=9)
        total_days = calculate_leave_days(start_date, end_date, include_weekends=leave_type == LeaveType.wfh)
        reviewed_at = review_timestamp(start_date) if status != LeaveStatus.pending else None
        reviewed_by = employee["manager_id"] if reviewed_at else None

        leave_documents.append(
            {
                "_id": ObjectId(),
                "user_id": employee["_id"],
                "manager_id": employee["manager_id"],
                "leave_type": leave_type.value,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "total_days": total_days,
                "is_half_day": False,
                "reason": reason,
                "status": status.value,
                "manager_comment": manager_comment,
                "ai_parsed_from_text": None,
                "ai_insight": {
                    "summary": f"{leave_type.value} request for {total_days:g} working day(s).",
                    "conflicts": [],
                    "risk_level": "low" if status != LeaveStatus.rejected else "medium",
                    "recommendation": "Approve" if status == LeaveStatus.approved else "Review manually",
                }
                if status != LeaveStatus.pending
                else None,
                "reviewed_by": reviewed_by,
                "reviewed_at": reviewed_at,
                "created_at": created_at,
                "updated_at": reviewed_at or created_at,
            }
        )
    return leave_documents


def build_audit_documents(leave_documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    audit_documents = []
    for leave in leave_documents:
        audit_documents.append(
            {
                "_id": ObjectId(),
                "entity_type": "leave_request",
                "entity_id": leave["_id"],
                "actor_id": leave["user_id"],
                "action": AuditAction.created.value,
                "before": None,
                "after": summarize_leave_for_audit(leave),
                "created_at": leave["created_at"],
            }
        )

        if leave["status"] == LeaveStatus.pending.value:
            continue

        before = summarize_leave_for_audit(leave)
        before["status"] = LeaveStatus.pending.value
        before["manager_comment"] = None
        before["reviewed_by"] = None
        before["reviewed_at"] = None

        audit_documents.append(
            {
                "_id": ObjectId(),
                "entity_type": "leave_request",
                "entity_id": leave["_id"],
                "actor_id": leave["manager_id"],
                "action": AuditAction.approved.value
                if leave["status"] == LeaveStatus.approved.value
                else AuditAction.rejected.value,
                "before": before,
                "after": summarize_leave_for_audit(leave),
                "created_at": leave["reviewed_at"],
            }
        )
    return audit_documents


def summarize_leave_for_audit(leave: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(leave["_id"]),
        "user_id": str(leave["user_id"]),
        "manager_id": str(leave["manager_id"]),
        "leave_type": leave["leave_type"],
        "start_date": leave["start_date"],
        "end_date": leave["end_date"],
        "total_days": leave["total_days"],
        "is_half_day": leave.get("is_half_day", False),
        "reason": leave["reason"],
        "status": leave["status"],
        "manager_comment": leave["manager_comment"],
        "reviewed_by": str(leave["reviewed_by"]) if leave["reviewed_by"] else None,
        "reviewed_at": leave["reviewed_at"].isoformat() if leave["reviewed_at"] else None,
    }


def apply_leave_usage_to_quotas(
    quota_documents: List[Dict[str, Any]],
    leave_documents: List[Dict[str, Any]],
) -> None:
    quota_lookup = {
        (quota["user_id"], quota["leave_type"], quota["year"]): quota
        for quota in quota_documents
    }

    for leave in leave_documents:
        leave_year = date.fromisoformat(leave["start_date"]).year
        quota = quota_lookup[(leave["user_id"], leave["leave_type"], leave_year)]

        if leave["status"] == LeaveStatus.pending.value:
            quota["pending_days"] += leave["total_days"]
        elif leave["status"] == LeaveStatus.approved.value and leave["leave_type"] != LeaveType.wfh.value:
            quota["used_days"] += leave["total_days"]

        quota["updated_at"] = now()


async def seed_database() -> None:
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[MONGODB_DB_NAME]

    try:
        await db.users.delete_many({})
        await db.leave_quotas.delete_many({})
        await db.leave_requests.delete_many({})
        await db.audit_trails.delete_many({})

        admin_document = build_admin_document()
        manager_documents = build_manager_documents()
        employee_documents = build_employee_documents(manager_documents)
        user_documents = [admin_document] + manager_documents + employee_documents

        quota_documents = build_quota_documents(user_documents, year=CURRENT_MONTH_START.year)
        leave_documents = build_leave_documents(employee_documents)
        apply_leave_usage_to_quotas(quota_documents, leave_documents)
        audit_documents = build_audit_documents(leave_documents)

        await db.users.insert_many(user_documents)
        await db.leave_quotas.insert_many(quota_documents)
        await db.leave_requests.insert_many(leave_documents)
        await db.audit_trails.insert_many(audit_documents)

        print("Seed completed successfully.")
        print(f"Users inserted: {len(user_documents)}")
        print("Demo credentials:")
        print(f"  Admin:    {MASTER_ADMIN['email']} / {DEMO_PASSWORDS[UserRole.admin.value]}")
        print(f"  Manager:  {MANAGERS[0]['email']} / {DEMO_PASSWORDS[UserRole.manager.value]}")
        print(f"  Employee: {EMPLOYEES[0][2]} / {DEMO_PASSWORDS[UserRole.employee.value]}")
        print(f"Managers inserted: {len(manager_documents)}")
        print(f"Employees inserted: {len(employee_documents)}")
        print(f"Leave quotas inserted: {len(quota_documents)}")
        print(f"Leave requests inserted: {len(leave_documents)}")
        print(f"Audit trails inserted: {len(audit_documents)}")
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(seed_database())
