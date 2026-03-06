/**
 * GitHub API wrapper for reading/writing to the venetian-wheat repo.
 * Uses fine-grained personal access token (PAT) with repo scope.
 */

const GITHUB_TOKEN = process.env.GITHUB_TOKEN!;
const GITHUB_OWNER = process.env.GITHUB_OWNER || "EricTylerZ";
const GITHUB_REPO = process.env.GITHUB_REPO || "venetian-wheat";

const API = `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}`;

async function gh(path: string, options: RequestInit = {}) {
  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      ...options.headers,
    },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`GitHub API ${res.status}: ${body.slice(0, 200)}`);
  }
  return res.json();
}

// ---- Read operations ----

export interface Branch {
  name: string;
  clientId: string;
  lastCommit: { sha: string; message: string; date: string };
}

export async function getClientBranches(): Promise<Branch[]> {
  const branches = await gh("/branches?per_page=100");
  const clientBranches = branches.filter((b: { name: string }) =>
    b.name.startsWith("client/")
  );

  // Get last commit for each branch
  const enriched = await Promise.all(
    clientBranches.map(async (b: { name: string; commit: { sha: string } }) => {
      const commit = await gh(`/commits/${b.commit.sha}`);
      return {
        name: b.name,
        clientId: b.name.replace("client/", ""),
        lastCommit: {
          sha: b.commit.sha.slice(0, 7),
          message: commit.commit.message.split("\n")[0],
          date: commit.commit.committer.date,
        },
      };
    })
  );

  return enriched;
}

export interface Commit {
  sha: string;
  message: string;
  date: string;
  author: string;
}

export async function getBranchCommits(
  branch: string,
  count = 10
): Promise<Commit[]> {
  const commits = await gh(`/commits?sha=${branch}&per_page=${count}`);
  return commits.map((c: any) => ({
    sha: c.sha.slice(0, 7),
    message: c.commit.message.split("\n")[0],
    date: c.commit.committer.date,
    author: c.commit.author.name,
  }));
}

export async function getFileContent(
  branch: string,
  path: string
): Promise<{ content: string; sha: string } | null> {
  try {
    const file = await gh(`/contents/${path}?ref=${branch}`);
    const content = Buffer.from(file.content, "base64").toString("utf-8");
    return { content, sha: file.sha };
  } catch {
    return null;
  }
}

export async function getClaudeMd(
  branch: string
): Promise<{ content: string; sha: string } | null> {
  return getFileContent(branch, "CLAUDE.md");
}

// ---- Write operations ----

export async function updateFile(
  branch: string,
  path: string,
  content: string,
  message: string,
  sha: string
) {
  return gh(`/contents/${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      content: Buffer.from(content).toString("base64"),
      sha,
      branch,
    }),
  });
}

export async function createBranch(
  branchName: string,
  fromBranch = "main"
): Promise<void> {
  // Get the SHA of the source branch
  const ref = await gh(`/git/ref/heads/${fromBranch}`);
  const sha = ref.object.sha;

  // Create the new branch
  await gh("/git/refs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ref: `refs/heads/${branchName}`,
      sha,
    }),
  });
}

export async function createFile(
  branch: string,
  path: string,
  content: string,
  message: string
) {
  return gh(`/contents/${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      content: Buffer.from(content).toString("base64"),
      branch,
    }),
  });
}
