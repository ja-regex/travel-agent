export const runtime = "nodejs";
export const maxDuration = 60;

export async function POST(request: Request) {
  const agentUrl = process.env.PYTHON_AGENT_URL ?? "http://127.0.0.1:8000";

  try {
    const response = await fetch(`${agentUrl}/chat`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: await request.text(),
      signal: request.signal,
      cache: "no-store"
    });

    return new Response(response.body, {
      status: response.status,
      headers: {
        "content-type": response.headers.get("content-type") ?? "application/x-ndjson; charset=utf-8",
        "cache-control": "no-cache, no-transform"
      }
    });
  } catch {
    return Response.json(
      { error: "The Python agent is unavailable. Start it with `pnpm dev:agent`." },
      { status: 503 }
    );
  }
}
