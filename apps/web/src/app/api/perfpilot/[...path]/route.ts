import { NextResponse } from "next/server";

async function proxy(
  request: Request,
  context: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const apiBaseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  const apiAuthSecret = process.env.API_AUTH_SECRET;
  if (!apiAuthSecret) {
    return NextResponse.json(
      {
        error: {
          code: "frontend_proxy_not_configured",
          message: "API_AUTH_SECRET is not configured.",
        },
      },
      { status: 500 },
    );
  }

  const { path } = await context.params;
  const upstreamUrl = new URL(`${apiBaseUrl.replace(/\/$/, "")}/api/${path.join("/")}`);
  upstreamUrl.search = new URL(request.url).search;

  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("authorization");
  headers.set("Authorization", `Bearer ${apiAuthSecret}`);

  const init: RequestInit = {
    method: request.method,
    headers,
    cache: "no-store",
  };
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.arrayBuffer();
  }

  const upstream = await fetch(upstreamUrl, init);
  const responseHeaders = new Headers();
  const contentType = upstream.headers.get("content-type");
  if (contentType) responseHeaders.set("content-type", contentType);
  return new Response(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
