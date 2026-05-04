# AI Prompt Log

This file records the AI assistance used while building the Leave Management assessment project.

## Prompt 1

What I asked:

```text
Design the ReactJS frontend for the application. Make sure we use the AI parser, auth page, and all pages depending on manager, admin, and employee.
```

What I got:

```text
Guidance and implementation help for a Vite React frontend with role-based workspaces, authentication, AI leave parser integration, manager approvals, and admin views.
```

What I used:

```text
Created the frontend folder, React app shell, auth page, employee dashboard, manager approval page, admin directory, AI parser form, and styling.
```

## Prompt 2

What I asked:

```text
Might wanna make another folder.
```

What I got:

```text
Recommendation to move frontend code into a dedicated frontend directory instead of keeping it inside FastAPI static files.
```

What I used:

```text
Created frontend/package.json, frontend/index.html, frontend/src/main.jsx, frontend/src/App.jsx, and frontend/src/styles.css.
```

## Prompt 3

What I asked:

```text
Explain where and how AI parsing is happening.
```

What I got:

```text
Explanation that the frontend calls POST /api/v1/ai/parse-leave-request and the backend tries Groq first, then falls back to a local parser.
```

What I used:

```text
Verified the parser flow and used the explanation to improve the UI source indicator.
```

## Prompt 4

What I asked:

```text
I wanna see the AI thingy work. It's not parsing properly.
```

What I got:

```text
Debugging help showing that GROQ_API_KEY was missing or Groq was failing, causing fallback parsing.
```

What I used:

```text
Improved fallback parsing for common date formats, weekdays, relative dates, and duration phrases. Added backend logging for Groq failures.
```

## Prompt 5

What I asked:

```text
How to see if Groq API is working?
```

What I got:

```text
Steps to check GROQ_API_KEY, restart FastAPI, test the parser response source, and call Groq's models endpoint with curl.
```

What I used:

```text
Added clearer troubleshooting instructions to README.md and exposed parser source in the frontend.
```

## Prompt 6

What I asked:

```text
It prints the API key, still fallback in frontend.
```

What I got:

```text
Debugging direction that the server process may not see the environment variable or that Groq may be rejecting the request.
```

What I used:

```text
Removed a hardcoded Groq key from code, added safe logging, and added an AI status endpoint.
```

## Prompt 7

What I asked:

```text
Groq leave parser failed; using fallback parser: Groq API HTTP 403: error code: 1010.
```

What I got:

```text
Explanation that 403/1010 is likely an edge access block before normal Groq API processing.
```

What I used:

```text
Added Accept and User-Agent headers to the Groq request and documented the failure mode.
```

## Prompt 8

What I asked:

```text
Create ARCHITECTURE.md and README.md. In README.md I want all installation steps so one can download the repo and install it by following the steps.
```

What I got:

```text
Documentation structure covering install, environment variables, seed data, backend/frontend startup, testing, architecture, and troubleshooting.
```

What I used:

```text
Created README.md and ARCHITECTURE.md at the repository root.
```

## Prompt 9

What I asked:

```text
Add functionality where managers can see the entry and exit time of an employee, and employees can click a button to make entry/exit happen as a simulation.
```

What I got:

```text
Implementation plan for a simulated attendance API and role-based UI.
```

What I used:

```text
Added attendance models, schemas, routes, MongoDB indexes, employee punch button, and manager attendance tab.
```

## Prompt 10

What I asked:

```text
Read the assessment document and suggest changes we can do to our project.
```

What I got:

```text
Gap analysis against the assessment: add PROMPTS.md, team calendar, employee filters, manager dropdown, AI status/reliability, CSV export, simple chart, and architecture improvements.
```

What I used:

```text
Added assessment-aligned features: team calendar, employee filters, manager dropdown, CSV export, chart, AI status endpoint, and documentation updates.
```

## Prompt 11

What I asked:

```text
Do the bonus changes if possible: monthly CSV export for team leave reports, simple charts, and half-day support.
```

What I got:

```text
Implementation plan for making the existing CSV/chart features more assessment-specific and adding half-day as a persisted backend field.
```

What I used:

```text
Added monthly CSV export controls, leave-by-month chart, half-day request support in backend schemas and CRUD, half-day frontend form control, and documentation updates.
```
