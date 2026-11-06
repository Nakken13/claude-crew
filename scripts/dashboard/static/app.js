const FOLDERS = ["TODO", "CURRENT_TASKS", "PAUSED", "ICEBOX"];
const POLL_MS = 2500;

async function api(path, opts) {
  const res = await fetch(path, opts);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || res.statusText);
  return body;
}

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function renderTasks(tasks) {
  const root = document.getElementById("tasks");
  root.innerHTML = "";
  for (const folder of FOLDERS) {
    const col = el("div", "task-col");
    col.appendChild(el("h3", null, `${folder} (${(tasks[folder] || []).length})`));
    for (const task of tasks[folder] || []) {
      const card = el("div", "card");
      card.appendChild(el("div", "title", task.title));
      const select = document.createElement("select");
      select.appendChild(el("option", null, "Move to…"));
      for (const dest of FOLDERS) {
        if (dest === folder) continue;
        const opt = el("option", null, dest);
        opt.value = dest;
        select.appendChild(opt);
      }
      select.onchange = async () => {
        const to = select.value;
        if (!to) return;
        try {
          await api(`/api/tasks/${encodeURIComponent(task.slug)}/move`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ to }),
          });
          load();
        } catch (e) {
          alert(e.message);
          select.value = "";
        }
      };
      card.appendChild(select);
      col.appendChild(card);
    }
    root.appendChild(col);
  }
}

function renderBatches(batches, warnings, blocking) {
  const alerts = document.getElementById("batch-alerts");
  alerts.innerHTML = "";
  for (const msg of blocking) alerts.appendChild(el("div", "alert blocking", msg));
  for (const msg of warnings) alerts.appendChild(el("div", "alert", msg));

  const root = document.getElementById("batches");
  root.innerHTML = "";
  for (const b of batches) {
    const row = el("div", "batch");
    const badge = el("span", `badge ${b.active ? "active" : "inactive"}`, b.active ? "active" : "inactive");
    row.appendChild(el("strong", null, b.header));
    row.appendChild(badge);
    row.appendChild(el("div", "muted", b.zone_paths.join(", ") || "(zone not declared)"));
    root.appendChild(row);
  }
}

function renderSessions(sessions) {
  const root = document.getElementById("sessions");
  root.innerHTML = "";
  for (const s of sessions) {
    const row = el("div", "session");
    row.appendChild(el("strong", null, s.session_id));
    if (s.stale) row.appendChild(el("span", "badge stale", "stale"));
    row.appendChild(el("div", "muted", `batch: ${s.batch || "-"} · since ${s.since || "?"}`));
    row.appendChild(el("div", "muted", `tasks: ${(s.tasks || []).join(", ") || "-"}`));
    row.appendChild(el("div", "muted", `worktree: ${s.worktree || "-"} · branch: ${s.branch || "-"}`));
    const btn = el("button", "danger", "Purge");
    btn.onclick = async () => {
      if (!confirm(`Purge session ${s.session_id}?`)) return;
      try {
        await api(`/api/sessions/${encodeURIComponent(s.session_id)}/purge`, { method: "POST" });
        load();
      } catch (e) {
        alert(e.message);
      }
    };
    row.appendChild(btn);
    root.appendChild(row);
  }
}

const TEAM_POLL_MS = 30000;
const TEAM_COLUMNS = [["todo", "To do"], ["current", "In progress"]];

function formatAge(min) {
  if (min === null || min === undefined) return "";
  return min < 60 ? `${min} min` : `${Math.floor(min / 60)} h ${String(min % 60).padStart(2, "0")}`;
}

function renderTeam(board) {
  const panel = document.getElementById("team-panel");
  panel.hidden = !board.enabled;
  if (!board.enabled) return;
  document.getElementById("team-status").textContent = board.offline ? "(offline: local view)" : "";
  const root = document.getElementById("team");
  root.innerHTML = "";
  for (const [key, label] of TEAM_COLUMNS) {
    const cards = board.columns[key] || [];
    const col = el("div", "task-col");
    col.appendChild(el("h3", null, `${label} (${cards.length})`));
    for (const c of cards) {
      const card = el("div", "card" + (c.mine ? " mine" : "") + (c.expired ? " expired" : ""));
      card.appendChild(el("div", "title", c.title));
      card.appendChild(el("div", "muted", `${c.mine ? "me" : c.owner || "free"}${c.batch ? " · " + c.batch : ""}`));
      if (c.zone.length) card.appendChild(el("div", "muted", c.zone.join(", ")));
      if (c.age_minutes !== null) {
        card.appendChild(el("div", "muted", c.expired ? `expired (${formatAge(c.age_minutes)})` : `since ${formatAge(c.age_minutes)}`));
      }
      col.appendChild(card);
    }
    root.appendChild(col);
  }
}

async function loadTeam() {
  if (document.hidden) return; // hidden tab: no pointless network fetch every 30 s
  try {
    renderTeam(await api("/api/claims?refresh=1"));
  } catch (e) {
    document.getElementById("team-status").textContent = `error: ${e.message}`;
  }
}

async function load() {
  const statusEl = document.getElementById("status");
  try {
    const state = await api("/api/state");
    renderTasks(state.tasks);
    renderBatches(state.batches, state.batch_warnings, state.batch_blocking);
    renderSessions(state.sessions);
    statusEl.textContent = `updated ${new Date().toLocaleTimeString()}`;
  } catch (e) {
    statusEl.textContent = `error: ${e.message}`;
  }
}

load();
setInterval(load, POLL_MS);
loadTeam();
setInterval(loadTeam, TEAM_POLL_MS);
document.addEventListener("visibilitychange", () => { if (!document.hidden) loadTeam(); });
