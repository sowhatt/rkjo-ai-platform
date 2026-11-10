/** Forward only the caller's bearer identity; never substitute a server role key. */
export async function relayAuthenticated(request: Request, path: string) {
  const authorization = request.headers.get("authorization") ?? "";
  const headers = { "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" };
  const error = (detail: string, status: number) => Response.json({ detail }, { status, headers });
  if (!/^Bearer [^\s]+$/i.test(authorization)) {
    return error("Bearer token required.", 401);
  }
  const upstreamHeaders: Record<string, string> = { Authorization: authorization, Accept: "application/json" };
  const contentType = request.headers.get("content-type");
  if (contentType) upstreamHeaders["Content-Type"] = contentType;
  try {
    const upstream = await fetch(`${process.env.RKJO_API_URL ?? "http://127.0.0.1:8000"}${path}`, {
      method: request.method,
      headers: upstreamHeaders,
      body: request.method === "GET" ? undefined : await request.arrayBuffer(),
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.timeout(60000),
    });
    if (upstream.status >= 300 && upstream.status < 400) return error("Unexpected upstream redirect.", 502);
    if (!(upstream.headers.get("content-type") ?? "").includes("application/json")) {
      return error("Invalid upstream response.", 502);
    }
    const body = await upstream.text();
    if (body.length > 1_000_000) return error("Upstream response too large.", 502);
    return new Response(body, { status: upstream.status, headers: { ...headers, "Content-Type": "application/json" } });
  } catch {
    return error("RKJO API unavailable.", 503);
  }
}

export function coursePath(courseId: string): string | null {
  if (!courseId.trim() || courseId === "." || courseId === ".." || /[\/\\\x00-\x1f]/.test(courseId)) return null;
  return `/education/courses/${encodeURIComponent(courseId)}`;
}
