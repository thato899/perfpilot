import { afterEach, describe, expect, it, vi } from "vitest";

import { GET } from "./route";

afterEach(() => {
  vi.unstubAllGlobals();
  delete process.env.API_BASE_URL;
  delete process.env.API_AUTH_SECRET;
});

describe("FastAPI proxy", () => {
  it("adds the server-only bearer token and ignores a browser Authorization header", async () => {
    process.env.API_BASE_URL = "http://fastapi.internal:8000";
    process.env.API_AUTH_SECRET = "server-secret";
    const upstream = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: "project-1" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", upstream);

    const response = await GET(
      new Request("http://web.test/api/perfpilot/projects?summary=true", {
        headers: { Authorization: "Bearer browser-value" },
      }),
      { params: Promise.resolve({ path: ["projects"] }) },
    );

    expect(response.status).toBe(200);
    const [url, init] = upstream.mock.calls[0] as [URL, RequestInit];
    expect(url.toString()).toBe("http://fastapi.internal:8000/api/projects?summary=true");
    expect((init.headers as Headers).get("Authorization")).toBe("Bearer server-secret");
  });
});
