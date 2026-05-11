export const ACCESS_TOKEN_COOKIE = "access_token";
export const CSRF_TOKEN_COOKIE = "csrf_token";

export const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type RequestOptions = RequestInit & {
  json?: unknown;
};

export type WorkspaceMembership = {
  workspace_id: string;
  workspace_name: string;
  workspace_slug: string;
  role: string;
};

export type AuthUser = {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
  memberships: WorkspaceMembership[];
};

export type AuthSessionResponse = {
  expires_in: number;
  user: AuthUser;
};

function getCookieValue(name: string): string | null {
  if (typeof document === "undefined") {
    return null;
  }
  const encodedName = `${encodeURIComponent(name)}=`;
  for (const cookiePart of document.cookie.split(";")) {
    const trimmed = cookiePart.trim();
    if (trimmed.startsWith(encodedName)) {
      return decodeURIComponent(trimmed.slice(encodedName.length));
    }
  }
  return null;
}

function shouldAttachCsrf(method: string): boolean {
  return !["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase());
}

export function buildApiHeaders(
  headers?: HeadersInit,
  method: string = "GET",
): Headers {
  const merged = new Headers(headers);
  if (shouldAttachCsrf(method) && !merged.has("X-CSRF-Token")) {
    const csrfToken = getCookieValue(CSRF_TOKEN_COOKIE);
    if (csrfToken) {
      merged.set("X-CSRF-Token", csrfToken);
    }
  }
  return merged;
}

export async function apiFetch(
  path: string,
  options: RequestInit = {},
): Promise<Response> {
  const method = options.method ?? "GET";
  const headers = buildApiHeaders(options.headers, method);

  return fetch(`${apiBaseUrl}${path}`, {
    ...options,
    method,
    headers,
    credentials: "include",
  });
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const method = options.method ?? "GET";
  const headers = buildApiHeaders(options.headers, method);
  if (!headers.has("Content-Type") && (options.json !== undefined || options.body)) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await apiFetch(path, {
      ...options,
      method,
      headers,
      body: options.json ? JSON.stringify(options.json) : options.body,
    });
  } catch {
    throw new Error(
      `Could not reach the backend at ${apiBaseUrl}. Make sure the FastAPI server is running.`,
    );
  }

  if (!response.ok) {
    const data = await response.json().catch(() => ({ detail: "Request failed." }));
    throw new Error(data.detail ?? "Request failed.");
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export async function login(payload: {
  email: string;
  password: string;
}): Promise<AuthSessionResponse> {
  return apiRequest<AuthSessionResponse>("/api/v1/auth/login", {
    method: "POST",
    json: payload,
  });
}

export async function signup(payload: {
  full_name: string;
  workspace_name: string;
  email: string;
  password: string;
}): Promise<AuthSessionResponse> {
  return apiRequest<AuthSessionResponse>("/api/v1/auth/signup", {
    method: "POST",
    json: payload,
  });
}

export async function logout(): Promise<{ message: string }> {
  return apiRequest<{ message: string }>("/api/v1/auth/logout", {
    method: "POST",
  });
}

export async function fetchCurrentUser(): Promise<AuthUser> {
  return apiRequest<AuthUser>("/api/v1/auth/me");
}
