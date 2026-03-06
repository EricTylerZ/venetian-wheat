"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Suspense } from "react";

interface Commit {
  sha: string;
  message: string;
  date: string;
  author: string;
}

function ProjectContent() {
  const params = useSearchParams();
  const branch = params.get("branch") || "";
  const clientId = branch.replace("client/", "");

  const [commits, setCommits] = useState<Commit[]>([]);
  const [claudeMd, setClaudeMd] = useState("");
  const [claudeSha, setClaudeSha] = useState("");
  const [editing, setEditing] = useState(false);
  const [editContent, setEditContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!branch) return;
    Promise.all([
      fetch(`/api/commits?branch=${branch}`).then((r) => r.json()),
      fetch(`/api/claude-md?branch=${branch}`).then((r) =>
        r.ok ? r.json() : null
      ),
    ]).then(([c, md]) => {
      setCommits(c);
      if (md) {
        setClaudeMd(md.content);
        setClaudeSha(md.sha);
      }
      setLoading(false);
    });
  }, [branch]);

  async function save() {
    setSaving(true);
    try {
      const res = await fetch("/api/claude-md", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          branch,
          content: editContent,
          sha: claudeSha,
          message: "Update CLAUDE.md from dashboard",
        }),
      });
      if (!res.ok) throw new Error((await res.json()).error);
      setClaudeMd(editContent);
      setEditing(false);
      // Refresh to get new SHA
      const md = await fetch(`/api/claude-md?branch=${branch}`).then((r) =>
        r.json()
      );
      setClaudeSha(md.sha);
    } catch (e: any) {
      alert(`Save failed: ${e.message}`);
    } finally {
      setSaving(false);
    }
  }

  function timeAgo(date: string) {
    const s = Math.floor((Date.now() - new Date(date).getTime()) / 1000);
    if (s < 60) return "just now";
    if (s < 3600) return `${Math.floor(s / 60)}m ago`;
    if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
    return `${Math.floor(s / 86400)}d ago`;
  }

  if (!branch) return <p>No branch specified</p>;

  return (
    <>
      <Link
        href="/"
        style={{ color: "#d4a843", fontSize: "0.9rem" }}
      >
        &larr; Dashboard
      </Link>
      <h1 style={{ color: "#2c1810", marginTop: "0.5rem", fontSize: "1.4rem" }}>
        {clientId.replace(/_/g, " ")}
      </h1>
      <p
        style={{
          fontFamily: "monospace",
          fontSize: "0.8rem",
          color: "#7a6e5d",
          marginBottom: "1.5rem",
        }}
      >
        {branch}
      </p>

      {loading && <p>Loading...</p>}

      {/* CLAUDE.md section */}
      <div
        style={{
          background: "#fff",
          border: "1px solid #e0d5c1",
          borderRadius: 8,
          padding: "1rem",
          marginBottom: "1rem",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "0.75rem",
          }}
        >
          <strong>CLAUDE.md</strong>
          {!editing ? (
            <button
              onClick={() => {
                setEditContent(claudeMd);
                setEditing(true);
              }}
              style={{
                padding: "0.3rem 0.75rem",
                background: "#d4a843",
                color: "#2c1810",
                border: "none",
                borderRadius: 6,
                cursor: "pointer",
                fontSize: "0.8rem",
                fontWeight: 600,
              }}
            >
              Edit
            </button>
          ) : (
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button
                onClick={save}
                disabled={saving}
                style={{
                  padding: "0.3rem 0.75rem",
                  background: "#4a7c3f",
                  color: "#fff",
                  border: "none",
                  borderRadius: 6,
                  cursor: "pointer",
                  fontSize: "0.8rem",
                }}
              >
                {saving ? "Saving..." : "Save"}
              </button>
              <button
                onClick={() => setEditing(false)}
                style={{
                  padding: "0.3rem 0.75rem",
                  background: "transparent",
                  border: "1px solid #e0d5c1",
                  borderRadius: 6,
                  cursor: "pointer",
                  fontSize: "0.8rem",
                }}
              >
                Cancel
              </button>
            </div>
          )}
        </div>
        {editing ? (
          <textarea
            value={editContent}
            onChange={(e) => setEditContent(e.target.value)}
            style={{
              width: "100%",
              minHeight: 300,
              padding: "0.75rem",
              border: "1px solid #e0d5c1",
              borderRadius: 6,
              fontFamily: "monospace",
              fontSize: "0.85rem",
              resize: "vertical",
              boxSizing: "border-box",
            }}
          />
        ) : claudeMd ? (
          <pre
            style={{
              background: "#2c1810",
              color: "#e8dcc8",
              padding: "0.75rem 1rem",
              borderRadius: 6,
              fontSize: "0.8rem",
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              maxHeight: 400,
              overflow: "auto",
            }}
          >
            {claudeMd}
          </pre>
        ) : (
          <p style={{ color: "#7a6e5d" }}>No CLAUDE.md found on this branch</p>
        )}
      </div>

      {/* Commits section */}
      <div
        style={{
          background: "#fff",
          border: "1px solid #e0d5c1",
          borderRadius: 8,
          padding: "1rem",
        }}
      >
        <strong style={{ display: "block", marginBottom: "0.75rem" }}>
          Recent Commits
        </strong>
        {commits.map((c) => (
          <div
            key={c.sha}
            style={{
              padding: "0.5rem 0",
              borderBottom: "1px solid #f0ebe0",
              fontSize: "0.85rem",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>
                <span
                  style={{
                    fontFamily: "monospace",
                    color: "#999",
                    marginRight: "0.5rem",
                  }}
                >
                  {c.sha}
                </span>
                {c.message.slice(0, 70)}
              </span>
              <span style={{ color: "#7a6e5d", fontSize: "0.8rem", flexShrink: 0, marginLeft: "0.5rem" }}>
                {timeAgo(c.date)}
              </span>
            </div>
          </div>
        ))}
        {commits.length === 0 && !loading && (
          <p style={{ color: "#7a6e5d" }}>No commits yet</p>
        )}
      </div>
    </>
  );
}

export default function ProjectPage() {
  return (
    <Suspense fallback={<p>Loading...</p>}>
      <ProjectContent />
    </Suspense>
  );
}
