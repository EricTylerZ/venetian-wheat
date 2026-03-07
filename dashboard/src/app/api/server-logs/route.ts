import { NextRequest, NextResponse } from "next/server";

const SERVER_URL = process.env.WHEAT_SERVER_URL ?? "";
const API_KEY    = process.env.WHEAT_API_KEY    ?? "";

function serverHeaders() {
  return { "X-Wheat-Key": API_KEY, "Content-Type": "application/json" };
}

/** GET /api/server-logs?limit=100&domain=&ip=&event= */
export async function GET(req: NextRequest) {
  if (!SERVER_URL) {
    return NextResponse.json({ error: "WHEAT_SERVER_URL not set" }, { status: 503 });
  }

  const { searchParams } = new URL(req.url);
  const params = new URLSearchParams({
    limit:  searchParams.get("limit")  ?? "100",
    domain: searchParams.get("domain") ?? "",
    ip:     searchParams.get("ip")     ?? "",
    event:  searchParams.get("event")  ?? "",
  });

  try {
    const res = await fetch(`${SERVER_URL}/logs.php?${params}`, {
      headers: serverHeaders(),
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.ok ? 200 : res.status });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 502 });
  }
}

/** POST /api/server-logs  — log a pageview event from the dashboard itself */
export async function POST(req: NextRequest) {
  if (!SERVER_URL) return NextResponse.json({ ok: false });

  try {
    const body = await req.json();
    const ip   = req.headers.get("x-forwarded-for")?.split(",")[0] ?? "unknown";

    const res = await fetch(`${SERVER_URL}/log.php`, {
      method:  "POST",
      headers: serverHeaders(),
      body:    JSON.stringify({ ...body, ip_override: ip }),
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 502 });
  }
}
