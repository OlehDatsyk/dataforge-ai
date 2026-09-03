/* DataForge AI - thin fetch wrapper around the backend REST API. */
const API = (() => {
  async function request(path, options = {}) {
    const res = await fetch(path, {
      headers: options.body && !(options.body instanceof FormData) ? { "Content-Type": "application/json" } : undefined,
      ...options,
    });
    let data = null;
    const contentType = res.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      data = await res.json();
    } else {
      data = await res.text();
    }
    if (!res.ok) {
      const message = (data && data.detail) ? data.detail : `Request failed (${res.status})`;
      throw new Error(message);
    }
    return data;
  }

  const post = (path, body) => request(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });
  const get = (path) => request(path, { method: "GET" });
  const del = (path) => request(path, { method: "DELETE" });

  return {
    health: () => get("/api/health"),
    dashboardStats: () => get("/api/dashboard/stats"),

    uploadDataset: (file) => {
      const fd = new FormData();
      fd.append("file", file);
      return request("/api/datasets/upload", { method: "POST", body: fd });
    },
    listDatasets: () => get("/api/datasets"),
    getDataset: (id) => get(`/api/datasets/${id}`),
    deleteDataset: (id) => del(`/api/datasets/${id}`),
    getProfile: (id) => get(`/api/datasets/${id}/profile`),
    cleanDataset: (id, body) => post(`/api/datasets/${id}/clean`, body),
    resetDataset: (id) => post(`/api/datasets/${id}/reset`),
    cleaningHistory: (id) => get(`/api/datasets/${id}/cleaning-history`),
    exportCsvUrl: (id) => `/api/datasets/${id}/export/csv`,
    exportXlsxUrl: (id) => `/api/datasets/${id}/export/xlsx`,

    descriptive: (id) => post(`/api/datasets/${id}/analyze/descriptive`),
    missing: (id) => post(`/api/datasets/${id}/analyze/missing`),
    duplicates: (id) => post(`/api/datasets/${id}/analyze/duplicates`),
    outliers: (id, body) => post(`/api/datasets/${id}/analyze/outliers`, body),
    correlation: (id, body) => post(`/api/datasets/${id}/analyze/correlation`, body),
    group: (id, body) => post(`/api/datasets/${id}/analyze/group`, body),
    timeseries: (id, body) => post(`/api/datasets/${id}/analyze/timeseries`, body),
    kpi: (id, body) => post(`/api/datasets/${id}/analyze/kpi`, body),
    category: (id, column, topN = 15) => get(`/api/datasets/${id}/analyze/category?column=${encodeURIComponent(column)}&top_n=${topN}`),

    chart: (id, body) => post(`/api/datasets/${id}/chart`, body),
    ask: (id, body) => post(`/api/datasets/${id}/ask`, body),
    insights: (id, body) => post(`/api/datasets/${id}/insights`, body),
    businessInsights: (id, body) => post(`/api/datasets/${id}/business-insights`, body),
    explainChart: (id, body) => post(`/api/datasets/${id}/explain`, body),
    cleaningSuggestions: (id, body) => post(`/api/datasets/${id}/cleaning-suggestions`, body),

    generateReport: (body) => post(`/api/reports/generate`, body),
    listReports: () => get(`/api/reports`),
    getReport: (id) => get(`/api/reports/${id}`),

    history: (datasetId) => get(`/api/history${datasetId ? `?dataset_id=${datasetId}` : ""}`),
    historyItem: (id) => get(`/api/history/${id}`),
    deleteHistoryItem: (id) => del(`/api/history/${id}`),
    exportHistoryUrl: (id) => `/api/history/${id}/export`,

    providers: () => get(`/api/ai/providers`),
    testProvider: (name) => post(`/api/ai/test/${name}`),
    testAllProviders: () => post(`/api/ai/test-all`),
  };
})();
