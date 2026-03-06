import { NextRequest, NextResponse } from "next/server";
import { getClaudeMd, updateFile } from "@/lib/github";

export async function GET(req: NextRequest) {
  const branch = req.nextUrl.searchParams.get("branch");
  if (!branch) {
    return NextResponse.json({ error: "branch param required" }, { status: 400 });
  }
  try {
    const result = await getClaudeMd(branch);
    if (!result) {
      return NextResponse.json({ error: "CLAUDE.md not found" }, { status: 404 });
    }
    return NextResponse.json(result);
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}

export async function PUT(req: NextRequest) {
  const { branch, content, sha, message } = await req.json();
  if (!branch || !content || !sha) {
    return NextResponse.json(
      { error: "branch, content, and sha required" },
      { status: 400 }
    );
  }
  try {
    await updateFile(
      branch,
      "CLAUDE.md",
      content,
      message || "Update CLAUDE.md from dashboard",
      sha
    );
    return NextResponse.json({ ok: true });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
