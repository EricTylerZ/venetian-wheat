"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface Branch {
  name: string;
  clientId: string;
  lastCommit: { sha: string; message: string; date: string };
}

export default function Dashboard() {
  const [branches, setBranches] = useState<Branch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showNew, setShowNew] = useState(false);
  const [newId, setNewId] = useState("");
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);

  async function load() {
    try {
      const res = await fetch("/api/branches");
      if (!res.ok) throw new Error(await res.text());
      setBranches(await res.json());
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function createProject() {
    if (!newId.trim()) return;
    setCreating(true);
    try {
      const res = await fetch("/api/actions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "create_project",
          clientId: newId.trim().toLowerCase().replace(/\s+/g, "_"),
          name: newName.trim() || undefined,
        }),
      });
      if (!res.ok) throw new Error((await res.json()).error);
      setShowNew(false);
      setNewId("");
      setNewName("");
      load();
    } catch (e: any) {
      alert(`Failed: ${e.message}`);
    } finally {
      setCreating(false);
    }
  }

  function timeAgo(date: string) {
    const s = Math.floor((Date.now() - new Date(date).getTime()) / 1000);
    if (s < 60) return "just now";
    if (s < 3600) return `${Math.floor(s / 60)}m ago`;
    if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
    return `${Math.floor(s / 86400)}d ago`;
  }

  return (
    <>
      <h1 style={{ color: "#2c1810", marginBottom: 4, fontSize: "1.5rem" }}>
        Venetian Wheat
      </h1>
      <p style={{ color: "#7a6e5d", marginBottom: "1.5rem", fontSize: "0.9rem" }}>
        Client fields &mdash; tap a project to see details
      </p>

      {loading && <p>Loading...</p>}
      {error && <p style={{ color: "#8b3a3a" }}>Error: {error}</p>}

      <div style={{ display: "grid", gap: "0.75rem" }}>
        {branches.map((b) => (
          <Link
            key={b.name}
            href={`/project?branch=${b.name}`}
            style={{
              display: "block",
              background: "#fff",
              border: "1px solid #e0d5c1",
              borderRadius: 8,
              padding: "1rem",
              textDecoration: "none",
              color: "inherit",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <strong style={{ fontSize: "1.05rem" }}>
                {b.clientId.replace(/_/g, " ")}
              </strong>
              <span
                style={{
                  fontSize: "0.75rem",
                  color: "#7a6e5d",
                }}
              >
                {timeAgo(b.lastCommit.date)}
              </span>
            </div>
            <div
              style={{
                fontSize: "0.85rem",
                color: "#7a6e5d",
                marginTop: 4,
              }}
            >
              <span style={{ color: "#999", fontFamily: "monospace" }}>
                {b.lastCommit.sha}
              </span>{" "}
              {b.lastCommit.message.slice(0, 60)}
            </div>
          </Link>
        ))}

        {/* New project card */}
        {!showNew ? (
          <button
            onClick={() => setShowNew(true)}
            style={{
              background: "transparent",
              border: "2px dashed #e0d5c1",
              borderRadius: 8,
              padding: "1.25rem",
              cursor: "pointer",
              fontSize: "1rem",
              color: "#7a6e5d",
            }}
          >
            + New Client Project
          </button>
        ) : (
          <div
            style={{
              background: "#fff",
              border: "1px solid #d4a843",
              borderRadius: 8,
              padding: "1rem",
            }}
          >
            <input
              placeholder="client_id (lowercase, underscores)"
              value={newId}
              onChange={(e) => setNewId(e.target.value)}
              style={{
                width: "100%",
                padding: "0.5rem",
                marginBottom: "0.5rem",
                border: "1px solid #e0d5c1",
                borderRadius: 6,
                fontSize: "0.9rem",
                boxSizing: "border-box",
              }}
            />
            <input
              placeholder="Display name (optional)"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              style={{
                width: "100%",
                padding: "0.5rem",
                marginBottom: "0.75rem",
                border: "1px solid #e0d5c1",
                borderRadius: 6,
                fontSize: "0.9rem",
                boxSizing: "border-box",
              }}
            />
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button
                onClick={createProject}
                disabled={creating}
                style={{
                  padding: "0.5rem 1rem",
                  background: "#d4a843",
                  color: "#2c1810",
                  border: "none",
                  borderRadius: 6,
                  cursor: "pointer",
                  fontWeight: 600,
                }}
              >
                {creating ? "Creating..." : "Create"}
              </button>
              <button
                onClick={() => setShowNew(false)}
                style={{
                  padding: "0.5rem 1rem",
                  background: "transparent",
                  border: "1px solid #e0d5c1",
                  borderRadius: 6,
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
