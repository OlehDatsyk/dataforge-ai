/* DataForge AI - Frontend application logic (vanilla JS, no build step). */
"use strict";

const state = {
  theme: localStorage.getItem("dfa-theme") || "light",
  datasets: [],
  activeDatasetId: localStorage.getItem("dfa-active-dataset") || null,
  activeDataset: null,
  mainChart: null,
  lastChartRequest: null,
  lastChartData: null,
  exploreTab: "descriptive",
  reportContent: null,
  reportFilename: "dataforge-report",
};

/* ---------------------------------------------------------------------- */
/* Utilities                                                               */
/* ---------------------------------------------------------------------- */

function $(sel, root = document) { return root.querySelector(sel); }
function $all(sel, root = document) { return Array.from(root.querySelectorAll(sel)); }

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

function fmtNum(n, decimals = 2) {
  if (n === null || n === undefined || Number.isNaN(n)) return "-";
  if (typeof n !== "number") return String(n);
  if (Number.isInteger(n)) return n.toLocaleString();
  return n.toLocaleString(undefined, { maximumFractionDigits: decimals });
}

function fmtBytes(bytes) {
  if (bytes === null || bytes === undefined) return "-";
  const units = ["B", "KB", "MB", "GB"];
  let i = 0, v = bytes;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(1)} ${units[i]}`;
}

function fmtDate(iso) {
  if (!iso) return "-";
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

function toast(type, message) {
  const container = $("#toast-container");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = message;
  container.appendChild(el);
  setTimeout(() => el.remove(), 5000);
}

function errorMessage(e) {
  return (e && e.message) ? e.message : "Something went wrong.";
}

function confirmModal(title, body) {
  return new Promise((resolve) => {
    const overlay = $("#confirm-modal");
    $("#confirm-modal-title").textContent = title;
    $("#confirm-modal-body").innerHTML = body;
    overlay.classList.add("active");
    const cleanup = (result) => {
      overlay.classList.remove("active");
      okBtn.removeEventListener("click", onOk);
      cancelBtn.removeEventListener("click", onCancel);
      resolve(result);
    };
    const okBtn = $("#confirm-modal-ok");
    const cancelBtn = $("#confirm-modal-cancel");
    const onOk = () => cleanup(true);
    const onCancel = () => cleanup(false);
    okBtn.addEventListener("click", onOk);
    cancelBtn.addEventListener("click", onCancel);
  });
}

function table(columns, rows, opts = {}) {
  if (!rows || rows.length === 0) {
    return `<div class="empty-state"><div class="icon">📭</div>${opts.emptyText || "No data."}</div>`;
  }
  const head = columns.map((c) => `<th>${escapeHtml(c.label)}</th>`).join("");
  const body = rows.map((row) => {
    const cells = columns.map((c) => `<td>${c.render ? c.render(row) : escapeHtml(row[c.key])}</td>`).join("");
    return `<tr>${cells}</tr>`;
  }).join("");
  return `<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function providerBadge(used, fallback) {
  if (!used) return `<span class="badge badge-warning">No AI provider available</span>`;
  const cls = fallback ? "badge-warning" : "badge-success";
  return `<span class="badge ${cls}">${escapeHtml(used)}${fallback ? " (fallback)" : ""}</span>`;
}

function aiEnvelopeBlock(envelope, opts = {}) {
  if (!envelope) return "";
  if (!envelope.success) {
    return `<div class="alert alert-warning">🤖 ${escapeHtml(envelope.message || "AI explanation unavailable.")}</div>`;
  }
  const meta = `
    <div class="flex small muted" style="margin-bottom:10px; flex-wrap:wrap;">
      <span>Provider: ${providerBadge(envelope.provider_used, envelope.fallback_used)}</span>
      <span>Model: <code>${escapeHtml(envelope.model_used || "-")}</code></span>
      <span>Fallback used: <strong>${envelope.fallback_used ? "Yes" : "No"}</strong></span>
      <span>Processing time: <strong>${fmtNum(envelope.processing_time_ms, 0)} ms</strong></span>
    </div>`;
  return meta;
}

function listBlock(title, items) {
  if (!items || items.length === 0) return "";
  return `<h4 style="margin:14px 0 6px;">${escapeHtml(title)}</h4><ul>${items.map((i) => `<li>${escapeHtml(i)}</li>`).join("")}</ul>`;
}

async function withLoading(button, fn) {
  const original = button.innerHTML;
  button.disabled = true;
  button.innerHTML = `<span class="spinner"></span> Working...`;
  try {
    await fn();
  } catch (e) {
    toast("error", errorMessage(e));
  } finally {
    button.disabled = false;
    button.innerHTML = original;
  }
}

/* ---------------------------------------------------------------------- */
/* Theme                                                                   */
/* ---------------------------------------------------------------------- */

function applyTheme() {
  document.documentElement.setAttribute("data-theme", state.theme);
  $("#theme-toggle").checked = state.theme === "dark";
  $("#theme-toggle-2").checked = state.theme === "dark";
}
function toggleTheme(checked) {
  state.theme = checked ? "dark" : "light";
  localStorage.setItem("dfa-theme", state.theme);
  applyTheme();
}

/* ---------------------------------------------------------------------- */
/* Navigation                                                              */
/* ---------------------------------------------------------------------- */

const VIEW_TITLES = {
  dashboard: "Dashboard", datasets: "Datasets", profile: "Data Profile", cleaning: "Cleaning Workspace",
  explore: "Explore", charts: "Charts", ask: "Ask Your Data", analyst: "AI Data Analyst",
  reports: "Reports", history: "Analysis History", providers: "AI Provider Status", settings: "Settings",
};

function switchView(view) {
  $all(".view").forEach((v) => v.classList.remove("active"));
  $(`#view-${view}`).classList.add("active");
  $all(".nav-item").forEach((n) => n.classList.toggle("active", n.dataset.view === view));
  $("#topbar-title").textContent = VIEW_TITLES[view] || view;

  if (view === "dashboard") loadDashboard();
  if (view === "datasets") refreshDatasetsList();
  if (view === "profile") loadProfile();
  if (view === "cleaning") { renderCleaningForm(); loadCleaningHistory(); }
  if (view === "explore") renderExploreTab(state.exploreTab);
  if (view === "charts") renderChartForm();
  if (view === "history") loadHistory();
  if (view === "providers") loadProviders();
}

function requireDataset() {
  if (!state.activeDatasetId) {
    toast("error", "Please select or upload a dataset first (Datasets tab).");
    return false;
  }
  return true;
}

function updateDatasetPill() {
  const pill = $("#active-dataset-pill");
  if (state.activeDataset) {
    pill.textContent = `📁 ${state.activeDataset.original_filename} (${state.activeDataset.row_count.toLocaleString()} rows)`;
  } else {
    pill.textContent = "No dataset selected";
  }
}

/* ---------------------------------------------------------------------- */
/* Dashboard                                                                */
/* ---------------------------------------------------------------------- */

async function loadDashboard() {
  try {
    const stats = await API.dashboardStats();
    const cards = [
      { label: "Datasets Analysed", value: stats.datasets_analysed, icon: "📁" },
      { label: "Rows Processed", value: stats.rows_processed, icon: "🧮" },
      { label: "Reports Generated", value: stats.reports_generated, icon: "📄" },
      { label: "AI Analyses", value: stats.ai_analyses, icon: "🤖" },
      { label: "Cleaning Operations", value: stats.cleaning_operations, icon: "🧹" },
      { label: "Charts Generated", value: stats.charts_generated, icon: "📈" },
      { label: "Provider Fallbacks", value: stats.provider_fallbacks, icon: "🔀" },
    ];
    $("#dashboard-stats").innerHTML = cards.map((c) => `
      <div class="card stat-card">
        <div class="flex-between"><span class="stat-label">${c.label}</span><span class="stat-icon">${c.icon}</span></div>
        <div class="stat-value">${fmtNum(c.value, 0)}</div>
      </div>`).join("");
  } catch (e) { toast("error", errorMessage(e)); }

  try {
    const datasets = await API.listDatasets();
    $("#dashboard-recent-datasets").innerHTML = datasets.length ? table(
      [
        { key: "original_filename", label: "Dataset" },
        { key: "row_count", label: "Rows", render: (r) => fmtNum(r.row_count, 0) },
        { key: "created_at", label: "Uploaded", render: (r) => fmtDate(r.created_at) },
      ],
      datasets.slice(0, 6)
    ) : `<div class="empty-state small">No datasets uploaded yet.</div>`;
  } catch (e) { /* non-fatal */ }

  try {
    const history = await API.history();
    $("#dashboard-recent-history").innerHTML = history.length ? table(
      [
        { key: "analysis_type", label: "Type" },
        { key: "ai_provider", label: "Provider", render: (r) => r.ai_provider || "-" },
        { key: "created_at", label: "When", render: (r) => fmtDate(r.created_at) },
      ],
      history.slice(0, 6)
    ) : `<div class="empty-state small">No analysis runs yet.</div>`;
  } catch (e) { /* non-fatal */ }
}

/* ---------------------------------------------------------------------- */
/* Datasets                                                                 */
/* ---------------------------------------------------------------------- */

function setupUpload() {
  const dropzone = $("#dropzone");
  const fileInput = $("#file-input");
  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("dragover"); });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length) uploadFile(e.dataTransfer.files[0]);
  });
  fileInput.addEventListener("change", () => {
    if (fileInput.files.length) uploadFile(fileInput.files[0]);
    fileInput.value = "";
  });
}

async function uploadFile(file) {
  const progressEl = $("#upload-progress");
  const resultEl = $("#upload-result");
  resultEl.innerHTML = "";
  progressEl.innerHTML = `
    <div class="progress-steps">
      <span class="step active" id="step-uploading">Uploading</span>
      <span class="step" id="step-loading">Loading</span>
      <span class="step" id="step-profiling">Profiling</span>
      <span class="step" id="step-ready">Ready</span>
    </div>`;
  try {
    const setStep = (id) => { $(`#${id}`).classList.remove("active"); $(`#${id}`).classList.add("done"); };
    setTimeout(() => { setStep("step-uploading"); const l = $("#step-loading"); if (l) l.classList.add("active"); }, 150);
    const data = await API.uploadDataset(file);
    setStep("step-loading");
    const p = $("#step-profiling"); if (p) { p.classList.add("active"); }
    await new Promise((r) => setTimeout(r, 200));
    setStep("step-profiling");
    const rd = $("#step-ready"); if (rd) rd.classList.add("done");

    toast("success", `Dataset "${data.original_filename}" uploaded - ${data.row_count.toLocaleString()} rows, ${data.column_count} columns.`);
    resultEl.innerHTML = `<div class="alert alert-success">Uploaded successfully. Rows: ${data.row_count.toLocaleString()}, Columns: ${data.column_count}.</div>`;
    await refreshDatasetsList();
    selectDataset(data.id);
  } catch (e) {
    progressEl.innerHTML = "";
    resultEl.innerHTML = `<div class="alert alert-danger">${escapeHtml(errorMessage(e))}</div>`;
    toast("error", errorMessage(e));
  }
}

async function refreshDatasetsList() {
  try {
    state.datasets = await API.listDatasets();
    $("#datasets-table").innerHTML = state.datasets.length ? table(
      [
        { key: "original_filename", label: "Filename" },
        { key: "file_type", label: "Type", render: (r) => `<span class="badge badge-info">${r.file_type.toUpperCase()}</span>` },
        { key: "row_count", label: "Rows", render: (r) => fmtNum(r.row_count, 0) },
        { key: "column_count", label: "Cols" },
        { key: "file_size_bytes", label: "Size", render: (r) => fmtBytes(r.file_size_bytes) },
        { key: "created_at", label: "Uploaded", render: (r) => fmtDate(r.created_at) },
        {
          key: "actions", label: "Actions", render: (r) => `
          <div class="btn-group">
            <button class="btn btn-sm" onclick="selectDataset('${r.id}')">${state.activeDatasetId === r.id ? "✓ Selected" : "Select"}</button>
            <button class="btn btn-sm btn-danger" onclick="deleteDatasetPrompt('${r.id}')">Delete</button>
          </div>`,
        },
      ],
      state.datasets
    ) : `<div class="empty-state"><div class="icon">📭</div>No datasets yet. Upload one above to get started.</div>`;
  } catch (e) { toast("error", errorMessage(e)); }
}

async function selectDataset(id) {
  try {
    const data = await API.getDataset(id);
    state.activeDatasetId = id;
    state.activeDataset = data;
    localStorage.setItem("dfa-active-dataset", id);
    updateDatasetPill();
    renderDatasetOverview(data);
    refreshDatasetsList();
  } catch (e) { toast("error", errorMessage(e)); }
}

function renderDatasetOverview(data) {
  const panel = $("#dataset-overview-panel");
  panel.style.display = "block";
  const numeric = Object.entries(data.dtypes).filter(([, t]) => t === "numeric").map(([c]) => c);
  const text = Object.entries(data.dtypes).filter(([, t]) => t === "text").map(([c]) => c);
  const date = Object.entries(data.dtypes).filter(([, t]) => t === "date").map(([c]) => c);
  $("#dataset-overview").innerHTML = `
    <div class="grid grid-4" style="margin-bottom:16px;">
      <div class="card stat-card"><div class="stat-label">Rows</div><div class="stat-value">${fmtNum(data.row_count, 0)}</div></div>
      <div class="card stat-card"><div class="stat-label">Columns</div><div class="stat-value">${data.column_count}</div></div>
      <div class="card stat-card"><div class="stat-label">File Size</div><div class="stat-value" style="font-size:20px;">${fmtBytes(data.file_size_bytes)}</div></div>
      <div class="card stat-card"><div class="stat-label">File Type</div><div class="stat-value" style="font-size:20px;">${data.file_type.toUpperCase()}</div></div>
    </div>
    <p><strong>Numeric columns:</strong> ${numeric.map(escapeHtml).join(", ") || "none"}</p>
    <p><strong>Text columns:</strong> ${text.map(escapeHtml).join(", ") || "none"}</p>
    <p><strong>Date columns:</strong> ${date.map(escapeHtml).join(", ") || "none"}</p>
    <h4>Sample Rows (first ${data.sample_rows.length})</h4>
    ${table(data.columns.map((c) => ({ key: c, label: c })), data.sample_rows)}
    <div class="btn-group" style="margin-top:12px;">
      <a class="btn btn-sm" href="${API.exportCsvUrl(data.id)}">⬇ Export CSV</a>
      <a class="btn btn-sm" href="${API.exportXlsxUrl(data.id)}">⬇ Export Excel</a>
    </div>
  `;
}

async function deleteDatasetPrompt(id) {
  const ok = await confirmModal("Delete dataset?", "This permanently removes the dataset, its working copy, and all related history. This cannot be undone.");
  if (!ok) return;
  try {
    await API.deleteDataset(id);
    if (state.activeDatasetId === id) { state.activeDatasetId = null; state.activeDataset = null; localStorage.removeItem("dfa-active-dataset"); updateDatasetPill(); $("#dataset-overview-panel").style.display = "none"; }
    toast("success", "Dataset deleted.");
    refreshDatasetsList();
  } catch (e) { toast("error", errorMessage(e)); }
}

/* ---------------------------------------------------------------------- */
/* Profile                                                                  */
/* ---------------------------------------------------------------------- */

async function loadProfile() {
  const el = $("#profile-content");
  if (!requireDataset()) { el.innerHTML = `<div class="empty-state"><div class="icon">🔍</div>Select a dataset first.</div>`; return; }
  el.innerHTML = `<div class="empty-state"><span class="spinner"></span> Loading profile...</div>`;
  try {
    const profile = await API.getProfile(state.activeDatasetId);
    const summaryCards = `
      <div class="grid grid-4" style="margin-bottom:18px;">
        <div class="card stat-card"><div class="stat-label">Rows</div><div class="stat-value">${fmtNum(profile.row_count, 0)}</div></div>
        <div class="card stat-card"><div class="stat-label">Columns</div><div class="stat-value">${profile.column_count}</div></div>
        <div class="card stat-card"><div class="stat-label">Duplicate Rows</div><div class="stat-value">${fmtNum(profile.duplicate_rows, 0)} <span class="small muted">(${profile.duplicate_pct}%)</span></div></div>
        <div class="card stat-card"><div class="stat-label">Missing Values</div><div class="stat-value">${fmtNum(profile.total_missing_values, 0)} <span class="small muted">(${profile.total_missing_pct}%)</span></div></div>
      </div>`;
    const rows = profile.columns.map((c) => {
      let extra = "";
      if (c.type === "numeric") {
        extra = `mean ${fmtNum(c.mean)} · median ${fmtNum(c.median)} · min ${fmtNum(c.min)} · max ${fmtNum(c.max)} · std ${fmtNum(c.std)} · p25 ${fmtNum(c.p25)} · p75 ${fmtNum(c.p75)}`;
      } else if (c.type === "date") {
        extra = `earliest ${escapeHtml(c.earliest_date || "-")} · latest ${escapeHtml(c.latest_date || "-")} · range ${c.range_days ?? "-"} days`;
      } else {
        const top = (c.most_common_values || []).map((v) => `${escapeHtml(v.value)} (${v.count})`).join(", ");
        extra = `top values: ${top || "-"}${c.avg_length ? ` · avg length ${fmtNum(c.avg_length)}` : ""}`;
      }
      return { ...c, extra };
    });
    const columnsTable = table(
      [
        { key: "name", label: "Column" },
        { key: "type", label: "Type", render: (r) => `<span class="badge badge-info">${r.type}</span>` },
        { key: "non_null_count", label: "Non-null" },
        { key: "missing_count", label: "Missing", render: (r) => `${r.missing_count} (${r.missing_pct}%)` },
        { key: "unique_values", label: "Unique" },
        { key: "extra", label: "Statistics", render: (r) => `<span class="small">${r.extra}</span>` },
      ],
      rows
    );
    el.innerHTML = summaryCards + `<div class="panel"><div class="panel-title">Column Profile</div>${columnsTable}</div>`;
  } catch (e) {
    el.innerHTML = `<div class="alert alert-danger">${escapeHtml(errorMessage(e))}</div>`;
  }
}

/* ---------------------------------------------------------------------- */
/* Cleaning                                                                  */
/* ---------------------------------------------------------------------- */

const CLEANING_OPS = [
  { value: "remove_duplicates", label: "Remove duplicate rows", needsColumn: false },
  { value: "drop_missing", label: "Drop rows with missing values", needsColumn: "optional" },
  { value: "fill_missing_numeric", label: "Fill missing numeric values", needsColumn: true, params: [{ key: "strategy", label: "Strategy", options: ["median", "mean", "mode"] }] },
  { value: "fill_missing_categorical", label: "Fill missing categorical values", needsColumn: true, params: [{ key: "strategy", label: "Strategy", options: ["mode", "constant"] }] },
  { value: "rename_column", label: "Rename column", needsColumn: true, params: [{ key: "new_name", label: "New name", type: "text" }] },
  { value: "trim_whitespace", label: "Trim whitespace", needsColumn: "optional" },
  { value: "standardize_case", label: "Standardize text case", needsColumn: true, params: [{ key: "case", label: "Case", options: ["lower", "upper", "title"] }] },
  { value: "convert_dtype", label: "Convert data type", needsColumn: true, params: [{ key: "target_type", label: "Target type", options: ["numeric", "string", "boolean"] }] },
  { value: "parse_dates", label: "Parse dates", needsColumn: true },
];

function renderCleaningForm() {
  const el = $("#cleaning-form");
  if (!requireDataset()) { el.innerHTML = `<div class="empty-state small">Select a dataset first.</div>`; return; }
  const columns = state.activeDataset.columns;
  el.innerHTML = `
    <div class="form-row">
      <label>Operation</label>
      <select id="clean-op">${CLEANING_OPS.map((o) => `<option value="${o.value}">${o.label}</option>`).join("")}</select>
    </div>
    <div class="form-row" id="clean-column-row">
      <label>Column</label>
      <select id="clean-column"><option value="">(none)</option>${columns.map((c) => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join("")}</select>
    </div>
    <div id="clean-params-row"></div>
    <button class="btn btn-primary" id="apply-clean-btn">Apply Operation (requires confirmation)</button>
  `;
  const opSelect = $("#clean-op");
  const paramsRow = $("#clean-params-row");
  function renderParams() {
    const op = CLEANING_OPS.find((o) => o.value === opSelect.value);
    paramsRow.innerHTML = (op.params || []).map((p) => {
      if (p.options) {
        return `<div class="form-row"><label>${p.label}</label><select id="param-${p.key}">${p.options.map((v) => `<option value="${v}">${v}</option>`).join("")}</select></div>`;
      }
      return `<div class="form-row"><label>${p.label}</label><input type="text" id="param-${p.key}" /></div>`;
    }).join("");
  }
  renderParams();
  opSelect.addEventListener("change", renderParams);
  $("#apply-clean-btn").addEventListener("click", applyCleaningOperation);
}

async function applyCleaningOperation() {
  if (!requireDataset()) return;
  const operation = $("#clean-op").value;
  const opDef = CLEANING_OPS.find((o) => o.value === operation);
  const column = $("#clean-column").value || null;
  if (opDef.needsColumn === true && !column) {
    toast("error", "This operation requires a column.");
    return;
  }
  const params = {};
  (opDef.params || []).forEach((p) => { const input = $(`#param-${p.key}`); if (input) params[p.key] = input.value; });

  const ok = await confirmModal(
    "Confirm cleaning operation",
    `Apply <strong>${escapeHtml(opDef.label)}</strong>${column ? ` to column <strong>${escapeHtml(column)}</strong>` : ""}? This modifies your working dataset (the original upload stays untouched, and can be restored anytime with "Reset to Original").`
  );
  if (!ok) return;

  const btn = $("#apply-clean-btn");
  await withLoading(btn, async () => {
    const result = await API.cleanDataset(state.activeDatasetId, { operation, column, params, confirm: true });
    toast("success", `Applied "${opDef.label}". Rows: ${result.rows_before} -> ${result.rows_after}.`);
    state.activeDataset = await API.getDataset(state.activeDatasetId);
    updateDatasetPill();
    loadCleaningHistory();
    $("#cleaning-preview").innerHTML = `<h4>Preview after operation</h4>` + table(
      state.activeDataset.columns.map((c) => ({ key: c, label: c })), result.sample_rows
    );
  });
}

async function loadCleaningHistory() {
  const el = $("#cleaning-history");
  if (!requireDataset()) { el.innerHTML = `<div class="empty-state small">Select a dataset first.</div>`; return; }
  try {
    const ops = await API.cleaningHistory(state.activeDatasetId);
    el.innerHTML = table(
      [
        { key: "created_at", label: "When", render: (r) => fmtDate(r.created_at) },
        { key: "operation", label: "Operation" },
        { key: "column", label: "Column", render: (r) => r.column || "-" },
        { key: "rows_before", label: "Rows Before" },
        { key: "rows_after", label: "Rows After" },
        { key: "rows_affected", label: "Rows Affected" },
      ],
      ops,
      { emptyText: "No cleaning operations applied yet." }
    );
  } catch (e) { toast("error", errorMessage(e)); }
}

async function resetDataset() {
  if (!requireDataset()) return;
  const ok = await confirmModal("Reset to original?", "This discards all cleaning operations and restores the working dataset to exactly what was originally uploaded.");
  if (!ok) return;
  try {
    await API.resetDataset(state.activeDatasetId);
    toast("success", "Working dataset reset to original.");
    state.activeDataset = await API.getDataset(state.activeDatasetId);
    updateDatasetPill();
    loadCleaningHistory();
    $("#cleaning-preview").innerHTML = "";
  } catch (e) { toast("error", errorMessage(e)); }
}

async function aiCleaningSuggestions() {
  if (!requireDataset()) return;
  const el = $("#ai-cleaning-suggestions");
  el.innerHTML = `<span class="spinner"></span> Asking AI for suggestions...`;
  try {
    const provider = "auto";
    const res = await API.cleaningSuggestions(state.activeDatasetId, { provider });
    const env = res.ai_result;
    if (!env.success) { el.innerHTML = aiEnvelopeBlock(env); return; }
    const suggestions = env.data.suggestions || [];
    el.innerHTML = aiEnvelopeBlock(env) + (suggestions.length ? suggestions.map((s) => `
      <div class="finding-card">
        <strong>${escapeHtml(s.column)}</strong> - ${escapeHtml(s.issue)}<br/>
        <span class="small">Suggested: <code>${escapeHtml(s.suggestion)}</code></span><br/>
        <span class="small muted">${escapeHtml(s.rationale)}</span>
      </div>`).join("") : `<p class="small muted">No specific suggestions returned.</p>`);
  } catch (e) {
    el.innerHTML = `<div class="alert alert-danger">${escapeHtml(errorMessage(e))}</div>`;
  }
}

/* ---------------------------------------------------------------------- */
/* Explore                                                                   */
/* ---------------------------------------------------------------------- */

function renderExploreTab(tab) {
  state.exploreTab = tab;
  $all("#explore-tabs .tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  const el = $("#explore-panels");
  if (!requireDataset()) { el.innerHTML = `<div class="empty-state"><div class="icon">🧮</div>Select a dataset first.</div>`; return; }

  const cols = state.activeDataset.columns;
  const numericCols = Object.entries(state.activeDataset.dtypes).filter(([, t]) => t === "numeric").map(([c]) => c);
  const dateCols = Object.entries(state.activeDataset.dtypes).filter(([, t]) => t === "date").map(([c]) => c);
  const opts = (arr) => arr.map((c) => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join("");

  const renderers = {
    descriptive: () => `<button class="btn btn-primary" onclick="runDescriptive()">Run Descriptive Statistics</button><div id="explore-result"></div>`,
    missing: () => `<button class="btn btn-primary" onclick="runMissing()">Run Missing Value Analysis</button><div id="explore-result"></div>`,
    duplicates: () => `<button class="btn btn-primary" onclick="runDuplicates()">Run Duplicate Detection</button><div id="explore-result"></div>`,
    outliers: () => `
      <div class="form-grid">
        <div><label>Method</label><select id="outlier-method"><option value="iqr">IQR</option><option value="zscore">Z-score</option></select></div>
        <div><label>Threshold</label><input type="number" id="outlier-threshold" value="1.5" step="0.1" /></div>
      </div>
      <button class="btn btn-primary" onclick="runOutliers()">Run Outlier Detection</button><div id="explore-result"></div>`,
    correlation: () => `
      <div class="form-grid">
        <div><label>Threshold</label><input type="number" id="corr-threshold" value="0.5" step="0.05" min="0" max="1" /></div>
      </div>
      <button class="btn btn-primary" onclick="runCorrelation()">Run Correlation Analysis</button><div id="explore-result"></div>`,
    category: () => `
      <div class="form-grid">
        <div><label>Column</label><select id="cat-column">${opts(cols)}</select></div>
      </div>
      <button class="btn btn-primary" onclick="runCategory()">Run Category Analysis</button><div id="explore-result"></div>`,
    group: () => `
      <div class="form-grid">
        <div><label>Group by</label><select id="group-by">${opts(cols)}</select></div>
        <div><label>Metric</label><select id="group-metric">${opts(numericCols)}</select></div>
        <div><label>Aggregation</label><select id="group-agg"><option value="sum">Sum</option><option value="mean">Average</option><option value="median">Median</option><option value="count">Count</option><option value="min">Min</option><option value="max">Max</option></select></div>
      </div>
      <button class="btn btn-primary" onclick="runGroup()">Run Grouped Analysis</button><div id="explore-result"></div>`,
    timeseries: () => dateCols.length ? `
      <div class="form-grid">
        <div><label>Date column</label><select id="ts-date">${opts(dateCols)}</select></div>
        <div><label>Value column</label><select id="ts-value">${opts(numericCols)}</select></div>
        <div><label>Frequency</label><select id="ts-freq"><option value="daily">Daily</option><option value="weekly">Weekly</option><option value="monthly" selected>Monthly</option><option value="quarterly">Quarterly</option><option value="yearly">Yearly</option></select></div>
        <div><label>Aggregation</label><select id="ts-agg"><option value="sum">Sum</option><option value="mean">Average</option><option value="count">Count</option><option value="min">Min</option><option value="max">Max</option></select></div>
      </div>
      <button class="btn btn-primary" onclick="runTimeseries()">Run Time-Series Analysis</button><div id="explore-result"></div>`
      : `<div class="empty-state small">No date columns detected in this dataset.</div>`,
    kpi: () => `
      <div class="form-grid">
        <div><label>Metric column</label><select id="kpi-metric">${opts(numericCols)}</select></div>
        <div><label>Aggregation</label><select id="kpi-agg"><option value="sum">Sum</option><option value="mean">Average</option><option value="count">Count</option><option value="median">Median</option><option value="min">Min</option><option value="max">Max</option></select></div>
        <div><label>Group by (optional)</label><select id="kpi-group"><option value="">(none)</option>${opts(cols)}</select></div>
        <div><label>Target (optional)</label><input type="number" id="kpi-target" /></div>
      </div>
      <button class="btn btn-primary" onclick="runKpi()">Run KPI Analysis</button><div id="explore-result"></div>`,
  };
  el.innerHTML = `<div class="panel">${renderers[tab] ? renderers[tab]() : ""}</div>`;
}

async function runDescriptive() {
  const res = $("#explore-result");
  res.innerHTML = `<span class="spinner"></span>`;
  try {
    const data = await API.descriptive(state.activeDatasetId);
    const rows = Object.entries(data.statistics).map(([col, s]) => ({ column: col, ...s }));
    res.innerHTML = table(
      [
        { key: "column", label: "Column" }, { key: "count", label: "Count" },
        { key: "mean", label: "Mean", render: (r) => fmtNum(r.mean) }, { key: "median", label: "Median", render: (r) => fmtNum(r.median) },
        { key: "min", label: "Min", render: (r) => fmtNum(r.min) }, { key: "max", label: "Max", render: (r) => fmtNum(r.max) },
        { key: "std", label: "Std Dev", render: (r) => fmtNum(r.std) }, { key: "sum", label: "Sum", render: (r) => fmtNum(r.sum) },
        { key: "p25", label: "P25", render: (r) => fmtNum(r.p25) }, { key: "p75", label: "P75", render: (r) => fmtNum(r.p75) },
      ],
      rows
    );
  } catch (e) { res.innerHTML = `<div class="alert alert-danger">${escapeHtml(errorMessage(e))}</div>`; }
}

async function runMissing() {
  const res = $("#explore-result");
  res.innerHTML = `<span class="spinner"></span>`;
  try {
    const data = await API.missing(state.activeDatasetId);
    res.innerHTML = `<div class="alert alert-info">${data.note}</div>` + table(
      [
        { key: "column", label: "Column" }, { key: "missing_count", label: "Missing Count" },
        { key: "missing_pct", label: "Missing %", render: (r) => `${r.missing_pct}%` },
        { key: "recommendation", label: "Recommendation", render: (r) => `<span class="badge badge-info">${r.recommendation.replace(/_/g, " ")}</span>` },
      ],
      data.columns
    );
  } catch (e) { res.innerHTML = `<div class="alert alert-danger">${escapeHtml(errorMessage(e))}</div>`; }
}

async function runDuplicates() {
  const res = $("#explore-result");
  res.innerHTML = `<span class="spinner"></span>`;
  try {
    const data = await API.duplicates(state.activeDatasetId);
    let html = `<div class="alert ${data.duplicate_count ? "alert-warning" : "alert-success"}">Duplicate rows: <strong>${data.duplicate_count}</strong> (${data.duplicate_pct}%)</div>`;
    if (data.preview.length) {
      const cols = Object.keys(data.preview[0]);
      html += table(cols.map((c) => ({ key: c, label: c })), data.preview);
    }
    res.innerHTML = html;
  } catch (e) { res.innerHTML = `<div class="alert alert-danger">${escapeHtml(errorMessage(e))}</div>`; }
}

async function runOutliers() {
  const res = $("#explore-result");
  res.innerHTML = `<span class="spinner"></span>`;
  try {
    const method = $("#outlier-method").value;
    const threshold = parseFloat($("#outlier-threshold").value) || 1.5;
    const data = await API.outliers(state.activeDatasetId, { method, threshold });
    res.innerHTML = table(
      [
        { key: "column", label: "Column" }, { key: "outlier_count", label: "Outlier Count" },
        { key: "outlier_pct", label: "Outlier %", render: (r) => `${r.outlier_pct}%` },
        { key: "lower_bound", label: "Lower Bound", render: (r) => fmtNum(r.lower_bound) },
        { key: "upper_bound", label: "Upper Bound", render: (r) => fmtNum(r.upper_bound) },
        { key: "example_values", label: "Examples", render: (r) => (r.example_values || []).map((v) => fmtNum(v)).join(", ") || "-" },
      ],
      data.results
    );
  } catch (e) { res.innerHTML = `<div class="alert alert-danger">${escapeHtml(errorMessage(e))}</div>`; }
}

async function runCorrelation() {
  const res = $("#explore-result");
  res.innerHTML = `<span class="spinner"></span>`;
  try {
    const threshold = parseFloat($("#corr-threshold").value) || 0.5;
    const data = await API.correlation(state.activeDatasetId, { threshold });
    let html = `<div class="alert alert-info">${data.disclaimer || data.note || ""}</div>`;
    html += `<h4>Strong Positive Correlations (≥ ${threshold})</h4>` + table(
      [{ key: "column_a", label: "Column A" }, { key: "column_b", label: "Column B" }, { key: "correlation", label: "Correlation", render: (r) => fmtNum(r.correlation, 3) }],
      data.strong_positive, { emptyText: "None above threshold." }
    );
    html += `<h4>Strong Negative Correlations (≤ -${threshold})</h4>` + table(
      [{ key: "column_a", label: "Column A" }, { key: "column_b", label: "Column B" }, { key: "correlation", label: "Correlation", render: (r) => fmtNum(r.correlation, 3) }],
      data.strong_negative, { emptyText: "None below threshold." }
    );
    html += `<h4>Weak / Other Relationships</h4>` + table(
      [{ key: "column_a", label: "Column A" }, { key: "column_b", label: "Column B" }, { key: "correlation", label: "Correlation", render: (r) => fmtNum(r.correlation, 3) }],
      data.weak_relationships, { emptyText: "None." }
    );
    res.innerHTML = html;
  } catch (e) { res.innerHTML = `<div class="alert alert-danger">${escapeHtml(errorMessage(e))}</div>`; }
}

async function runCategory() {
  const res = $("#explore-result");
  res.innerHTML = `<span class="spinner"></span>`;
  try {
    const column = $("#cat-column").value;
    const data = await API.category(state.activeDatasetId, column);
    let html = `<p>Unique categories: <strong>${data.unique_categories}</strong></p>`;
    html += `<h4>Top Categories</h4>` + table(
      [{ key: "value", label: "Value" }, { key: "count", label: "Count" }, { key: "pct", label: "%", render: (r) => `${r.pct}%` }],
      data.top_categories
    );
    if (data.rare_categories.length) {
      html += `<h4>Rare Categories (&lt;1%)</h4>` + table(
        [{ key: "value", label: "Value" }, { key: "count", label: "Count" }, { key: "pct", label: "%", render: (r) => `${r.pct}%` }],
        data.rare_categories
      );
    }
    res.innerHTML = html;
  } catch (e) { res.innerHTML = `<div class="alert alert-danger">${escapeHtml(errorMessage(e))}</div>`; }
}

async function runGroup() {
  const res = $("#explore-result");
  res.innerHTML = `<span class="spinner"></span>`;
  try {
    const group_by = $("#group-by").value, metric = $("#group-metric").value, aggregation = $("#group-agg").value;
    const data = await API.group(state.activeDatasetId, { group_by, metric, aggregation });
    res.innerHTML = `<p>${data.group_count} groups · metric: <strong>${escapeHtml(data.metric)}</strong> (${escapeHtml(data.aggregation)})</p>` + table(
      [{ key: "group", label: escapeHtml(group_by) }, { key: "value", label: "Value", render: (r) => fmtNum(r.value) }],
      data.groups
    );
  } catch (e) { res.innerHTML = `<div class="alert alert-danger">${escapeHtml(errorMessage(e))}</div>`; }
}

async function runTimeseries() {
  const res = $("#explore-result");
  res.innerHTML = `<span class="spinner"></span>`;
  try {
    const date_column = $("#ts-date").value, value_column = $("#ts-value").value;
    const frequency = $("#ts-freq").value, aggregation = $("#ts-agg").value;
    const data = await API.timeseries(state.activeDatasetId, { date_column, value_column, frequency, aggregation });
    let html = `<div class="alert alert-info">${data.note}</div>`;
    html += `<p>Peak: <strong>${data.peak_period ? `${data.peak_period.period} (${fmtNum(data.peak_period.value)})` : "-"}</strong> · `;
    html += `Trough: <strong>${data.trough_period ? `${data.trough_period.period} (${fmtNum(data.trough_period.value)})` : "-"}</strong> · `;
    html += `Overall change: <strong>${data.overall_change_pct !== null ? data.overall_change_pct + "%" : "-"}</strong></p>`;
    html += table([{ key: "period", label: "Period" }, { key: "value", label: "Value", render: (r) => fmtNum(r.value) }], data.points);
    res.innerHTML = html;
  } catch (e) { res.innerHTML = `<div class="alert alert-danger">${escapeHtml(errorMessage(e))}</div>`; }
}

async function runKpi() {
  const res = $("#explore-result");
  res.innerHTML = `<span class="spinner"></span>`;
  try {
    const metric_column = $("#kpi-metric").value, aggregation = $("#kpi-agg").value;
    const group_by = $("#kpi-group").value || null;
    const targetVal = $("#kpi-target").value;
    const target = targetVal ? parseFloat(targetVal) : null;
    const data = await API.kpi(state.activeDatasetId, { metric_column, aggregation, group_by, target });
    let html = `<div class="grid grid-3">
      <div class="card stat-card"><div class="stat-label">Current Value</div><div class="stat-value">${fmtNum(data.current_value)}</div></div>
      <div class="card stat-card"><div class="stat-label">Target</div><div class="stat-value">${data.target !== null && data.target !== undefined ? fmtNum(data.target) : "-"}</div></div>
      <div class="card stat-card"><div class="stat-label">% to Target</div><div class="stat-value">${data.pct_to_target !== undefined && data.pct_to_target !== null ? data.pct_to_target + "%" : "-"}</div></div>
    </div>`;
    if (data.breakdown) html += `<h4>Breakdown</h4>` + table([{ key: "group", label: "Group" }, { key: "value", label: "Value", render: (r) => fmtNum(r.value) }], data.breakdown);
    res.innerHTML = html;
  } catch (e) { res.innerHTML = `<div class="alert alert-danger">${escapeHtml(errorMessage(e))}</div>`; }
}

/* ---------------------------------------------------------------------- */
/* Charts                                                                    */
/* ---------------------------------------------------------------------- */

const CHART_COLORS = ["#4f46e5", "#0891b2", "#16a34a", "#d97706", "#dc2626", "#7c3aed", "#0ea5e9", "#65a30d"];

function renderChartForm() {
  const el = $("#chart-form-panel");
  if (!requireDataset()) { el.innerHTML = `<div class="empty-state small">Select a dataset first.</div>`; return; }
  const cols = state.activeDataset.columns;
  const opts = (arr) => arr.map((c) => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join("");
  el.innerHTML = `
    <div class="form-grid">
      <div><label>Chart type</label><select id="chart-type">
        <option value="bar">Bar</option><option value="line">Line</option><option value="pie">Pie</option>
        <option value="scatter">Scatter</option><option value="histogram">Histogram</option><option value="box">Box Plot</option>
      </select></div>
      <div><label>X-axis / column</label><select id="chart-x">${opts(cols)}</select></div>
      <div><label>Y-axis (optional)</label><select id="chart-y"><option value="">(none)</option>${opts(cols)}</select></div>
      <div><label>Aggregation</label><select id="chart-agg"><option value="count">Count</option><option value="sum">Sum</option><option value="mean">Average</option><option value="median">Median</option><option value="min">Min</option><option value="max">Max</option></select></div>
      <div><label>Group by (optional)</label><select id="chart-group"><option value="">(none)</option>${opts(cols)}</select></div>
      <div><label>Bins (histogram)</label><input type="number" id="chart-bins" value="10" min="2" max="50" /></div>
    </div>
    <button class="btn btn-primary" id="generate-chart-btn">Generate Chart</button>
  `;
  $("#generate-chart-btn").addEventListener("click", generateChart);
}

async function generateChart() {
  if (!requireDataset()) return;
  const body = {
    chart_type: $("#chart-type").value,
    x: $("#chart-x").value || null,
    y: $("#chart-y").value || null,
    aggregation: $("#chart-agg").value,
    group_by: $("#chart-group").value || null,
    bins: parseInt($("#chart-bins").value, 10) || 10,
  };
  try {
    const data = await API.chart(state.activeDatasetId, body);
    state.lastChartRequest = body;
    state.lastChartData = data;
    $("#chart-empty").style.display = "none";
    renderChartCanvas(data);
    $("#explain-chart-btn").disabled = false;
    $("#chart-explanation-panel").style.display = "none";
  } catch (e) { toast("error", errorMessage(e)); }
}

function renderChartCanvas(data) {
  const ctx = $("#main-chart").getContext("2d");
  if (state.mainChart) { state.mainChart.destroy(); }

  let type = data.chart_type;
  let chartJsType = { bar: "bar", line: "line", pie: "pie", scatter: "scatter", histogram: "bar", box: "bar" }[type] || "bar";

  let datasets, labels = data.labels || [];
  if (type === "scatter") {
    datasets = data.datasets.map((ds, i) => ({ label: ds.label, data: ds.data, backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }));
  } else if (type === "box") {
    // Render box plot summary as a simple bar range chart (min-max) since Chart.js core has no boxplot type.
    const d = data.datasets[0].data[0];
    labels = ["Min-Q1", "Q1-Median", "Median-Q3", "Q3-Max"];
    datasets = [{
      label: data.datasets[0].label,
      data: [d.q1 - d.min, d.median - d.q1, d.q3 - d.median, d.max - d.q3],
      backgroundColor: CHART_COLORS.slice(0, 4),
    }];
    type = "bar";
  } else {
    datasets = data.datasets.map((ds, i) => ({
      label: ds.label, data: ds.data,
      backgroundColor: type === "pie" ? CHART_COLORS : CHART_COLORS[i % CHART_COLORS.length],
      borderColor: CHART_COLORS[i % CHART_COLORS.length],
      fill: type === "line" ? false : true,
    }));
  }

  state.mainChart = new Chart(ctx, {
    type: chartJsType,
    data: { labels, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: datasets.length > 1 || type === "pie" }, title: { display: true, text: `${data.x_label || ""}${data.y_label ? " vs " + data.y_label : ""}` } },
      scales: type === "pie" ? {} : { x: { title: { display: true, text: data.x_label || "" } }, y: { title: { display: true, text: data.y_label || "" } } },
    },
  });
}

async function explainChart() {
  if (!state.lastChartRequest) return;
  const panel = $("#chart-explanation-panel");
  const el = $("#chart-explanation");
  panel.style.display = "block";
  el.innerHTML = `<span class="spinner"></span> Asking AI to explain the chart...`;
  try {
    const body = { ...state.lastChartRequest, provider: "auto", chart_data: state.lastChartData };
    const res = await API.explainChart(state.activeDatasetId, body);
    const env = res.ai_result;
    if (!env.success) { el.innerHTML = aiEnvelopeBlock(env); return; }
    const d = env.data;
    el.innerHTML = aiEnvelopeBlock(env) + `
      <p><strong>Main pattern:</strong> ${escapeHtml(d.main_pattern)}</p>
      <p><strong>Largest values:</strong> ${escapeHtml(d.largest_values)}</p>
      <p><strong>Smallest values:</strong> ${escapeHtml(d.smallest_values)}</p>
      <p><strong>Trend:</strong> ${escapeHtml(d.trend)}</p>
      <p><strong>Interpretation:</strong> ${escapeHtml(d.interpretation)}</p>
      <p class="muted small"><strong>Limitations:</strong> ${escapeHtml(d.limitations)}</p>
    `;
  } catch (e) { el.innerHTML = `<div class="alert alert-danger">${escapeHtml(errorMessage(e))}</div>`; }
}

/* ---------------------------------------------------------------------- */
/* Ask Your Data                                                             */
/* ---------------------------------------------------------------------- */

async function askQuestion() {
  if (!requireDataset()) return;
  const question = $("#ask-input").value.trim();
  if (!question) { toast("error", "Please enter a question."); return; }
  const provider = $("#ask-provider").value;
  const resultEl = $("#ask-result");
  resultEl.innerHTML = `<div class="panel"><span class="spinner"></span> Calculating...</div>`;
  try {
    const res = await API.ask(state.activeDatasetId, { question, provider });
    const calc = res.calculated_result;
    const env = res.ai_explanation;
    let calcHtml = `<div class="panel"><div class="panel-title">Calculated Result <span class="badge badge-success">Verified - pandas</span></div>`;
    if (calc.result !== undefined) {
      calcHtml += `<div class="stat-value" style="font-size:32px;">${fmtNum(calc.result)}</div>`;
    } else if (calc.result_group !== undefined) {
      calcHtml += `<div class="stat-value" style="font-size:26px;">${escapeHtml(calc.result_group)} - ${fmtNum(calc.result_value)}</div>`;
    }
    if (calc.full_breakdown) {
      calcHtml += table([{ key: "group", label: "Group" }, { key: "value", label: "Value", render: (r) => fmtNum(r.value) }], calc.full_breakdown);
    }
    calcHtml += `<p class="small muted">${escapeHtml(calc.explanation_basis)}</p></div>`;

    let aiHtml = `<div class="panel"><div class="panel-title">AI Explanation</div>`;
    if (env.success) {
      aiHtml += aiEnvelopeBlock(env) + `<p>${escapeHtml(env.data.answer_explanation)}</p>` + listBlock("Caveats", env.data.caveats);
    } else {
      aiHtml += aiEnvelopeBlock(env);
    }
    aiHtml += `</div>`;

    resultEl.innerHTML = calcHtml + aiHtml;
  } catch (e) {
    resultEl.innerHTML = `<div class="alert alert-danger">${escapeHtml(errorMessage(e))}</div>`;
  }
}

/* ---------------------------------------------------------------------- */
/* AI Analyst                                                                */
/* ---------------------------------------------------------------------- */

function renderInsightsResult(data) {
  let html = "";
  if (data.executive_summary) html += `<div class="panel"><div class="panel-title">Executive Summary</div><p>${escapeHtml(data.executive_summary)}</p></div>`;
  if (data.key_findings && data.key_findings.length) {
    html += `<div class="panel"><div class="panel-title">Key Findings</div>` + data.key_findings.map((f) => `
      <div class="finding-card">
        <span class="badge badge-${f.importance === "high" ? "danger" : f.importance === "low" ? "info" : "warning"} importance">${escapeHtml(f.importance)}</span>
        <strong>${escapeHtml(f.finding)}</strong>
        <p class="small muted mb-0">${escapeHtml(f.evidence)}</p>
      </div>`).join("") + `</div>`;
  }
  const listSections = [
    ["trends", "Trends"], ["anomalies", "Anomalies"], ["business_implications", "Potential Business Implications"],
    ["questions_worth_investigating", "Questions Worth Investigating"], ["recommended_next_analysis", "Recommended Next Analysis"],
    ["top_insights", "Top Insights"], ["opportunities", "Opportunities"], ["risks", "Risks"], ["next_steps", "Suggested Next Steps"],
  ];
  const cols = listSections.filter(([k]) => data[k] && data[k].length);
  if (cols.length) {
    html += `<div class="grid grid-2">` + cols.map(([k, label]) => `<div class="panel">${listBlock(label, data[k])}</div>`).join("") + `</div>`;
  }
  const limitations = data.limitations || data.data_limitations;
  if (limitations && limitations.length) html += `<div class="panel"><div class="panel-title">Limitations</div><ul>${limitations.map((l) => `<li>${escapeHtml(l)}</li>`).join("")}</ul></div>`;
  return html;
}

async function runInsights() {
  if (!requireDataset()) return;
  const provider = $("#analyst-provider").value;
  const focus = $("#analyst-focus").value.trim() || null;
  const metaEl = $("#analyst-meta"), resultEl = $("#analyst-result");
  metaEl.innerHTML = `<div class="panel"><span class="spinner"></span> Running deterministic analysis, then asking AI to interpret it...</div>`;
  resultEl.innerHTML = "";
  try {
    const res = await API.insights(state.activeDatasetId, { provider, focus });
    const env = res.ai_result;
    metaEl.innerHTML = `<div class="panel">${aiEnvelopeBlock(env)}</div>`;
    if (env.success) resultEl.innerHTML = renderInsightsResult(env.data);
    else resultEl.innerHTML = `<div class="alert alert-warning">${escapeHtml(env.message)}</div><div class="panel"><div class="panel-title">Verified Statistics (still available without AI)</div><pre class="code-block">${escapeHtml(JSON.stringify(res.verified_statistics, null, 2))}</pre></div>`;
  } catch (e) {
    metaEl.innerHTML = `<div class="alert alert-danger">${escapeHtml(errorMessage(e))}</div>`;
  }
}

async function runBusinessInsights() {
  if (!requireDataset()) return;
  const provider = $("#analyst-provider").value;
  const metaEl = $("#analyst-meta"), resultEl = $("#analyst-result");
  metaEl.innerHTML = `<div class="panel"><span class="spinner"></span> Generating business insights...</div>`;
  resultEl.innerHTML = "";
  try {
    const res = await API.businessInsights(state.activeDatasetId, { provider });
    const env = res.ai_result;
    metaEl.innerHTML = `<div class="panel">${aiEnvelopeBlock(env)}</div>`;
    if (env.success) resultEl.innerHTML = renderInsightsResult(env.data);
    else resultEl.innerHTML = `<div class="alert alert-warning">${escapeHtml(env.message)}</div>`;
  } catch (e) {
    metaEl.innerHTML = `<div class="alert alert-danger">${escapeHtml(errorMessage(e))}</div>`;
  }
}

/* ---------------------------------------------------------------------- */
/* Reports                                                                    */
/* ---------------------------------------------------------------------- */

async function generateReport() {
  if (!requireDataset()) return;
  const btn = $("#generate-report-btn");
  const report_type = $("#report-type").value;
  const export_format = $("#report-format").value;
  const provider = $("#report-provider").value;
  const include_ai = $("#report-include-ai").checked;
  await withLoading(btn, async () => {
    const res = await API.generateReport({ dataset_id: state.activeDatasetId, report_type, export_format, provider, include_ai });
    $("#report-output-panel").style.display = "block";
    $("#report-output-title").textContent = res.title;
    state.reportContent = res.content;
    state.reportMediaType = res.media_type;
    state.reportFilename = `${res.title.replace(/\s+/g, "_").toLowerCase()}.${export_format === "markdown" ? "md" : export_format}`;
    if (export_format === "html") {
      $("#report-output").innerHTML = `<iframe style="width:100%; height:500px; border:1px solid var(--border); border-radius:8px;" srcdoc="${escapeHtml(res.content)}"></iframe>`;
    } else {
      $("#report-output").innerHTML = `<pre class="code-block">${escapeHtml(res.content)}</pre>`;
    }
    toast("success", "Report generated.");
    loadReportsList();
  });
}

function downloadReport() {
  if (!state.reportContent) return;
  const blob = new Blob([state.reportContent], { type: state.reportMediaType || "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = state.reportFilename;
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}

async function loadReportsList() {
  try {
    const reports = await API.listReports();
    $("#reports-list").innerHTML = table(
      [
        { key: "title", label: "Title" }, { key: "report_type", label: "Type" },
        { key: "ai_provider", label: "AI Provider", render: (r) => r.ai_provider || "None" },
        { key: "created_at", label: "Generated", render: (r) => fmtDate(r.created_at) },
      ],
      reports, { emptyText: "No reports generated yet." }
    );
  } catch (e) { /* non-fatal */ }
}

/* ---------------------------------------------------------------------- */
/* History                                                                    */
/* ---------------------------------------------------------------------- */

async function loadHistory() {
  const el = $("#history-table");
  const scope = $("#history-filter-scope").value;
  const datasetId = scope === "current" ? state.activeDatasetId : null;
  if (scope === "current" && !state.activeDatasetId) { el.innerHTML = `<div class="empty-state">Select a dataset, or switch to "All datasets".</div>`; return; }
  try {
    const runs = await API.history(datasetId);
    el.innerHTML = table(
      [
        { key: "created_at", label: "When", render: (r) => fmtDate(r.created_at) },
        { key: "analysis_type", label: "Type", render: (r) => `<span class="badge badge-info">${r.analysis_type}</span>` },
        { key: "ai_provider", label: "AI Provider", render: (r) => r.ai_provider || "-" },
        { key: "processing_time_ms", label: "Time (ms)", render: (r) => fmtNum(r.processing_time_ms, 0) },
        {
          key: "actions", label: "Actions", render: (r) => `
          <div class="btn-group">
            <button class="btn btn-sm" onclick="viewHistoryItem('${r.id}')">View</button>
            <a class="btn btn-sm" href="${API.exportHistoryUrl(r.id)}">Export</a>
            <button class="btn btn-sm btn-danger" onclick="deleteHistoryItem('${r.id}')">Delete</button>
          </div>`,
        },
      ],
      runs, { emptyText: "No analysis runs recorded yet." }
    );
  } catch (e) { toast("error", errorMessage(e)); }
}

async function viewHistoryItem(id) {
  try {
    const item = await API.historyItem(id);
    await confirmModal(`Analysis: ${escapeHtml(item.analysis_type)}`, `<pre class="code-block" style="max-height:300px;">${escapeHtml(JSON.stringify(item.result, null, 2)).slice(0, 4000)}</pre>`);
  } catch (e) { toast("error", errorMessage(e)); }
}

async function deleteHistoryItem(id) {
  const ok = await confirmModal("Delete this history entry?", "This cannot be undone.");
  if (!ok) return;
  try { await API.deleteHistoryItem(id); toast("success", "Deleted."); loadHistory(); } catch (e) { toast("error", errorMessage(e)); }
}

/* ---------------------------------------------------------------------- */
/* AI Providers                                                              */
/* ---------------------------------------------------------------------- */

const PROVIDER_LABELS = { openai: "OpenAI", anthropic: "Anthropic Claude", gemini: "Google Gemini" };

async function loadProviders() {
  const el = $("#providers-panel");
  el.innerHTML = `<div class="panel"><span class="spinner"></span> Loading provider status...</div>`;
  try {
    const res = await API.providers();
    el.innerHTML = `<div class="panel">` + res.providers.map((p) => `
      <div class="provider-row">
        <div>
          <div class="provider-name">${PROVIDER_LABELS[p.provider] || p.provider} <span class="badge badge-info small">${p.role.replace(/_/g, " ")}</span></div>
          <div class="small muted">Model: <code>${escapeHtml(p.model)}</code></div>
        </div>
        <div class="flex">
          <span class="badge ${p.configured ? "badge-success" : "badge-warning"}">${p.configured ? "Configured" : "Not Configured"}</span>
          <span id="provider-status-${p.provider}"></span>
          <button class="btn btn-sm" onclick="testProvider('${p.provider}')">Test Provider</button>
        </div>
      </div>
    `).join("") + `</div>`;
  } catch (e) { el.innerHTML = `<div class="alert alert-danger">${escapeHtml(errorMessage(e))}</div>`; }
}

async function testProvider(name) {
  const statusEl = $(`#provider-status-${name}`);
  if (statusEl) statusEl.innerHTML = `<span class="spinner"></span>`;
  try {
    const res = await API.testProvider(name);
    renderProviderTestResult(name, res);
  } catch (e) { toast("error", errorMessage(e)); }
}

function renderProviderTestResult(name, res) {
  const statusEl = $(`#provider-status-${name}`);
  if (!statusEl) return;
  if (!res.configured) { statusEl.innerHTML = `<span class="badge badge-warning">Not configured</span>`; return; }
  if (res.available) {
    statusEl.innerHTML = `<span class="badge badge-success">Available · ${fmtNum(res.latency_ms, 0)} ms</span>`;
  } else {
    statusEl.innerHTML = `<span class="badge badge-danger" title="${escapeHtml(res.error || "")}">Error${res.error_category ? " · " + res.error_category : ""}</span>`;
  }
}

async function testAllProviders() {
  const btn = $("#test-all-btn");
  await withLoading(btn, async () => {
    const res = await API.testAllProviders();
    res.results.forEach((r) => renderProviderTestResult(r.provider, r));
    toast("success", "Provider test complete.");
  });
}

/* ---------------------------------------------------------------------- */
/* Init                                                                       */
/* ---------------------------------------------------------------------- */

async function init() {
  applyTheme();
  $("#theme-toggle").addEventListener("change", (e) => toggleTheme(e.target.checked));
  $("#theme-toggle-2").addEventListener("change", (e) => toggleTheme(e.target.checked));

  $all(".nav-item").forEach((item) => item.addEventListener("click", () => switchView(item.dataset.view)));
  $all("#explore-tabs .tab-btn").forEach((btn) => btn.addEventListener("click", () => renderExploreTab(btn.dataset.tab)));

  setupUpload();
  $("#refresh-datasets-btn").addEventListener("click", refreshDatasetsList);
  $("#refresh-profile-btn").addEventListener("click", loadProfile);
  $("#reset-dataset-btn").addEventListener("click", resetDataset);
  $("#ai-cleaning-suggest-btn").addEventListener("click", aiCleaningSuggestions);
  $("#ask-btn").addEventListener("click", askQuestion);
  $("#ask-input").addEventListener("keydown", (e) => { if (e.key === "Enter") askQuestion(); });
  $("#run-insights-btn").addEventListener("click", runInsights);
  $("#run-business-insights-btn").addEventListener("click", runBusinessInsights);
  $("#generate-report-btn").addEventListener("click", generateReport);
  $("#download-report-btn").addEventListener("click", downloadReport);
  $("#history-filter-scope").addEventListener("change", loadHistory);
  $("#test-all-btn").addEventListener("click", testAllProviders);
  $("#explain-chart-btn").addEventListener("click", explainChart);

  await refreshDatasetsList();
  if (state.activeDatasetId) {
    try { await selectDataset(state.activeDatasetId); } catch { state.activeDatasetId = null; }
  }
  loadDashboard();
}

document.addEventListener("DOMContentLoaded", init);
