# Architecture

## Overview

The application is split into two main parts:

- A FastAPI backend under `app/`.
- A React/Vite frontend under `frontend/`.

MongoDB stores users, leave quotas, leave requests, and audit trails. The frontend authenticates with the backend, stores the bearer token in local storage, and calls role-specific API endpoints.

```text
Browser
  |
  | React/Vite frontend
  v
FastAPI API
  |
  | Motor async driver
  v
MongoDB

FastAPI API
  |
  | optional HTTPS request
  v
Groq API
```

## Backend Layout

```text
app/main.py
```

Creates the FastAPI application, configures CORS, connects to MongoDB during lifespan startup, includes route modules, and serves legacy static files from `app/static`.

```text
app/database.py
```

Creates the MongoDB client and database handle. It also creates indexes for users, leave quotas, leave requests, and audit trails during startup.

```text
app/auth.py
```

Handles password hashing, password verification, token creation, token decoding, current-user lookup, and role guards.

```text
app/models.py
```

Defines domain enums and Mongo-oriented model classes:

- `UserRole`: `Employee`, `Manager`, `Admin`
- `LeaveType`: `Sick`, `Casual`, `WFH`, `Comp-off`
- `LeaveStatus`: `Pending`, `Approved`, `Rejected`
- `AuditAction`

```text
app/schemas.py
```

Defines Pydantic request and response schemas for users, auth, quotas, leave requests, decisions, audit trails, and AI responses.

```text
app/crud.py
```

Contains database operations and domain rules, including:

- creating and updating users
- listing users
- creating leave quotas
- creating leave requests
- calculating total leave days
- enforcing quota availability
- approving or rejecting leave requests
- writing audit trail records

## Route Modules

```text
app/routes/auth.py
```

Authentication endpoints:

- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`

```text
app/routes/users.py
```

User and quota endpoints. Admins can create and update users. Managers see their team. Employees see themselves.

```text
app/routes/leaves.py
```

Leave request endpoints. Employees can create their own leave requests. Managers can create leave for themselves or team members. Admins can view broader data.

```text
app/routes/managers.py
```

Manager approval queue and approval/rejection endpoints.

```text
app/routes/ai.py
```

AI endpoints:

- `POST /api/v1/ai/parse-leave-request`
- `POST /api/v1/ai/approval-insight/{leave_id}`

The parser endpoint attempts Groq first. If Groq fails, it returns a local fallback result. The response includes `source`, so the frontend can show whether the result came from `groq` or `fallback`.

## Frontend Layout

```text
frontend/src/main.jsx
```

Mounts the React app.

```text
frontend/src/App.jsx
```

Contains the main application shell and role workspaces:

- `AuthPage`
- `EmployeeWorkspace`
- `ManagerWorkspace`
- `AdminWorkspace`
- `LeaveComposer`
- `ApprovalQueue`
- directory, request, balance, and summary components

```text
frontend/src/styles.css
```

Defines the visual system, responsive layout, panels, tables, request cards, badges, forms, and auth screen.

## Authentication Flow

1. User submits email and password from the frontend.
2. Frontend calls `POST /api/v1/auth/login`.
3. Backend verifies the password hash and returns an access token plus public user data.
4. Frontend stores the token in `localStorage`.
5. Future API calls include:

```text
Authorization: Bearer <token>
```

6. Backend dependencies decode the token and load the current user from MongoDB.

## Role-Based Access

The backend is the source of truth for role enforcement.

Employee:

- Can view their own user record.
- Can view their own leave requests.
- Can create leave requests for themselves.
- Can use the AI leave parser.

Manager:

- Can view their team.
- Can view pending approval queue for their own manager ID.
- Can approve or reject their team members' requests.
- Can generate AI approval insight for requests assigned to them.

Admin:

- Can list and create users.
- Can view broader leave data.
- Can create quotas.
- Can access manager approval/history endpoints.

## Leave Request Flow

1. Employee enters natural-language text in the frontend.
2. Frontend calls `POST /api/v1/ai/parse-leave-request`.
3. Backend returns structured fields:

```text
leave_type
start_date
end_date
reason
working_days
confidence
missing_fields
source
```

4. Frontend fills the leave form.
5. Employee reviews and submits.
6. Frontend calls `POST /api/v1/leaves`.
7. Backend validates dates, quota, manager assignment, and access rules.
8. Backend stores a pending leave request and increments pending quota days.
9. Manager sees the request in their pending queue.
10. Manager approves or rejects the request.
11. Backend updates leave status, quota counts, review metadata, and audit trail.

## AI Parser Flow

The AI parser lives in `app/routes/ai.py`.

```text
frontend LeaveComposer
  -> POST /api/v1/ai/parse-leave-request
  -> parse_leave_request()
  -> call_groq_json()
  -> normalize_parser_response()
  -> frontend fills form
```

If Groq fails:

```text
call_groq_json()
  -> exception
  -> fallback_parse_leave_request()
  -> response source becomes fallback
```

The fallback parser is deliberately local and deterministic. It handles common phrases such as weekdays, tomorrow, ISO dates, day/month dates, month names, and simple duration phrases.

## AI Approval Insight Flow

Manager clicks `AI insight` on a pending leave request.

```text
frontend ApprovalCard
  -> POST /api/v1/ai/approval-insight/{leave_id}
  -> get_approval_context()
  -> call_groq_json()
  -> normalize_approval_response()
  -> save_ai_insight()
```

The approval context includes:

- leave request details
- employee details
- leave balances
- overlapping pending or approved team leaves

If Groq fails, the backend returns a deterministic fallback insight based on balances and overlaps.

## Data Model

Users:

- identity and login email
- hashed password
- role
- department
- manager relationship
- active/inactive status

Leave quotas:

- user
- year
- leave type
- total days
- used days
- pending days

Leave requests:

- user
- manager
- leave type
- start and end dates
- total working days
- reason
- status
- manager comments
- optional AI parsed text
- optional AI insight
- review metadata

Audit trails:

- entity type and ID
- actor ID
- action
- before/after snapshots
- timestamp

## Configuration

Backend environment variables:

- `MONGODB_URI`
- `MONGODB_DB_NAME`
- `JWT_SECRET_KEY`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `GROQ_API_KEY`
- `GROQ_API_URL`
- `GROQ_MODEL`
- `GROQ_TIMEOUT_SECONDS`

Frontend environment variable:

- `VITE_API_BASE`

Default frontend API base:

```text
http://127.0.0.1:8000/api/v1
```

## Development Runtime

Typical local runtime:

```text
MongoDB:  localhost:27017
Backend:  http://127.0.0.1:8000
Frontend: http://localhost:5173
```

The backend CORS configuration allows common local Vite origins.

## Testing

`e2e_test.py` exercises the API as a smoke test. It assumes:

- backend is running
- database has been seeded
- demo credentials are available

The test checks health, auth, RBAC, seeded users, quotas, leave requests, AI parser response shape, approval insight, and manager decisions.
