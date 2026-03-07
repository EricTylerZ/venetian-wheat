"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface LogEntry {
  id: number;
  ip: string;
  page: string;
  referrer: string;
  domain: string;
  event: string;
  user_hash: string;
  created_at: string;
}

interface LogsResponse {
  ok: boolean;
  count: number;
  unique_ips: number;
  logs: LogEntry[];
  error?: string;
}

interface CpanelDomain {
  domain: string;
  documentroot?: string;
  type?: string;
}

interface CpanelDisk {
  diskused?: number;
  disklimit?: number;
}

const cardStyle: React.CSSProperties = {
  background: "#fff",
  border: "1px solid #e0d5c1",
  borderRadius: 8,
  padding: "1rem",
};

const labelStyle: React.CSSProperties = {
  fontSize: "0.75rem",
  color: "#7a6e5d",
  textTransform: "uppercase",
  letterSpacing: "0.05em",
  marginBottom: "0.5rem",
};

export default function ServerPage() {
  const [logs, setLogs]           = useState<LogEntry[]>([]);
  const [logsMeta, setLogsMeta]   = useState<{ count: number; unique_ips: number } | null>(null);
  const [domains, setDomains]     = useState<CpanelDomain[]>([]);
  const [disk, setDisk]           = useState<CpanelDisk | null>(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState("");
  const [filterDomain, setFilter] = useState("");
  const [filterIp, setFilterIp]   = useState("");

  async function loadLogs(domain = "", ip = "") {
    const params = new URLSearchParams({ limit: "200", domain, ip });
    const res    = await fetch(`/api/server-logs?${params}`);
    const data: LogsResponse = await res.json();
    if (!data.ok) throw new Error(data.error ?? "load failed");
    setLogs(data.logs);
    setLogsMeta({ count: data.count, unique_ips: data.unique_ips });
  }

  async function loadCpanel() {
    const [domRes, diskRes] = await Promise.all([
      fetch("/api/cpanel?action=domains"),
      fetch("/api/cpanel?action=disk"),
    ]);
    const domData  = await domRes.json();
    const diskData = await diskRes.json();

    const allDomains: CpanelDomain[] = [
      ...(domData.main   ? [{ domain: domData.main.main_domain, type: "main" }] : []),
      ...(domData.addons ?? []).map((d: any) => ({ domain: d.domain, type: "addon", documentroot: d.documentroot })),
      ...(domData.subs   ?? []).map((d: any) => ({ domain: d.domain, type: "sub",   documentroot: d.documentroot })),
    ];
    setDomains(allDomains);
    setDisk(diskData.disk ?? null);
  }

  useEffect(() => {
    Promise.all([loadLogs(), loadCpanel()])
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function applyFilter() {
    setLoading(true);
    try { await loadLogs(filterDomain, filterIp); }
    catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }

  function fmtBytes(b?: number) {
    if (b == null) return "—";
    if (b < 1024) return `${b} B`;
    if (b < 1048576) return `${(b / 1024).toFixed(1)} KB`;
    return `${(b / 1048576).toFixed(1)} MB`;
  }

  function timeAgo(dateStr: string) {
    const s = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
    if (s < 60) return "just now";
    if (s < 3600) return `${Math.floor(s / 60)}m ago`;
    if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
    return `${Math.floor(s / 86400)}d ago`;
  }

  return (
    <>
      <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "1rem" }}>
        <Link href="/" style={{ color: "#7a6e5d", fontSize: "0.85rem", textDecoration: "none" }}>
          ← Dashboard
        </Link>
        <h1 style={{ color: "#2c1810", fontSize: "1.3rem", margin: 0 }}>Server Monitor</h1>
      </div>

      {error && (
        <div style={{ background: "#fff3f3", border: "1px solid #e09090", borderRadius: 6, padding: "0.75rem", marginBottom: "1rem", fontSize: "0.85rem", color: "#8b3a3a" }}>
          {error.includes("WHEAT_SERVER_URL") ? (
            <>Server not configured. Set <code>WHEAT_SERVER_URL</code> and <code>WHEAT_API_KEY</code> in Vercel environment variables.</>
          ) : (
            `Error: ${error}`
          )}
        </div>
      )}

      {/* --- cPanel Summary --- */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem", marginBottom: "1rem" }}>
        <div style={cardStyle}>
          <div style={labelStyle}>Domains</div>
          {loading ? <p style={{ margin: 0 }}>Loading...</p> : (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
              {domains.length === 0 && <span style={{ color: "#999" }}>None loaded</span>}
              {domains.map((d) => (
                <div key={d.domain} style={{ fontSize: "0.85rem" }}>
                  <span style={{ color: "#7a6e5d", fontSize: "0.7rem", marginRight: 6 }}>{d.type}</span>
                  <strong>{d.domain}</strong>
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={cardStyle}>
          <div style={labelStyle}>Disk Usage</div>
          {loading ? <p style={{ margin: 0 }}>Loading...</p> : disk ? (
            <>
              <div style={{ fontSize: "1.2rem", fontWeight: 700, color: "#2c1810" }}>
                {fmtBytes(disk.diskused)}
              </div>
              <div style={{ fontSize: "0.8rem", color: "#7a6e5d" }}>
                of {fmtBytes(disk.disklimit)} used
              </div>
            </>
          ) : <span style={{ color: "#999" }}>Unavailable</span>}
        </div>
      </div>

      {/* --- Access Log --- */}
      <div style={cardStyle}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
          <div>
            <div style={labelStyle}>Access Log</div>
            {logsMeta && (
              <div style={{ fontSize: "0.8rem", color: "#7a6e5d" }}>
                {logsMeta.count} entries · {logsMeta.unique_ips} unique IPs
              </div>
            )}
          </div>
        </div>

        {/* Filters */}
        <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.75rem", flexWrap: "wrap" }}>
          <input
            placeholder="Filter by domain"
            value={filterDomain}
            onChange={(e) => setFilter(e.target.value)}
            style={{ flex: 1, minWidth: 120, padding: "0.4rem 0.6rem", border: "1px solid #e0d5c1", borderRadius: 6, fontSize: "0.85rem" }}
          />
          <input
            placeholder="Filter by IP"
            value={filterIp}
            onChange={(e) => setFilterIp(e.target.value)}
            style={{ flex: 1, minWidth: 120, padding: "0.4rem 0.6rem", border: "1px solid #e0d5c1", borderRadius: 6, fontSize: "0.85rem" }}
          />
          <button
            onClick={applyFilter}
            style={{ padding: "0.4rem 0.9rem", background: "#d4a843", color: "#2c1810", border: "none", borderRadius: 6, cursor: "pointer", fontWeight: 600, fontSize: "0.85rem" }}
          >
            Filter
          </button>
          <button
            onClick={() => { setFilter(""); setFilterIp(""); loadLogs(); }}
            style={{ padding: "0.4rem 0.9rem", background: "transparent", border: "1px solid #e0d5c1", borderRadius: 6, cursor: "pointer", fontSize: "0.85rem" }}
          >
            Clear
          </button>
        </div>

        {loading ? (
          <p style={{ color: "#7a6e5d" }}>Loading logs...</p>
        ) : logs.length === 0 ? (
          <p style={{ color: "#999", fontSize: "0.85rem" }}>No log entries yet. Logs appear after the PHP scripts are deployed and receive traffic.</p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #e0d5c1", textAlign: "left", color: "#7a6e5d" }}>
                  <th style={{ padding: "0.4rem 0.5rem" }}>IP</th>
                  <th style={{ padding: "0.4rem 0.5rem" }}>Domain</th>
                  <th style={{ padding: "0.4rem 0.5rem" }}>Page</th>
                  <th style={{ padding: "0.4rem 0.5rem" }}>Event</th>
                  <th style={{ padding: "0.4rem 0.5rem" }}>When</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((l) => (
                  <tr key={l.id} style={{ borderBottom: "1px solid #f5f0e8" }}>
                    <td style={{ padding: "0.4rem 0.5rem", fontFamily: "monospace", whiteSpace: "nowrap" }}>
                      <button
                        onClick={() => { setFilterIp(l.ip); loadLogs(filterDomain, l.ip); }}
                        style={{ background: "none", border: "none", cursor: "pointer", color: "#2c6fad", fontFamily: "monospace", padding: 0, fontSize: "0.8rem" }}
                      >
                        {l.ip}
                      </button>
                    </td>
                    <td style={{ padding: "0.4rem 0.5rem", color: "#7a6e5d" }}>{l.domain || "—"}</td>
                    <td style={{ padding: "0.4rem 0.5rem", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{l.page || "—"}</td>
                    <td style={{ padding: "0.4rem 0.5rem" }}>
                      <span style={{ background: "#f5f0e8", borderRadius: 4, padding: "0.1rem 0.4rem" }}>{l.event}</span>
                    </td>
                    <td style={{ padding: "0.4rem 0.5rem", color: "#7a6e5d", whiteSpace: "nowrap" }}>{timeAgo(l.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
