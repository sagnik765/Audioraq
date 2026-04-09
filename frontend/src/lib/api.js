const backendBaseUrl = (process.env.REACT_APP_BACKEND_URL || "").replace(/\/$/, "");

export const API = backendBaseUrl ? `${backendBaseUrl}/api` : "/api";
