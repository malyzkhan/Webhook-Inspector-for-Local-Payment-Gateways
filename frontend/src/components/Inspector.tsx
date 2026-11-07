"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { WebhookEvent } from "@/types";

const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

function pretty(value: unknown) {
  return JSON.stringify(value, null, 2) ?? String(value);
}

function shellQuote(value: string) {
  return `'${value.replace(/'/g, "'\\''")}'`;
}

function curlCommand(event: WebhookEvent) {
  const query = event.raw_query ? `?${event.raw_query}` : "";
  const url = `${API_URL}/api/wh/${encodeURIComponent(event.endpoint_id)}${query}`;
  const ignoredHeaders = new Set(["host", "content-length", "connection", "transfer-encoding", "accept-encoding"]);
  const args = [`curl -X ${event.method} ${shellQuote(url)}`];
  for (const [name, value] of Object.entries(event.headers)) {
    if (!ignoredHeaders.has(name.toLowerCase())) {
      args.push(`-H ${shellQuote(`${name}: ${value}`)}`);
    }
  }
  if (event.raw_body_base64) {
    args.push("--data-binary @-");
    return `printf '%s' '${event.raw_body_base64}' | base64 --decode | \\\n  ${args.join(" \\\n  ")}`;
  }
  return args.join(" \\\n  ");
}

function badgeClass(gateway: string) {
  return `gateway-badge ${gateway.toLowerCase()}`;
}

export default function Inspector({ endpointId }: { endpointId: string }) {
  const [events, setEvents] = useState<WebhookEvent[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [copied, setCopied] = useState("");
  const endpointUrl = `${API_URL}/api/wh/${encodeURIComponent(endpointId)}`;
  const selected = useMemo(
    () => events.find((event) => event.id === selectedId) ?? events[0] ?? null,
    [events, selectedId],
  );

  useEffect(() => {
    let active = true;
    const source = new EventSource(`${API_URL}/api/stream/${encodeURIComponent(endpointId)}`);
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);
    source.onmessage = (message) => {
      try {
        const event = JSON.parse(message.data) as WebhookEvent;
        if (!active) return;
        setEvents((current) => [event, ...current.filter((item) => item.id !== event.id)].slice(0, 50));
        setSelectedId((current) => current ?? event.id);
      } catch {
        setLoadError("Received an unreadable event from the live stream.");
      }
    };
    fetch(`${API_URL}/api/endpoints/${encodeURIComponent(endpointId)}/history`)
      .then(async (response) => {
        if (!response.ok) throw new Error(`History request failed (${response.status})`);
        return (await response.json()) as WebhookEvent[];
      })
      .then((history) => {
        if (!active) return;
        setEvents((current) => {
          const known = new Set(current.map((event) => event.id));
          return [...current, ...history.filter((event) => !known.has(event.id))]
            .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))
            .slice(0, 50);
        });
        setLoadError("");
      })
      .catch((error: unknown) => {
        if (active) setLoadError(error instanceof Error ? error.message : "Could not load webhook history.");
      });
    return () => {
      active = false;
      source.close();
    };
  }, [endpointId]);

  const copy = useCallback(async (value: string, label: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(label);
      window.setTimeout(() => setCopied(""), 1600);
    } catch {
      setLoadError("Clipboard access failed. Copy the text manually.");
    }
  }, []);

  return (
    <main className="console">
      <header className="topbar">
        <a className="brand" href="/"> <span className="brand-mark small">P</span> PakHook</a>
        <div className="endpoint-wrap">
          <span className="endpoint-caption">YOUR WEBHOOK URL</span>
          <code>{endpointUrl}</code>
          <button className="icon-button" onClick={() => void copy(endpointUrl, "URL")} aria-label="Copy webhook URL">
            {copied === "URL" ? "Copied" : "Copy URL"}
          </button>
        </div>
        <div className={`connection ${connected ? "online" : ""}`}>
          <span className="connection-dot" /> {connected ? "Live SSE Connected" : "Reconnecting"}
        </div>
      </header>

      <div className="workspace">
        <aside className="event-sidebar">
          <div className="sidebar-heading">
            <div><p className="eyebrow">INCOMING TRAFFIC</p><h2>Webhook events <span>{events.length}</span></h2></div>
            <button className="text-button" onClick={() => { setEvents([]); setSelectedId(null); }}>Clear List</button>
          </div>
          {loadError && <p className="error-banner">{loadError}</p>}
          <div className="event-list">
            {events.length === 0 ? (
              <div className="empty-state"><div className="empty-icon">⌁</div><h3>Listening for events</h3><p>Send a request to your webhook URL. New events will appear here instantly.</p></div>
            ) : events.map((event) => (
              <button
                key={event.id}
                className={`event-row ${selected?.id === event.id ? "selected" : ""}`}
                onClick={() => setSelectedId(event.id)}
              >
                <div className="event-row-top"><span className={`method-badge ${event.method.toLowerCase()}`}>{event.method}</span><span className={badgeClass(event.gateway)}>{event.gateway}</span><time>{new Date(event.created_at).toLocaleTimeString()}</time></div>
                <div className="event-row-bottom"><span>{event.query_params.orderId ? `orderId=${String(event.query_params.orderId)}` : event.id.slice(0, 8)}</span><span className="status-ok">{event.response_status} OK</span></div>
              </button>
            ))}
          </div>
          <div className="sidebar-footer"><span className="live-pulse" /> Retention window · 24 hours</div>
        </aside>

        <section className="inspector-pane">
          {selected ? (
            <>
              <div className="detail-heading">
                <div><p className="eyebrow">REQUEST DETAILS</p><h1>{selected.gateway} <span className="detail-method">{selected.method}</span></h1><p className="detail-subtitle">Captured {new Date(selected.created_at).toLocaleString()} · {selected.client_ip || "Unknown IP"}</p></div>
                <button className="primary-button compact" onClick={() => void copy(curlCommand(selected), "cURL")}>{copied === "cURL" ? "Copied!" : "Copy as cURL"}</button>
              </div>
              <div className="detail-content">
                <DataSection title="Headers" data={selected.headers} />
                <DataSection title="Query Parameters" data={selected.query_params} />
                <DataSection title="Payload Body" data={selected.parsed_body} />
              </div>
            </>
          ) : (
            <div className="welcome-panel">
              <div className="welcome-orbit"><span>↘</span></div>
              <p className="eyebrow">READY WHEN YOU ARE</p><h2>Your callback, <span>under the microscope.</span></h2>
              <p>Register this endpoint with your payment gateway sandbox, then send a test transaction. Inspect headers, parameters, and payloads here as they arrive.</p>
              <div className="tip-card"><span>01</span><p><strong>Set the callback URL</strong><br />Copy the endpoint URL above into your gateway settings.</p></div>
              <div className="tip-card"><span>02</span><p><strong>Trigger a test payment</strong><br />The request will show up in this inspector in real time.</p></div>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

function DataSection({ title, data }: { title: string; data: unknown }) {
  const display = pretty(data);
  return (
    <section className="data-section">
      <div className="section-title"><h2>{title}</h2><span>{display.length} chars</span></div>
      <pre><code>{display}</code></pre>
    </section>
  );
}
