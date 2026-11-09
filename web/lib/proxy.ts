const HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
  "host",
  "content-length",
]);

export async function proxyRequest(request: Request, path: string[]): Promise<Response> {
  const base = (process.env.API_INTERNAL_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
  const incoming = new URL(request.url);
  const target = new URL(`${base}/${path.map(encodeURIComponent).join("/")}`);
  target.search = incoming.search;
  const headers = new Headers();
  request.headers.forEach((value, key) => {
    if (!HOP.has(key.toLowerCase())) headers.set(key, value);
  });
  const method = request.method.toUpperCase();
  const body = method === "GET" || method === "HEAD" ? undefined : await request.arrayBuffer();
  const response = await fetch(target, { method, headers, body, redirect: "manual" });
  const outgoing = new Headers();
  response.headers.forEach((value, key) => {
    if (!HOP.has(key.toLowerCase())) outgoing.set(key, value);
  });
  return new Response(response.body, { status: response.status, headers: outgoing });
}
