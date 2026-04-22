import {
  clearStoredTokens,
  getStoredTokens,
  setStoredTokens,
} from "./auth-storage.js";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

let refreshPromise = null;

function buildUrl(path) {
  return `${API_BASE_URL}${path}`;
}

export async function loginRequest({ email, password }) {
  const body = new URLSearchParams({
    username: email,
    password,
  });

  const response = await fetch(buildUrl("/auth/login"), {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body,
  });

  if (!response.ok) {
    throw new Error("Invalid email or password.");
  }

  return response.json();
}

export async function registerRequest(payload) {
  const response = await fetch(buildUrl("/auth/register"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await safeError(response);
    throw new Error(error);
  }

  return response.json();
}

async function refreshTokens() {
  const { refreshToken } = getStoredTokens();

  if (!refreshToken) {
    throw new Error("Missing refresh token.");
  }

  const response = await fetch(buildUrl("/auth/refresh"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!response.ok) {
    clearStoredTokens();
    throw new Error("Session expired.");
  }

  const tokens = await response.json();
  setStoredTokens({
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
  });

  return tokens;
}

async function getFreshAccessToken() {
  if (!refreshPromise) {
    refreshPromise = refreshTokens().finally(() => {
      refreshPromise = null;
    });
  }

  const tokens = await refreshPromise;
  return tokens.access_token;
}

export async function apiRequest(path, options = {}) {
  const { accessToken } = getStoredTokens();
  const headers = new Headers(options.headers ?? {});

  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  let response = await fetch(buildUrl(path), {
    ...options,
    headers,
  });

  if (response.status === 401 && accessToken) {
    const freshAccessToken = await getFreshAccessToken();
    headers.set("Authorization", `Bearer ${freshAccessToken}`);

    response = await fetch(buildUrl(path), {
      ...options,
      headers,
    });
  }

  if (!response.ok) {
    const error = await safeError(response);
    throw new Error(error);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

export async function getCurrentUser() {
  return apiRequest("/auth/me", { method: "GET" });
}

export async function getTasks() {
  return apiRequest("/tasks", { method: "GET" });
}

export async function createTask(payload) {
  return apiRequest("/tasks", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateTask(taskId, payload) {
  return apiRequest(`/tasks/${taskId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function logoutRequest() {
  return apiRequest("/auth/logout", {
    method: "POST",
  });
}

async function safeError(response) {
  try {
    const payload = await response.json();
    return payload.detail ?? "Request failed.";
  } catch {
    return "Request failed.";
  }
}
