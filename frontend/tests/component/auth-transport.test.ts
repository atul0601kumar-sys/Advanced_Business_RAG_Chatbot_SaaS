import { apiRequest } from "@/lib/auth";

describe("auth transport", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    document.cookie = "csrf_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
  });

  test("uses cookie credentials and sends csrf header for mutating requests", async () => {
    document.cookie = "csrf_token=test-csrf-token; path=/";
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ok: true }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await apiRequest("/api/v1/auth/logout", { method: "POST" });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/auth/logout",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        headers: expect.any(Headers),
      }),
    );
    const headers = fetchMock.mock.calls[0][1].headers as Headers;
    expect(headers.get("X-CSRF-Token")).toBe("test-csrf-token");
    expect(headers.get("Authorization")).toBeNull();
  });

  test("does not attach csrf header to safe requests", async () => {
    document.cookie = "csrf_token=test-csrf-token; path=/";
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ id: "user-1" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await apiRequest("/api/v1/auth/me");

    const headers = fetchMock.mock.calls[0][1].headers as Headers;
    expect(headers.get("X-CSRF-Token")).toBeNull();
    expect(headers.get("Authorization")).toBeNull();
  });
});
