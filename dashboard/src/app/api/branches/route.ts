import { NextResponse } from "next/server";
import { getClientBranches } from "@/lib/github";

export async function GET() {
  try {
    const branches = await getClientBranches();
    return NextResponse.json(branches);
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
