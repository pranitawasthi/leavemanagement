# Leave Management

A role-based leave and time-off management application with a FastAPI backend, MongoDB persistence, a React/Vite frontend, JWT-style bearer authentication, seeded demo data, and Groq-powered AI helpers for parsing natural-language leave requests and generating manager approval insights.

## Features

- Employee, Manager, and Admin role-based views.
- Employee leave request creation with natural-language AI parsing.
- Manager approval queue with approve/reject actions and AI approval insight.
- Admin people directory and user creation.
- Leave quotas, leave request history, audit trail storage, and seeded demo data.
- End-to-end API smoke test script.

## Tech Stack

- Backend: FastAPI, Uvicorn, Motor, MongoDB, Pydantic.
- Frontend: React 18, Vite.
- Database: MongoDB.
- AI provider: Groq OpenAI-compatible chat completions API.

## Prerequisites

Install these before running the project:

- Python 3.10 or newer.
- Node.js 18 or newer.
- npm.
- MongoDB running locally, or a MongoDB connection string.
- Optional: a Groq API key for real AI parsing.

## Installation

Clone the repository:

```bash
git clone <repo-url>
cd leave_management
```

Create and activate a Python virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install backend dependencies:

```bash
pip install -r requirements.txt
```

Install frontend dependencies:

```bash
cd frontend
npm install
cd ..
```

## Environment Variables

The app has sensible development defaults, but these variables can be configured:

```bash
export MONGODB_URI="mongodb://localhost:27017"
export MONGODB_DB_NAME="leave_management"
export JWT_SECRET_KEY="change-this-for-real-use"
export ACCESS_TOKEN_EXPIRE_MINUTES="480"
export GROQ_API_KEY="your_groq_api_key"
export GROQ_MODEL="llama-3.3-70b-versatile"
```

`GROQ_API_KEY` is optional. If it is missing or Groq rejects the request, the backend uses a local fallback parser and the frontend will show a `fallback` source.

## Database Setup

Start MongoDB first. If you use a local MongoDB service, the default URI is:

```text
mongodb://localhost:27017
```

Seed demo data:

```bash
python3 -m app.seed_data
```

The seed script creates demo users, managers, employees, leave quotas, leave requests, and audit trails.

Demo credentials:

```text
Admin:    admin@company.com / Admin@123
Manager:  aarav.mehta@company.com / Manager@123
Employee: isha.sharma@company.com / Employee@123
```

## Run The Backend

From the repository root:

```bash
uvicorn app.main:app --reload
```

Backend URLs:

```text
API:     http://127.0.0.1:8000
Docs:    http://127.0.0.1:8000/docs
Health:  http://127.0.0.1:8000/health
```

## Run The Frontend

In another terminal:

```bash
cd frontend
npm run dev
```

Open:

```text
http://localhost:5173
```

By default the frontend calls:

```text
http://127.0.0.1:8000/api/v1
```

To point it at another backend:

```bash
cd frontend
VITE_API_BASE="http://your-backend-host/api/v1" npm run dev
```

## Check AI Parsing

Start the backend with a Groq key:

```bash
export GROQ_API_KEY="your_groq_api_key"
uvicorn app.main:app --reload
```

Then open the frontend, log in as an employee, go to `Request`, enter a sentence like:

```text
Need next Monday and Tuesday off for family function
```

Click `Parse with AI`.

The parser result shows the source:

- `groq`: real Groq API response.
- `fallback (...)`: local fallback parser was used because Groq failed or was not configured.

You can also test Groq reachability directly:

```bash
curl https://api.groq.com/openai/v1/models \
  -H "Authorization: Bearer $GROQ_API_KEY" \
  -H "Accept: application/json"
```

## Run Tests

Start the backend and seed the database first, then run:

```bash
python3 e2e_test.py
```

To test a different backend URL:

```bash
python3 e2e_test.py --base-url http://127.0.0.1:8000
```

## Useful API Endpoints

- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET /api/v1/users`
- `POST /api/v1/users`
- `GET /api/v1/users/{user_id}/quotas`
- `POST /api/v1/leaves`
- `GET /api/v1/leaves`
- `GET /api/v1/managers/{manager_id}/leave-requests/pending`
- `PATCH /api/v1/managers/leave-requests/{leave_id}/approve`
- `PATCH /api/v1/managers/leave-requests/{leave_id}/reject`
- `POST /api/v1/ai/parse-leave-request`
- `POST /api/v1/ai/approval-insight/{leave_id}`

## Project Structure

```text
app/
  routes/          FastAPI route modules
  utils/           Date and leave-day helpers
  auth.py          Authentication and role dependencies
  crud.py          Database operations
  database.py      MongoDB connection setup
  main.py          FastAPI app entrypoint
  models.py        Domain enums and Mongo models
  schemas.py       Pydantic request/response schemas
  seed_data.py     Demo data seeding script
frontend/
  src/
    App.jsx        React app and role workspaces
    styles.css     Frontend styles
    main.jsx       React entrypoint
  package.json
e2e_test.py        API smoke test script
requirements.txt   Backend dependencies
ARCHITECTURE.md    System architecture notes
```

## Troubleshooting

If login fails, make sure MongoDB is running and `python3 -m app.seed_data` completed successfully.

If the frontend cannot reach the backend, make sure FastAPI is running on `http://127.0.0.1:8000`. The backend CORS settings allow Vite on `localhost:5173`.

If AI parsing says `fallback`, check the FastAPI terminal logs. A `403 / 1010` from Groq usually means the request is being blocked by Groq/Cloudflare before normal API processing.

If MongoDB connects to the wrong database, set `MONGODB_URI` and `MONGODB_DB_NAME` explicitly before starting the backend and before running the seed script.
