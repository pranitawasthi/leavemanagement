import React from "react";
import { useEffect, useMemo, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000/api/v1";
const TOKEN_KEY = "leave_app_token";
const LEAVE_TYPES = ["Sick", "Casual", "WFH", "Comp-off"];
const ROLES = ["Employee", "Manager", "Admin"];

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [currentUser, setCurrentUser] = useState(null);
  const [users, setUsers] = useState([]);
  const [leaves, setLeaves] = useState([]);
  const [quotas, setQuotas] = useState([]);
  const [tab, setTab] = useState("overview");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(Boolean(token));

  const api = useMemo(() => {
    return async (path, options = {}) => {
      const response = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(options.headers || {}),
        },
      });
      const text = await response.text();
      const data = text ? JSON.parse(text) : null;
      if (!response.ok) throw new Error(data?.detail || data?.message || "Request failed");
      return data;
    };
  }, [token]);

  const flash = (message) => {
    setNotice(message);
    window.clearTimeout(flash.timer);
    flash.timer = window.setTimeout(() => setNotice(""), 4200);  
  }; 

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setCurrentUser(null);
    setUsers([]);
    setLeaves([]);
    setQuotas([]);
    setTab("overview");
  };

  const refresh = async (user = currentUser) => {
    if (!user) return;
    const year = new Date().getFullYear();
    const [nextUsers, nextLeaves, nextQuotas] = await Promise.all([
      api("/users"),
      api("/leaves"),
      api(`/users/${user.id}/quotas?year=${year}`).catch(() => []),
    ]);
    setUsers(nextUsers);
    setLeaves(nextLeaves);
    setQuotas(nextQuotas);
  };

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const user = await api("/auth/me");
        if (cancelled) return;
        setCurrentUser(user);
        setTab(user.role === "Admin" ? "people" : "overview");
        await refresh(user);
      } catch (error) {
        if (!cancelled) {
          logout();
          flash(error.message);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [token, api]);

  const login = async (credentials) => {
    const data = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify(credentials),
    });
    localStorage.setItem(TOKEN_KEY, data.access_token);
    setToken(data.access_token);
    setCurrentUser(data.user);
    flash(`Welcome back, ${data.user.name}.`);
  };

  if (!currentUser && !loading) return <AuthPage onLogin={login} notice={notice} />;

  return (
    <Shell user={currentUser} tab={tab} setTab={setTab} notice={notice} loading={loading} logout={logout}>
      {loading ? (
        <Loading />
      ) : (
        <Workspace
          api={api}
          flash={flash}
          user={currentUser}
          users={users}
          leaves={leaves}
          quotas={quotas}
          tab={tab}
          refresh={refresh}
        />
      )}
    </Shell>
  );
}

function AuthPage({ onLogin, notice }) {
  const [email, setEmail] = useState("isha.sharma@company.com");
  const [password, setPassword] = useState("Employee@123");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const presets = [
    ["Employee", "isha.sharma@company.com", "Employee@123"],
    ["Manager", "aarav.mehta@company.com", "Manager@123"],
    ["Admin", "admin@company.com", "Admin@123"],
  ];

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await onLogin({ email, password });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="auth-page">
      <section className="auth-visual">
        <Brand />
        <h1>Plan time away without losing the team picture.</h1>
        <p>
          Employees can ask in natural language, managers get AI review context,
          and admins keep people, balances, and requests in one place.
        </p>
        <div className="metric-strip">
          <Metric label="AI parser" value="Natural text" />
          <Metric label="Roles" value="3 views" />
          <Metric label="Approvals" value="Insight-led" />
        </div>
      </section>
      <section className="auth-card">
        <h2>Sign in</h2>
        <p className="muted">Use seeded credentials or your backend account.</p>
        {(error || notice) && <div className="alert">{error || notice}</div>}
        <form onSubmit={submit}>
          <label>Email<input value={email} type="email" onChange={(e) => setEmail(e.target.value)} required /></label>
          <label>Password<input value={password} type="password" onChange={(e) => setPassword(e.target.value)} required /></label>
          <button className="primary" disabled={busy}>{busy ? "Signing in..." : "Sign in"}</button>
        </form>
        <div className="preset-grid">
          {presets.map(([label, presetEmail, presetPassword]) => (
            <button className="soft" key={label} onClick={() => { setEmail(presetEmail); setPassword(presetPassword); }}>
              {label}
            </button>
          ))}
        </div>
      </section>
    </main>
  );
}

function Shell({ user, tab, setTab, notice, loading, logout, children }) {
  const tabs = user ? roleTabs(user.role) : [];
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Brand />
        <nav className="nav-tabs">
          {tabs.map((item) => (
            <button className={tab === item.id ? "active" : ""} key={item.id} onClick={() => setTab(item.id)}>
              <span>{item.step}</span>{item.label}
            </button>
          ))}
        </nav>
      </aside>
      <main className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">{loading ? "Loading" : user?.role}</p>
            <h1>{loading ? "Preparing workspace" : titleFor(user)}</h1>
          </div>
          {user && (
            <div className="profile-pill">
              <div><strong>{user.name}</strong><span>{user.department}</span></div>
              <button className="ghost" onClick={logout}>Logout</button>
            </div>
          )}
        </header>
        {notice && <div className="toast">{notice}</div>}
        {children}
      </main>
    </div>
  );
}

function Workspace(props) {
  if (props.user.role === "Admin") return <AdminWorkspace {...props} />;
  if (props.user.role === "Manager") return <ManagerWorkspace {...props} />;
  return <EmployeeWorkspace {...props} />;
}

function EmployeeWorkspace({ api, flash, user, users, leaves, quotas, tab, refresh }) {
  const userMap = useUserMap(users);
  if (tab === "request") return <LeaveComposer api={api} flash={flash} user={user} refresh={refresh} />;
  if (tab === "balances") return <Balances quotas={quotas} leaves={leaves} userMap={userMap} />;
  if (tab === "calendar") return <TeamCalendar api={api} flash={flash} users={users} />;
  return (
    <DashboardGrid>
      <SummaryCards leaves={leaves} quotas={quotas} users={users} />
      <LeaveTypeChart leaves={leaves} />
      <LeaveMonthChart leaves={leaves} />
      <EmployeeAttendance api={api} flash={flash} />
      <Panel title="Recent requests" action={<RefreshButton onClick={refresh} />}>
        <LeaveFilters leaves={leaves} users={users} userMap={userMap} showExport={false} />
      </Panel>
      <Panel title="Profile">
        <Profile user={user} users={users} />
      </Panel>
    </DashboardGrid>
  );
}

function ManagerWorkspace({ api, flash, user, users, leaves, tab, refresh }) {
  const userMap = useUserMap(users);
  const [pending, setPending] = useState([]);
  const [busy, setBusy] = useState(false);

  const loadPending = async () => {
    setBusy(true);
    try {
      setPending(await api(`/managers/${user.id}/leave-requests/pending`));
    } catch (error) {
      flash(error.message);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    loadPending();
  }, [user.id]);

  const decide = async (leaveId, approved, comment) => {
    const endpoint = approved ? "approve" : "reject";
    await api(`/managers/leave-requests/${leaveId}/${endpoint}`, {
      method: "PATCH",
      body: JSON.stringify({ manager_id: user.id, manager_comment: comment || null }),
    });
    flash(`Request ${approved ? "approved" : "rejected"}.`);
    await Promise.all([loadPending(), refresh()]);
  };

  if (tab === "team") return <TeamPage users={users} leaves={leaves} manager={user} userMap={userMap} />;
  if (tab === "attendance") return <ManagerAttendance api={api} flash={flash} users={users} userMap={userMap} />;
  if (tab === "calendar") return <TeamCalendar api={api} flash={flash} users={users} />;
  if (tab === "history") {
    return <Panel title="Team leave history" action={<RefreshButton onClick={refresh} />}><LeaveFilters leaves={leaves} users={users} userMap={userMap} showExport /></Panel>;
  }
  return (
    <DashboardGrid>
      <SummaryCards leaves={leaves} users={users} />
      <LeaveTypeChart leaves={leaves} />
      <LeaveMonthChart leaves={leaves} />
      <Panel title="Pending approvals" action={<RefreshButton onClick={loadPending} busy={busy} />}>
        <ApprovalQueue api={api} flash={flash} manager={user} leaves={pending} userMap={userMap} onDecision={decide} />
      </Panel>
    </DashboardGrid>
  );
}

function AdminWorkspace({ api, flash, user, users, leaves, tab, refresh }) {
  const userMap = useUserMap(users);
  if (tab === "requests") {
    return <Panel title="All leave requests" action={<RefreshButton onClick={refresh} />}><LeaveFilters leaves={leaves} users={users} userMap={userMap} showExport /></Panel>;
  }
  if (tab === "calendar") return <TeamCalendar api={api} flash={flash} users={users} />;
  if (tab === "create") return <AdminCreateUser api={api} flash={flash} users={users} refresh={refresh} />;
  return (
    <DashboardGrid>
      <SummaryCards leaves={leaves} users={users} />
      <LeaveTypeChart leaves={leaves} />
      <LeaveMonthChart leaves={leaves} />
      <Panel title="People directory" action={<RefreshButton onClick={refresh} />}>
        <PeopleTable users={users} currentUser={user} />
      </Panel>
    </DashboardGrid>
  );
}

function LeaveComposer({ api, flash, user, refresh }) {
  const [text, setText] = useState("Need next Monday and Tuesday off for family function");
  const [form, setForm] = useState({ leave_type: "Casual", start_date: "", end_date: "", is_half_day: false, reason: "", manager_id: user.manager_id || "" });
  const [managers, setManagers] = useState([]);
  const [parsed, setParsed] = useState(null);
  const [busy, setBusy] = useState("");

  useEffect(() => {
    async function loadManagers() {
      try {
        const result = await api("/users?role=Manager");
        setManagers(result);
        if (!form.manager_id && result.length) {
          setForm((current) => ({ ...current, manager_id: result[0].id }));
        }
      } catch (error) {
        flash(error.message);
      }
    }
    loadManagers();
  }, []);

  const parse = async () => {
    setBusy("parse");
    try {
      const result = await api("/ai/parse-leave-request", {
        method: "POST",
        body: JSON.stringify({ text, today: new Date().toISOString().slice(0, 10) }),
      });
      setParsed(result);
      setForm({
        leave_type: result.leave_type || form.leave_type,
        start_date: result.start_date || form.start_date,
        end_date: result.end_date || form.end_date,
        is_half_day: Boolean(result.is_half_day),
        reason: result.reason || text,
      });
      flash(`AI parser filled the request from ${result.source}.`);
    } catch (error) {
      flash(error.message);
    } finally {
      setBusy("");
    }
  };

  const submit = async (event) => {
    event.preventDefault();
    setBusy("submit");
    try {
      await api("/leaves", {
        method: "POST",
        body: JSON.stringify({ ...form, user_id: user.id, ai_parsed_from_text: text }),
      });
      flash("Leave request submitted.");
      setText("");
      setParsed(null);
      setForm({ leave_type: "Casual", start_date: "", end_date: "", is_half_day: false, reason: "", manager_id: user.manager_id || managers[0]?.id || "" });
      await refresh();
    } catch (error) {
      flash(error.message);
    } finally {
      setBusy("");
    }
  };

  return (
    <DashboardGrid>
      <Panel title="AI leave parser" subtitle="Start with natural language, then review the structured request.">
        <div className="composer">
          <label>Request text<textarea value={text} onChange={(e) => setText(e.target.value)} /></label>
          <button className="primary" onClick={parse} disabled={busy === "parse" || text.trim().length < 5}>{busy === "parse" ? "Parsing..." : "Parse with AI"}</button>
        </div>
        {parsed && <ParserResult parsed={parsed} />}
      </Panel>
      <Panel title="Review and submit">
        <form onSubmit={submit}>
          <div className="form-grid">
            <label>Leave type<select value={form.leave_type} onChange={(e) => setForm({ ...form, leave_type: e.target.value })}>{LEAVE_TYPES.map((type) => <option key={type}>{type}</option>)}</select></label>
            <label>Start date<input type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value, end_date: form.is_half_day ? e.target.value : form.end_date })} required /></label>
            <label>End date<input type="date" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} required disabled={form.is_half_day} /></label>
            <label>Apply to manager<select value={form.manager_id} onChange={(e) => setForm({ ...form, manager_id: e.target.value })} required>{managers.map((manager) => <option key={manager.id} value={manager.id}>{manager.name}</option>)}</select></label>
          </div>
          <label className="checkbox-line">
            <input
              type="checkbox"
              checked={form.is_half_day}
              onChange={(e) => setForm({ ...form, is_half_day: e.target.checked, end_date: e.target.checked ? form.start_date : form.end_date })}
            />
            Half-day leave
          </label>
          <label>Reason<textarea value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} required /></label>
          <button className="primary" disabled={busy === "submit"}>{busy === "submit" ? "Submitting..." : "Submit request"}</button>
        </form>
      </Panel>
    </DashboardGrid>
  );
}

function ApprovalQueue({ api, flash, manager, leaves, userMap, onDecision }) {
  if (!leaves.length) return <EmptyState title="No pending approvals" text="The approval queue is clear." />;
  return <div className="stack">{leaves.map((leave) => <ApprovalCard key={leave.id} api={api} flash={flash} manager={manager} leave={leave} user={userMap[leave.user_id]} onDecision={onDecision} />)}</div>;
}

function EmployeeAttendance({ api, flash }) {
  const [records, setRecords] = useState([]);
  const [busy, setBusy] = useState(false);
  const today = localDateISO();
  const current = records[0];

  const loadAttendance = async () => {
    try {
      setRecords(await api(`/attendance/me?work_date=${today}`));
    } catch (error) {
      flash(error.message);
    }
  };

  useEffect(() => {
    loadAttendance();
  }, []);

  const punch = async () => {
    setBusy(true);
    try {
      const record = await api("/attendance/punch", { method: "POST", body: JSON.stringify({}) });
      setRecords([record]);
      flash(record.exit_time ? "Exit time recorded." : "Entry time recorded.");
    } catch (error) {
      flash(error.message);
    } finally {
      setBusy(false);
    }
  };

  const buttonText = !current ? "Mark entry" : current.exit_time ? "Attendance complete" : "Mark exit";

  return (
    <Panel title="Today attendance" action={<RefreshButton onClick={loadAttendance} />}>
      <div className="attendance-card">
        <div className="attendance-times">
          <Metric label="Entry" value={current?.entry_time ? formatTime(current.entry_time) : "Not marked"} />
          <Metric label="Exit" value={current?.exit_time ? formatTime(current.exit_time) : "Not marked"} />
          <Metric label="Status" value={current?.status || "Not started"} />
        </div>
        <button className="primary" onClick={punch} disabled={busy || Boolean(current?.exit_time)}>
          {busy ? "Saving..." : buttonText}
        </button>
      </div>
    </Panel>
  );
}

function ManagerAttendance({ api, flash, userMap }) {
  const [workDate, setWorkDate] = useState(localDateISO());
  const [records, setRecords] = useState([]);
  const [busy, setBusy] = useState(false);

  const loadAttendance = async () => {
    setBusy(true);
    try {
      const query = workDate ? `?work_date=${workDate}` : "";
      setRecords(await api(`/attendance/team${query}`));
    } catch (error) {
      flash(error.message);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    loadAttendance();
  }, []);

  return (
    <Panel title="Team attendance" subtitle="Simulated entry and exit times from employee punch actions." action={<RefreshButton onClick={loadAttendance} busy={busy} />}>
      <div className="filter-row">
        <input type="date" value={workDate} onChange={(e) => setWorkDate(e.target.value)} />
        <button className="soft" onClick={loadAttendance} disabled={busy}>Apply date</button>
        <span>{records.length} record(s)</span>
      </div>
      <AttendanceTable records={records} userMap={userMap} />
    </Panel>
  );
}

function AttendanceTable({ records, userMap }) {
  if (!records.length) return <EmptyState title="No attendance records" text="No team member has marked attendance for this date." />;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Employee</th>
            <th>Date</th>
            <th>Entry</th>
            <th>Exit</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {records.map((record) => {
            const employee = userMap[record.user_id];
            return (
              <tr key={record.id}>
                <td><strong>{employee?.name || record.user_id}</strong><span>{employee?.employee_id || "Employee"}</span></td>
                <td>{record.work_date}</td>
                <td>{formatTime(record.entry_time)}</td>
                <td>{record.exit_time ? formatTime(record.exit_time) : "Not marked"}</td>
                <td><StatusBadge status={record.status} /></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ApprovalCard({ api, flash, manager, leave, user, onDecision }) {
  const [comment, setComment] = useState("");
  const [insight, setInsight] = useState(leave.ai_insight || null);
  const [busy, setBusy] = useState("");

  const generateInsight = async () => {
    setBusy("insight");
    try {
      const result = await api(`/ai/approval-insight/${leave.id}`, {
        method: "POST",
        body: JSON.stringify({ manager_id: manager.id }),
      });
      setInsight(result);
      flash(`AI insight generated from ${result.source}.`);
    } catch (error) {
      flash(error.message);
    } finally {
      setBusy("");
    }
  };

  const decide = async (approved) => {
    setBusy(approved ? "approve" : "reject");
    try {
      await onDecision(leave.id, approved, comment);
    } finally {
      setBusy("");
    }
  };

  return (
    <article className="request-card">
      <div className="request-main">
        <div><strong>{user?.name || "Employee"}</strong><span>{user?.department || "Team"} · {leave.leave_type}</span></div>
        <StatusBadge status={leave.status} />
      </div>
      <p>{formatDate(leave.start_date)} to {formatDate(leave.end_date)} · {fmtDays(leave.total_days)} day(s)</p>
      {leave.is_half_day && <p className="muted">Half-day request</p>}
      <p>{leave.reason}</p>
      {insight && <InsightBlock insight={insight} />}
      <div className="decision-row">
        <input value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Manager comment" />
        <button className="soft" onClick={generateInsight} disabled={busy === "insight"}>{busy === "insight" ? "Thinking..." : "AI insight"}</button>
        <button className="success" onClick={() => decide(true)} disabled={Boolean(busy)}>Approve</button>
        <button className="danger" onClick={() => decide(false)} disabled={Boolean(busy)}>Reject</button>
      </div>
    </article>
  );
}

function AdminCreateUser({ api, flash, users, refresh }) {
  const managers = users.filter((item) => item.role === "Manager");
  const [form, setForm] = useState({
    employee_id: "",
    name: "",
    email: "",
    password: "Employee@123",
    role: "Employee",
    department: "",
    manager_id: "",
    job_title: "",
    is_active: true,
  });
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      await api("/users", { method: "POST", body: JSON.stringify({ ...form, manager_id: form.manager_id || null }) });
      flash("User created.");
      setForm({ ...form, employee_id: "", name: "", email: "", manager_id: "", job_title: "" });
      await refresh();
    } catch (error) {
      flash(error.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel title="Create user" subtitle="Admins can add employees, managers, and admins.">
      <form onSubmit={submit}>
        <div className="form-grid">
          <Field label="Employee ID" value={form.employee_id} onChange={(employee_id) => setForm({ ...form, employee_id })} />
          <Field label="Name" value={form.name} onChange={(name) => setForm({ ...form, name })} />
          <Field label="Email" type="email" value={form.email} onChange={(email) => setForm({ ...form, email })} />
          <Field label="Password" type="password" value={form.password} onChange={(password) => setForm({ ...form, password })} />
          <label>Role<select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>{ROLES.map((role) => <option key={role}>{role}</option>)}</select></label>
          <Field label="Department" value={form.department} onChange={(department) => setForm({ ...form, department })} />
          <Field label="Job title" value={form.job_title} onChange={(job_title) => setForm({ ...form, job_title })} />
          <label>Manager<select value={form.manager_id} onChange={(e) => setForm({ ...form, manager_id: e.target.value })}><option value="">No manager</option>{managers.map((manager) => <option key={manager.id} value={manager.id}>{manager.name}</option>)}</select></label>
        </div>
        <button className="primary" disabled={busy}>{busy ? "Creating..." : "Create user"}</button>
      </form>
    </Panel>
  );
}

function TeamCalendar({ api, flash, users }) {
  const [leaveType, setLeaveType] = useState("");
  const [range, setRange] = useState("this");
  const [leaves, setLeaves] = useState([]);
  const [directory, setDirectory] = useState(users);
  const [busy, setBusy] = useState(false);
  const userMap = useUserMap(directory.length ? directory : users);
  const { start, end } = calendarRange(range);

  const loadCalendar = async () => {
    setBusy(true);
    try {
      const params = new URLSearchParams({ start_date: start, end_date: end });
      if (leaveType) params.set("leave_type", leaveType);
      const [calendarLeaves, employees, managers] = await Promise.all([
        api(`/leaves/calendar?${params.toString()}`),
        api("/users?role=Employee").catch(() => []),
        api("/users?role=Manager").catch(() => []),
      ]);
      setLeaves(calendarLeaves);
      setDirectory([...employees, ...managers]);
    } catch (error) {
      flash(error.message);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    loadCalendar();
  }, [range, leaveType]);

  return (
    <Panel title="Team calendar" subtitle="See who is out this week and next week." action={<RefreshButton onClick={loadCalendar} busy={busy} />}>
      <div className="filter-row">
        <select value={range} onChange={(e) => setRange(e.target.value)}>
          <option value="this">This week</option>
          <option value="next">Next week</option>
          <option value="both">This and next week</option>
        </select>
        <select value={leaveType} onChange={(e) => setLeaveType(e.target.value)}>
          <option value="">All leave types</option>
          {LEAVE_TYPES.map((type) => <option key={type}>{type}</option>)}
        </select>
        <span>{formatDate(start)} to {formatDate(end)}</span>
      </div>
      <CalendarList leaves={leaves} userMap={userMap} start={start} end={end} />
    </Panel>
  );
}

function CalendarList({ leaves, userMap, start, end }) {
  const days = enumerateDays(start, end);
  const grouped = days.map((day) => {
    const items = leaves.filter((leave) => leave.start_date <= day && leave.end_date >= day);
    return { day, items };
  });

  return (
    <div className="calendar-grid">
      {grouped.map(({ day, items }) => (
        <section className="calendar-day" key={day}>
          <div className="calendar-date">
            <strong>{new Date(`${day}T00:00:00`).toLocaleDateString(undefined, { weekday: "short" })}</strong>
            <span>{formatDate(day)}</span>
          </div>
          {items.length ? items.map((leave) => {
            const person = userMap[leave.user_id];
            return (
              <div className="calendar-item" key={`${day}-${leave.id}`}>
                <strong>{person?.name || "Employee"}</strong>
                <span>{leave.leave_type}{leave.is_half_day ? " · Half-day" : ""}</span>
                <StatusBadge status={leave.status} />
              </div>
            );
          }) : <p className="muted">No leave</p>}
        </section>
      ))}
    </div>
  );
}

function LeaveTypeChart({ leaves }) {
  const counts = LEAVE_TYPES.map((type) => ({
    type,
    count: leaves.filter((leave) => leave.leave_type === type).length,
  }));
  const max = Math.max(1, ...counts.map((item) => item.count));

  return (
    <Panel title="Leaves by type">
      <div className="chart-list">
        {counts.map((item) => (
          <div className="chart-row" key={item.type}>
            <span>{item.type}</span>
            <div className="chart-track"><span style={{ width: `${(item.count / max) * 100}%` }} /></div>
            <strong>{item.count}</strong>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function LeaveMonthChart({ leaves }) {
  const counts = monthBuckets(leaves).slice(-6);
  const max = Math.max(1, ...counts.map((item) => item.count));

  return (
    <Panel title="Leaves by month">
      <div className="chart-list">
        {counts.map((item) => (
          <div className="chart-row" key={item.month}>
            <span>{item.month}</span>
            <div className="chart-track"><span style={{ width: `${(item.count / max) * 100}%` }} /></div>
            <strong>{item.count}</strong>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function LeaveFilters({ leaves, users, userMap, showExport = false }) {
  const [status, setStatus] = useState("");
  const [query, setQuery] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [reportMonth, setReportMonth] = useState(localDateISO().slice(0, 7));
  const filtered = leaves.filter((leave) => {
    const person = userMap[leave.user_id];
    const haystack = `${person?.name || ""} ${leave.leave_type} ${leave.reason}`.toLowerCase();
    const afterFrom = !from || leave.end_date >= from;
    const beforeTo = !to || leave.start_date <= to;
    return (!status || leave.status === status) && haystack.includes(query.toLowerCase()) && afterFrom && beforeTo;
  });
  return (
    <>
      <div className="filter-row">
        <input placeholder="Search by employee, type, or reason" value={query} onChange={(e) => setQuery(e.target.value)} />
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option>Pending</option>
          <option>Approved</option>
          <option>Rejected</option>
        </select>
        <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        <input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
        <span>{filtered.length} of {leaves.length}</span>
        {showExport && <input type="month" value={reportMonth} onChange={(e) => setReportMonth(e.target.value)} />}
        {showExport && <button className="soft" onClick={() => exportLeavesCsv(monthFilteredLeaves(filtered, reportMonth), userMap, reportMonth)}>Export month CSV</button>}
      </div>
      <LeaveList leaves={filtered} userMap={userMap} />
    </>
  );
}

function TeamPage({ users, leaves, manager, userMap }) {
  const team = users.filter((item) => item.manager_id === manager.id);
  return (
    <DashboardGrid>
      <Panel title="Team members"><PeopleTable users={team} compact /></Panel>
      <Panel title="Team calendar snapshot"><LeaveList leaves={leaves} userMap={userMap} /></Panel>
    </DashboardGrid>
  );
}

function Balances({ quotas, leaves, userMap }) {
  return (
    <DashboardGrid>
      <Panel title="Leave balances">
        <div className="quota-grid">
          {quotas.map((quota) => (
            <div className="quota-card" key={quota.id}>
              <div className="quota-top"><strong>{quota.leave_type}</strong><span>{quota.year}</span></div>
              <div className="meter"><span style={{ width: `${Math.min(100, (quota.remaining_days / quota.total_days) * 100)}%` }} /></div>
              <p>{fmtDays(quota.remaining_days)} remaining of {fmtDays(quota.total_days)}</p>
              <small>{fmtDays(quota.used_days)} used · {fmtDays(quota.pending_days)} pending</small>
            </div>
          ))}
        </div>
      </Panel>
      <Panel title="Balance-impacting requests"><LeaveList leaves={leaves.filter((leave) => leave.status !== "Rejected")} userMap={userMap} /></Panel>
    </DashboardGrid>
  );
}

function SummaryCards({ leaves = [], quotas = [], users = [] }) {
  const pending = leaves.filter((leave) => leave.status === "Pending").length;
  const approved = leaves.filter((leave) => leave.status === "Approved").length;
  const remaining = quotas.reduce((total, quota) => total + Number(quota.remaining_days || 0), 0);
  return (
    <section className="summary-grid">
      <Metric label="Pending" value={pending} />
      <Metric label="Approved" value={approved} />
      <Metric label="People visible" value={users.length || 1} />
      <Metric label="Balance left" value={quotas.length ? remaining.toFixed(1) : "N/A"} />
    </section>
  );
}

function LeaveList({ leaves, userMap }) {
  if (!leaves.length) return <EmptyState title="No requests found" text="There is nothing matching this view yet." />;
  return (
    <div className="stack">
      {leaves.map((leave) => {
        const person = userMap[leave.user_id];
        return (
          <article className="request-card" key={leave.id}>
            <div className="request-main">
              <div><strong>{person?.name || "Your request"}</strong><span>{leave.leave_type} · {formatDate(leave.start_date)} to {formatDate(leave.end_date)}{leave.is_half_day ? " · Half-day" : ""}</span></div>
              <StatusBadge status={leave.status} />
            </div>
            <p>{fmtDays(leave.total_days)} day(s) · {leave.reason}</p>
            {leave.manager_comment && <p className="muted">Manager note: {leave.manager_comment}</p>}
            {leave.ai_parsed_from_text && <p className="ai-chip">AI parsed from: {leave.ai_parsed_from_text}</p>}
          </article>
        );
      })}
    </div>
  );
}

function PeopleTable({ users, currentUser, compact = false }) {
  if (!users.length) return <EmptyState title="No people found" text="The directory is empty for this view." />;
  return (
    <div className="table-wrap">
      <table>
        <thead><tr><th>Name</th><th>Role</th><th>Department</th>{!compact && <th>Email</th>}<th>Status</th></tr></thead>
        <tbody>
          {users.map((person) => (
            <tr key={person.id} className={currentUser?.id === person.id ? "selected-row" : ""}>
              <td><strong>{person.name}</strong><span>{person.employee_id}</span></td>
              <td>{person.role}</td>
              <td>{person.department}</td>
              {!compact && <td>{person.email}</td>}
              <td>{person.is_active ? "Active" : "Inactive"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Profile({ user, users }) {
  const manager = users.find((item) => item.id === user.manager_id);
  return (
    <div className="profile-grid">
      <Metric label="Employee ID" value={user.employee_id} />
      <Metric label="Title" value={user.job_title || user.role} />
      <Metric label="Manager" value={manager?.name || "Not assigned"} />
      <Metric label="Email" value={user.email} />
    </div>
  );
}

function ParserResult({ parsed }) {
  return (
    <div className="insight-block">
      <div className="insight-header"><strong>Parser result</strong><span>{Math.round(parsed.confidence * 100)}% confidence · {parsed.source}</span></div>
      <div className="insight-grid">
        <Metric label="Type" value={parsed.leave_type || "Missing"} />
        <Metric label="Start" value={parsed.start_date || "Missing"} />
        <Metric label="End" value={parsed.end_date || "Missing"} />
        <Metric label="Half-day" value={parsed.is_half_day ? "Yes" : "No"} />
        <Metric label="Days" value={fmtDays(parsed.working_days)} />
      </div>
      {parsed.missing_fields?.length > 0 && <p className="muted">Missing: {parsed.missing_fields.join(", ")}</p>}
    </div>
  );
}

function InsightBlock({ insight }) {
  return (
    <div className="insight-block">
      <div className="insight-header"><strong>AI review</strong><StatusBadge status={insight.risk_level || "medium"} /></div>
      <p>{insight.short_manager_summary || insight.summary}</p>
      <p>{insight.possible_team_conflict || insight.conflicts?.join(", ") || "No conflict data."}</p>
      <p>{insight.leave_balance_impact || "Balance impact unavailable."}</p>
      <strong>{insight.approval_recommendation || insight.recommendation}</strong>
    </div>
  );
}

function Panel({ title, subtitle, action, children }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>
        {action}
      </div>
      {children}
    </section>
  );
}

function Metric({ label, value }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong></div>;
}

function Field({ label, value, onChange, type = "text" }) {
  return <label>{label}<input type={type} value={value} onChange={(e) => onChange(e.target.value)} required /></label>;
}

function StatusBadge({ status }) {
  return <span className={`badge ${String(status).toLowerCase()}`}>{status}</span>;
}

function RefreshButton({ onClick, busy }) {
  return <button className="soft" onClick={() => onClick()} disabled={busy}>{busy ? "Refreshing..." : "Refresh"}</button>;
}

function DashboardGrid({ children }) {
  return <div className="dashboard-grid">{children}</div>;
}

function EmptyState({ title, text }) {
  return <div className="empty-state"><strong>{title}</strong><p>{text}</p></div>;
}

function Loading() {
  return <div className="loading-state"><div className="loader" /><p>Loading your leave workspace...</p></div>;
}

function Brand() {
  return <div className="brand-lockup"><span className="logo-mark">LF</span><span>LeaveFlow</span></div>;
}

function useUserMap(users) {
  return useMemo(() => Object.fromEntries(users.map((item) => [item.id, item])), [users]);
}

function roleTabs(role) {
  if (role === "Admin") return [{ id: "people", label: "People", step: "01" }, { id: "calendar", label: "Calendar", step: "02" }, { id: "requests", label: "Requests", step: "03" }, { id: "create", label: "Create user", step: "04" }];
  if (role === "Manager") return [{ id: "overview", label: "Approvals", step: "01" }, { id: "team", label: "Team", step: "02" }, { id: "calendar", label: "Calendar", step: "03" }, { id: "attendance", label: "Attendance", step: "04" }, { id: "history", label: "History", step: "05" }];
  return [{ id: "overview", label: "Overview", step: "01" }, { id: "request", label: "Request", step: "02" }, { id: "calendar", label: "Calendar", step: "03" }, { id: "balances", label: "Balances", step: "04" }];
}

function titleFor(user) {
  if (!user) return "Leave management";
  if (user.role === "Admin") return "Admin control center";
  if (user.role === "Manager") return "Manager approvals";
  return "Employee leave desk";
}

function formatDate(value) {
  if (!value) return "";
  return new Date(`${value}T00:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function localDateISO(value = new Date()) {
  const offsetDate = new Date(value.getTime() - value.getTimezoneOffset() * 60000);
  return offsetDate.toISOString().slice(0, 10);
}

function calendarRange(range) {
  const today = new Date();
  const current = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const mondayOffset = (current.getDay() + 6) % 7;
  const thisMonday = new Date(current);
  thisMonday.setDate(current.getDate() - mondayOffset);

  const startDate = new Date(thisMonday);
  const endDate = new Date(thisMonday);
  if (range === "next") {
    startDate.setDate(thisMonday.getDate() + 7);
    endDate.setDate(thisMonday.getDate() + 13);
  } else if (range === "both") {
    endDate.setDate(thisMonday.getDate() + 13);
  } else {
    endDate.setDate(thisMonday.getDate() + 6);
  }
  return { start: localDateISO(startDate), end: localDateISO(endDate) };
}

function enumerateDays(start, end) {
  const days = [];
  const cursor = new Date(`${start}T00:00:00`);
  const last = new Date(`${end}T00:00:00`);
  while (cursor <= last) {
    days.push(localDateISO(cursor));
    cursor.setDate(cursor.getDate() + 1);
  }
  return days;
}

function monthBuckets(leaves) {
  const buckets = {};
  leaves.forEach((leave) => {
    const month = String(leave.start_date || "").slice(0, 7);
    if (!month) return;
    buckets[month] = (buckets[month] || 0) + 1;
  });
  return Object.entries(buckets)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([month, count]) => ({ month, count }));
}

function monthFilteredLeaves(leaves, month) {
  if (!month) return leaves;
  const start = `${month}-01`;
  const endDate = new Date(Number(month.slice(0, 4)), Number(month.slice(5, 7)), 0);
  const end = localDateISO(endDate);
  return leaves.filter((leave) => leave.end_date >= start && leave.start_date <= end);
}

function exportLeavesCsv(leaves, userMap, reportMonth = localDateISO().slice(0, 7)) {
  const headers = ["Employee", "Leave Type", "Start Date", "End Date", "Days", "Half Day", "Status", "Reason"];
  const rows = leaves.map((leave) => [
    userMap[leave.user_id]?.name || leave.user_id,
    leave.leave_type,
    leave.start_date,
    leave.end_date,
    fmtDays(leave.total_days),
    leave.is_half_day ? "Yes" : "No",
    leave.status,
    leave.reason,
  ]);
  const csv = [headers, ...rows].map((row) => row.map(csvCell).join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `leave-report-${reportMonth}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

function csvCell(value) {
  return `"${String(value ?? "").replaceAll('"', '""')}"`;
}

function formatTime(value) {
  if (!value) return "";
  return new Date(value).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function fmtDays(value) {
  const number = Number(value || 0);
  return Number.isInteger(number) ? String(number) : number.toFixed(1);
}
