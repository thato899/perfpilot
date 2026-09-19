import { afterEach, describe, expect, it, vi } from "vitest";

import { GET, POST } from "./route";

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

  it("strips browser framing headers before proxying a POST body", async () => {
    process.env.API_BASE_URL = "http://fastapi.internal:8000";
    process.env.API_AUTH_SECRET = "server-secret";
    const upstream = vi.fn().mockResolvedValue(new Response("{}", { status: 201 }));
    vi.stubGlobal("fetch", upstream);

    const response = await POST(
      new Request("http://web.test/api/perfpilot/projects", {
        method: "POST",
        headers: {
          Authorization: "Bearer browser-value",
          "Content-Length": "18",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ name: "demo" }),
      }),
      { params: Promise.resolve({ path: ["projects"] }) },
    );

    expect(response.status).toBe(201);
    const [, init] = upstream.mock.calls[0] as [URL, RequestInit];
    const headers = init.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer server-secret");
    expect(headers.has("Content-Length")).toBe(false);
  });
});
