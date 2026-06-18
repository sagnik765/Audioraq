const backendBaseUrl = (import.meta.env.VITE_BACKEND_URL || "").replace(/\/$/, "");

export const API = backendBaseUrl ? `${backendBaseUrl}/api` : "/api";
