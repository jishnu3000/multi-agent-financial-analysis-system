/**
 * Centralised API client.
 * Every request automatically attaches the stored JWT bearer token.
 */

const API_URL = import.meta.env.VITE_API_URL;

/** Retrieve the token from localStorage (set by AuthContext on login). */
const getToken = () => localStorage.getItem("token");

/**
 * Core fetch wrapper.
 * Throws an Error with the server's detail message on non-2xx responses.
 */
async function request(path, options = {}) {
  const token = getToken();
  const headers = {
    ...(options.headers || {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  // Only set Content-Type for JSON bodies
  if (options.body && typeof options.body === "string") {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (!res.ok) {
    let detail = `Request failed with status ${res.status}`;
    try {
      const json = await res.json();
      detail = json.detail || detail;
    } catch {
      // ignore parse errors
    }
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }

  return res.json();
}

/* ==================== AUTH ==================== */

/**
 * Register a new user.
 * @param {string} username
 * @param {string} password
 */
export async function registerUser(username, password) {
  return request("/register", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

/**
 * Log in and return { access_token, token_type }.
 * The backend expects application/x-www-form-urlencoded (OAuth2 form).
 */
export async function loginUser(username, password) {
  const body = new URLSearchParams({ username, password });
  const res = await fetch(`${API_URL}/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });

  if (!res.ok) {
    let detail = "Login failed";
    try {
      const json = await res.json();
      detail = json.detail || detail;
    } catch {
      // ignore
    }
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }

  return res.json();
}

/* ==================== ANALYSIS ==================== */

/**
 * Run the multi-agent analysis for a ticker symbol.
 * @param {string} ticker  e.g. "AAPL"
 */
export async function analyzeStock(ticker) {
  return request("/analyze", {
    method: "POST",
    body: JSON.stringify({ ticker }),
  });
}

/* ==================== HISTORY ==================== */

/** Fetch the authenticated user's past analyses (up to 50). */
export async function fetchHistory() {
  return request("/history");
}

/**
 * Delete a single history entry.
 * @param {string} id  The ``_id`` of the history document.
 */
export async function deleteHistoryItem(id) {
  return request(`/history/${id}`, { method: "DELETE" });
}

/* ==================== PDF DOWNLOAD ==================== */

/** Open the PDF in a new tab. */
export function downloadPDF(pdfPath) {
  const filename = pdfPath.split("/").pop();
  window.open(`${API_URL}/download/${filename}`, "_blank");
}

/* ==================== HEALTH ==================== */

export async function healthCheck() {
  return request("/health");
}
