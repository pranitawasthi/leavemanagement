import argparse
import json
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "http://127.0.0.1:8000"


class E2EFailure(AssertionError):
    pass 


@dataclass
class TestResult:
    name: str
    elapsed_ms: int


class APIClient:
    def __init__(self, base_url: str, timeout_seconds: int = 10) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.access_token: Optional[str] = None

    def set_token(self, access_token: Optional[str]) -> None:
        self.access_token = access_token

    def request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        query: Optional[Dict[str, Any]] = None,
        expected_status: int = 200,
    ) -> Any:
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"

        body = None
        headers = {"Accept": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(url, data=body, headers=headers, method=method)

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
                status_code = response.status
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise E2EFailure(
                f"{method} {path} returned HTTP {exc.code}, expected {expected_status}. Body: {error_body}"
            ) from exc
        except URLError as exc:
            raise E2EFailure(
                f"Could not reach API at {self.base_url}. Start it with: uvicorn app.main:app --reload"
            ) from exc

        if status_code != expected_status:
            raise E2EFailure(f"{method} {path} returned HTTP {status_code}, expected {expected_status}")

        if not response_body:
            return None
        return json.loads(response_body)

    def get(self, path: str, query: Optional[Dict[str, Any]] = None, expected_status: int = 200) -> Any:
        return self.request("GET", path, query=query, expected_status=expected_status)

    def post(self, path: str, payload: Dict[str, Any], expected_status: int = 200) -> Any:
        return self.request("POST", path, payload=payload, expected_status=expected_status)

    def patch(self, path: str, payload: Dict[str, Any], expected_status: int = 200) -> Any:
        return self.request("PATCH", path, payload=payload, expected_status=expected_status)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise E2EFailure(message)


def assert_keys(document: Dict[str, Any], keys: List[str], label: str) -> None:
    missing = [key for key in keys if key not in document]
    assert_true(not missing, f"{label} is missing keys: {missing}")


def run_step(name: str, func: Any) -> TestResult:
    started_at = time.perf_counter()
    func()
    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    print(f"PASS {name} ({elapsed_ms} ms)")
    return TestResult(name=name, elapsed_ms=elapsed_ms)


def find_first_employee_with_manager(users: List[Dict[str, Any]]) -> Dict[str, Any]:
    for user in users:
        if user.get("role") == "Employee" and user.get("manager_id"):
            return user
    raise E2EFailure("No employee with manager_id found. Did you run python3 -m app.seed_data?")


def find_pending_leave_for_manager(leaves: List[Dict[str, Any]], manager_id: Optional[str] = None) -> Dict[str, Any]:
    for leave in leaves:
        if leave.get("status") == "Pending" and leave.get("manager_id"):
            if manager_id and leave.get("manager_id") != manager_id:
                continue
            return leave
    raise E2EFailure("No pending leave request found. Did you run python3 -m app.seed_data?")


def build_test_leave_payload(employee_id: str) -> Dict[str, Any]:
    return {
        "user_id": employee_id,
        "leave_type": "WFH",
        "start_date": "2026-06-25",
        "end_date": "2026-06-25",
        "reason": "E2E smoke test remote work day.",
        "ai_parsed_from_text": "Need WFH on June 25 for E2E test.",
    }


def run_e2e(base_url: str) -> None:
    client = APIClient(base_url)
    state: Dict[str, Any] = {}
    results: List[TestResult] = []

    def health_check() -> None:
        response = client.get("/health")
        assert_true(response == {"status": "ok"}, f"Unexpected health response: {response}")

    def auth_login_works() -> None:
        admin_login = client.post(
            "/api/v1/auth/login",
            {"email": "admin@company.com", "password": "Admin@123"},
        )
        assert_keys(admin_login, ["access_token", "token_type", "user"], "Admin login response")
        assert_true(admin_login["user"]["role"] == "Admin", f"Expected admin user, got {admin_login}")
        state["admin_token"] = admin_login["access_token"]

        manager_login = client.post(
            "/api/v1/auth/login",
            {"email": "aarav.mehta@company.com", "password": "Manager@123"},
        )
        assert_true(manager_login["user"]["role"] == "Manager", f"Expected manager user, got {manager_login}")
        state["manager_token"] = manager_login["access_token"]
        state["manager"] = manager_login["user"]
 
        employee_login = client.post(
            "/api/v1/auth/login",
            {"email": "isha.sharma@company.com", "password": "Employee@123"},
        )
        assert_true(employee_login["user"]["role"] == "Employee", f"Expected employee user, got {employee_login}")
        state["employee_token"] = employee_login["access_token"]
        state["employee_login_user"] = employee_login["user"]
        client.set_token(state["admin_token"])

    def auth_me_works() -> None:
        client.set_token(state["employee_token"])
        me = client.get("/api/v1/auth/me")
        assert_true(me["email"] == "isha.sharma@company.com", f"Unexpected /auth/me response: {me}")
        client.set_token(state["admin_token"])

    def rbac_blocks_employee_admin_views() -> None:
        client.set_token(state["employee_token"])
        users = client.get("/api/v1/users")
        assert_true(len(users) == 1, f"Employee /users should only return self, got {len(users)} users")
        forbidden_manager_id = state["manager"]["id"]
        try:
            client.get(f"/api/v1/managers/{forbidden_manager_id}/leave-requests/pending")
        except E2EFailure as exc:
            assert_true("HTTP 403" in str(exc), f"Expected HTTP 403 for employee manager queue access: {exc}")
        else:
            raise E2EFailure("Employee was able to access manager approval queue")
        client.set_token(state["admin_token"])

    def seeded_users_exist() -> None:
        users = client.get("/api/v1/users")
        assert_true(isinstance(users, list), "Users response should be a list")
        assert_true(len(users) >= 23, f"Expected at least 23 seeded users, found {len(users)}")
        managers = [user for user in users if user.get("role") == "Manager"]
        employees = [user for user in users if user.get("role") == "Employee"]
        assert_true(len(managers) >= 3, f"Expected at least 3 managers, found {len(managers)}")
        assert_true(len(employees) >= 20, f"Expected at least 20 employees, found {len(employees)}")
        state["users"] = users
        state["employee"] = find_first_employee_with_manager(users)

    def employee_quotas_exist() -> None:
        employee = state["employee"]
        quotas = client.get(f"/api/v1/users/{employee['id']}/quotas", query={"year": 2026})
        assert_true(len(quotas) == 4, f"Expected 4 leave quotas for {employee['name']}, found {len(quotas)}")
        quota_types = {quota["leave_type"] for quota in quotas}
        assert_true(
            quota_types == {"Sick", "Casual", "WFH", "Comp-off"},
            f"Unexpected quota types: {quota_types}",
        )
        state["quotas"] = quotas

    def seeded_leave_requests_exist() -> None:
        leaves = client.get("/api/v1/leaves")
        assert_true(len(leaves) >= 30, f"Expected at least 30 seeded leave requests, found {len(leaves)}")
        statuses = {leave["status"] for leave in leaves}
        assert_true({"Approved", "Rejected", "Pending"}.issubset(statuses), f"Missing mixed statuses: {statuses}")
        state["leaves"] = leaves
        state["pending_leave"] = find_pending_leave_for_manager(leaves, state["manager"]["id"])

    def natural_language_parser_works() -> None:
        client.set_token(state["employee_token"])
        parsed = client.post(
            "/api/v1/ai/parse-leave-request",
            {
                "text": "Need next Monday and Tuesday off for family function",
                "today": "2026-05-04",
            },
        )
        assert_keys(
            parsed,
            ["leave_type", "start_date", "end_date", "reason", "working_days", "source"],
            "AI parser response",
        )
        assert_true(parsed["leave_type"] == "Casual", f"Expected Casual leave type, got {parsed}")
        assert_true(parsed["start_date"] == "2026-05-11", f"Expected next Monday date, got {parsed}")
        assert_true(parsed["end_date"] == "2026-05-12", f"Expected Tuesday end date, got {parsed}")
        assert_true(parsed["working_days"] == 2.0, f"Expected 2 working days, got {parsed}")
        state["parsed_leave"] = parsed
        client.set_token(state["admin_token"])

    def approval_insight_works() -> None:
        pending_leave = state["pending_leave"]
        client.set_token(state["manager_token"])
        insight = client.post(
            f"/api/v1/ai/approval-insight/{pending_leave['id']}",
            {"manager_id": pending_leave["manager_id"]},
        )
        assert_keys(
            insight,
            [
                "short_manager_summary",
                "possible_team_conflict",
                "leave_balance_impact",
                "approval_recommendation",
                "risk_level",
                "source",
            ],
            "Approval insight response",
        )
        assert_true(
            insight["approval_recommendation"] in {"Approve", "Reject", "Review manually"},
            f"Unexpected approval recommendation: {insight}",
        )
        client.set_token(state["admin_token"])
        refreshed = client.get(f"/api/v1/leaves/{pending_leave['id']}")
        assert_true(refreshed.get("ai_insight") is not None, "Approval insight was not persisted on leave request")
        state["approval_insight"] = insight

    def create_and_approve_leave_request() -> None:
        employee = state["employee_login_user"]
        client.set_token(state["employee_token"])
        created = client.post(
            "/api/v1/leaves",
            build_test_leave_payload(employee["id"]),
            expected_status=201,
        )
        assert_true(created["status"] == "Pending", f"Created leave should be Pending: {created}")
        assert_true(created["total_days"] == 1.0, f"Created leave should be 1 working day: {created}")

        client.set_token(state["manager_token"])
        approved = client.patch(
            f"/api/v1/managers/leave-requests/{created['id']}/approve",
            {
                "manager_id": created["manager_id"],
                "manager_comment": "Approved by E2E smoke test.",
            },
        )
        assert_true(approved["status"] == "Approved", f"Leave approval failed: {approved}")
        assert_true(approved["reviewed_by"] == created["manager_id"], f"Unexpected reviewer: {approved}")
        state["created_leave"] = created
        state["approved_leave"] = approved
        client.set_token(state["admin_token"])

    steps = [
        ("health check", health_check),
        ("auth login works", auth_login_works),
        ("auth me works", auth_me_works),
        ("rbac blocks employee admin views", rbac_blocks_employee_admin_views),
        ("seeded users exist", seeded_users_exist),
        ("employee quotas exist", employee_quotas_exist),
        ("seeded leave requests exist", seeded_leave_requests_exist),
        ("natural language parser works", natural_language_parser_works),
        ("approval insight works", approval_insight_works),
        ("create and approve leave request", create_and_approve_leave_request),
    ]

    print(f"Running E2E tests against {base_url}")
    for name, step in steps:
        results.append(run_step(name, step))

    total_ms = sum(result.elapsed_ms for result in results)
    print(f"\nAll {len(results)} E2E checks passed in {total_ms} ms.")
    print("Note: this script creates and approves one WFH leave request each time it runs.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="End-to-end smoke tests for the Leave Tracker API.")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"FastAPI base URL. Defaults to {DEFAULT_BASE_URL}",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        run_e2e(args.base_url)
    except E2EFailure as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        sys.exit(1)
