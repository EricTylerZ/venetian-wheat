import { NextRequest, NextResponse } from "next/server";
import { getBranchCommits } from "@/lib/github";

export async function GET(req: NextRequest) {
  const branch = req.nextUrl.searchParams.get("branch");
  if (!branch) {
    return NextResponse.json({ error: "branch param required" }, { status: 400 });
  }
  try {
    const commits = await getBranchCommits(branch);
    return NextResponse.json(commits);
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
