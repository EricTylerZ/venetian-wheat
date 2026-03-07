import { NextRequest, NextResponse } from "next/server";

const SERVER_URL = process.env.WHEAT_SERVER_URL ?? "";
const API_KEY    = process.env.WHEAT_API_KEY    ?? "";

/** GET /api/cpanel?action=domains|dbs|emails|disk|ssl */
export async function GET(req: NextRequest) {
  if (!SERVER_URL) {
    return NextResponse.json({ error: "WHEAT_SERVER_URL not set" }, { status: 503 });
  }

  const action = new URL(req.url).searchParams.get("action") ?? "domains";

  try {
    const res = await fetch(`${SERVER_URL}/cpanel.php?action=${encodeURIComponent(action)}`, {
      headers: { "X-Wheat-Key": API_KEY },
      cache:   "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.ok ? 200 : res.status });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 502 });
  }
}
