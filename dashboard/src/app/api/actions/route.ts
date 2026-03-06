import { NextRequest, NextResponse } from "next/server";
import { createBranch, createFile } from "@/lib/github";

const CLAUDE_MD_TEMPLATE = (name: string) => `# ${name} — Project Context

## Who is this client?
[TODO: Describe the client and what they need]

## What does this codebase do?
[TODO: Describe the architecture, key files, tech stack]

## Current priorities
1. [TODO: First priority]
2. [TODO: Second priority]
3. [TODO: Third priority]

## Rules and constraints
- Do not modify files outside of this project's scope
- Run tests before committing
- Keep commits small and focused

## Key files
- \`CLAUDE.md\` — this file (project context)

## Recent decisions
- ${new Date().toISOString().split("T")[0]}: Project initialized
`;

export async function POST(req: NextRequest) {
  const { action, ...params } = await req.json();

  try {
    switch (action) {
      case "create_project": {
        const { clientId, name } = params;
        if (!clientId) {
          return NextResponse.json(
            { error: "clientId required" },
            { status: 400 }
          );
        }
        const branch = `client/${clientId}`;
        const displayName = name || clientId.replace(/_/g, " ");

        // Create the branch from main
        await createBranch(branch);

        // Add CLAUDE.md to the new branch
        await createFile(
          branch,
          "CLAUDE.md",
          CLAUDE_MD_TEMPLATE(displayName),
          `Initialize client field: ${clientId}`
        );

        return NextResponse.json({ ok: true, branch });
      }

      default:
        return NextResponse.json(
          { error: `Unknown action: ${action}` },
          { status: 400 }
        );
    }
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
