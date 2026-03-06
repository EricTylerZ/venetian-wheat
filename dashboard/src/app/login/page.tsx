"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      if (!res.ok) {
        setError("Wrong password");
        return;
      }
      router.push("/");
    } catch {
      setError("Connection failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#faf6ee",
        padding: "1rem",
      }}
    >
      <form
        onSubmit={submit}
        style={{
          background: "#fff",
          border: "1px solid #e0d5c1",
          borderRadius: 12,
          padding: "2rem",
          width: "100%",
          maxWidth: 360,
        }}
      >
        <h1
          style={{
            color: "#2c1810",
            fontSize: "1.3rem",
            marginBottom: "0.25rem",
          }}
        >
          Venetian Wheat
        </h1>
        <p style={{ color: "#7a6e5d", fontSize: "0.85rem", marginBottom: "1.5rem" }}>
          Enter your password to continue
        </p>

        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          autoFocus
          style={{
            width: "100%",
            padding: "0.75rem",
            border: "1px solid #e0d5c1",
            borderRadius: 8,
            fontSize: "1rem",
            marginBottom: "0.75rem",
            boxSizing: "border-box",
          }}
        />

        {error && (
          <p style={{ color: "#8b3a3a", fontSize: "0.85rem", marginBottom: "0.5rem" }}>
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={loading}
          style={{
            width: "100%",
            padding: "0.75rem",
            background: "#d4a843",
            color: "#2c1810",
            border: "none",
            borderRadius: 8,
            fontSize: "1rem",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          {loading ? "..." : "Enter"}
        </button>
      </form>
    </div>
  );
}
