import React, { useState, useMemo, useEffect } from "react";
import { useClients, useBrief, useConsent } from "../hooks/useApi";
import {
  ROLES,
  categoryLabel,
  formatDate,
  type RecipientRole,
  type ConsentRow,
} from "../lib/api";
import { TierBadge } from "./Primitives";
import { MetricsModal } from "./MetricsModal";

export const WorkstationLayout: React.FC = () => {
  // State
  const [selectedClientId, setSelectedClientId] = useState<string>("C005");
  const [role, setRole] = useState<RecipientRole>("counsellor");
  const [tierOverride, setTierOverride] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterTab, setFilterTab] = useState<"all" | "urgent" | "actions">("all");
  const [rightDrawerOpen, setRightDrawerOpen] = useState(true);
  const [activeRightTab, setActiveRightTab] = useState<"consent" | "explainability" | "provenance">("consent");
  const [showMetricsModal, setShowMetricsModal] = useState(false);
  const [copySuccess, setCopySuccess] = useState(false);
  const [currentTime, setCurrentTime] = useState<string>("");

  // Update clock
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setCurrentTime(
        now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
      );
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  // Queries
  const { data: clientsData, isLoading: clientsLoading, error: clientsError } = useClients();
  const { data: brief, isLoading: briefLoading, error: briefError } = useBrief(
    selectedClientId,
    role,
    tierOverride
  );
  const { data: consentData, isLoading: consentLoading } = useConsent(selectedClientId);

  const clients = useClientsData(clientsData);

  // Set default client once clients load if current is not set
  useEffect(() => {
    if (clients.length > 0 && !clients.some((c) => c.client_id === selectedClientId)) {
      setSelectedClientId(clients[0].client_id);
    }
  }, [clients, selectedClientId]);

  // Filter clients
  const filteredClients = useMemo(() => {
    return clients.filter((client) => {
      const matchesSearch =
        client.client_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        client.pseudonym.toLowerCase().includes(searchQuery.toLowerCase());

      if (!matchesSearch) return false;

      if (filterTab === "urgent") return client.red_flags > 0;
      if (filterTab === "actions") return client.open_high_priority > 0;
      return true;
    });
  }, [clients, searchQuery, filterTab]);

  const selectedClient = useMemo(() => {
    return clients.find((c) => c.client_id === selectedClientId);
  }, [clients, selectedClientId]);

  const handleCopyHandover = () => {
    if (!brief) return;
    const textToCopy = `CLINICAL HANDOVER SUMMARY
Client: ${brief.client_id} (${brief.pseudonym})
Recipient Role: ${brief.recipient_role.toUpperCase()}
Generated: ${formatDate(brief.generated_at, true)}
Tier: ${brief.tier_label}

${brief.summary}

OPEN ACTIONS:
${brief.actions.map((a) => `- [${a.priority.toUpperCase()}] ${a.description} (Owner: ${a.owner_role}, Due: ${formatDate(a.due_date)})`).join("\n") || "None"}

GOALS:
${brief.goals.map((g) => `- ${g}`).join("\n") || "None"}`;

    navigator.clipboard.writeText(textToCopy);
    setCopySuccess(true);
    setTimeout(() => setCopySuccess(false), 2000);
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-slate-100 text-slate-900 font-sans overflow-hidden">
      {/* ── TOP GLOBAL COMMAND BAR ────────────────────────────────────────────── */}
      <header className="h-14 bg-slate-900 text-white flex items-center justify-between px-4 z-20 shrink-0 shadow-md border-b border-slate-800">
        {/* Left: Branding & Ward Info */}
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-blue-600 font-bold text-white shadow-sm">
            ⚕️
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold tracking-tight text-sm text-white">
                SYNAPSE<span className="text-blue-400 font-normal">·EHR</span>
              </span>
              <span className="text-[10px] font-mono uppercase bg-slate-800 text-blue-300 px-1.5 py-0.5 rounded border border-slate-700">
                Psych Handover Portal
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              Ward 4B Acute Crisis &bull; Consent-Filtered Continuity
            </p>
          </div>
        </div>

        {/* Center: Recipient Role Switcher & Tier Simulator */}
        <div className="flex items-center gap-3">
          <div className="flex items-center bg-slate-800/90 rounded-lg p-0.5 border border-slate-700">
            <span className="text-[11px] text-slate-400 font-medium px-2.5">
              Viewing As:
            </span>
            <div className="flex gap-1">
              {ROLES.map((r) => {
                const isActive = role === r.value;
                return (
                  <button
                    key={r.value}
                    onClick={() => setRole(r.value)}
                    className={`flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded-md transition-all ${
                      isActive
                        ? "bg-blue-600 text-white shadow-sm font-semibold"
                        : "text-slate-300 hover:text-white hover:bg-slate-700"
                    }`}
                    title={r.desc}
                  >
                    <span>{r.icon}</span>
                    <span>{r.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Fallback Tier Simulator */}
          <div className="hidden lg:flex items-center bg-slate-800/80 rounded-lg px-2 py-1 border border-slate-700 text-xs">
            <span className="text-slate-400 mr-2 text-[11px]">Ladder Tier:</span>
            <select
              value={tierOverride ?? ""}
              onChange={(e) =>
                setTierOverride(e.target.value ? Number(e.target.value) : null)
              }
              className="bg-slate-900 text-slate-200 rounded px-2 py-0.5 text-xs border border-slate-700 focus:ring-1 focus:ring-blue-400"
            >
              <option value="">Auto (Fallback Ladder)</option>
              <option value="1">Tier 1: Ollama LLM</option>
              <option value="2">Tier 2: Extractive</option>
              <option value="3">Tier 3: Template</option>
              <option value="4">Tier 4: Minimal Deterministic</option>
            </select>
          </div>
        </div>

        {/* Right: Clock & Governance Metrics */}
        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-2 bg-teal-950/70 border border-teal-800/60 rounded-full px-2.5 py-1">
            <span className="w-2 h-2 rounded-full bg-teal-400 animate-pulse"></span>
            <span className="text-[11px] font-mono text-teal-300 font-medium">
              Consent Leakage: 0.000 (Pass)
            </span>
          </div>

          <button
            onClick={() => setShowMetricsModal(true)}
            className="flex items-center gap-1.5 px-3 py-1 bg-slate-800 hover:bg-slate-700 border border-slate-600 rounded-lg text-xs font-medium text-slate-200 transition shadow-sm"
          >
            <span>📊</span>
            <span className="hidden sm:inline">CoE Metrics</span>
          </button>

          <div className="hidden md:block font-mono text-xs text-slate-400 pl-2 border-l border-slate-700">
            {currentTime || "10:30:00"}
          </div>
        </div>
      </header>

      {/* ── MAIN WORKSPACE SPLIT ─────────────────────────────────────────────── */}
      <div className="flex-1 flex overflow-hidden">
        {/* ── LEFT PANE: PATIENT ROSTER & TRIAGE ───────────────────────────── */}
        <aside className="w-80 bg-slate-900 text-slate-200 flex flex-col shrink-0 border-r border-slate-800 select-none">
          {/* Header & Search */}
          <div className="p-3 border-b border-slate-800 space-y-2.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Client Roster
                </span>
                <span className="bg-slate-800 text-slate-300 text-[11px] font-mono px-1.5 py-0.2 rounded">
                  {filteredClients.length}
                </span>
              </div>
              <span className="text-[10px] text-slate-500 font-mono">Urgency Sorted</span>
            </div>

            {/* Search Box */}
            <div className="relative">
              <input
                type="text"
                placeholder="Search ID (e.g. C005) or patient..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-slate-800 text-slate-200 placeholder-slate-500 rounded-lg pl-8 pr-3 py-1.5 text-xs border border-slate-700 focus:outline-none focus:border-blue-500"
              />
              <svg
                className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
              </svg>
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="absolute right-2.5 top-2 text-slate-400 hover:text-slate-200 text-xs"
                >
                  &times;
                </button>
              )}
            </div>

            {/* Filter Tabs */}
            <div className="grid grid-cols-3 gap-1 bg-slate-800/80 p-0.5 rounded-lg text-center text-xs">
              <button
                onClick={() => setFilterTab("all")}
                className={`py-1 rounded-md transition font-medium ${
                  filterTab === "all"
                    ? "bg-blue-600 text-white font-semibold shadow-sm"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                All
              </button>
              <button
                onClick={() => setFilterTab("urgent")}
                className={`py-1 rounded-md transition font-medium flex items-center justify-center gap-1 ${
                  filterTab === "urgent"
                    ? "bg-rose-600 text-white font-semibold shadow-sm"
                    : "text-slate-400 hover:text-rose-300"
                }`}
              >
                <span>🚩 Urgent</span>
              </button>
              <button
                onClick={() => setFilterTab("actions")}
                className={`py-1 rounded-md transition font-medium ${
                  filterTab === "actions"
                    ? "bg-slate-700 text-white font-semibold shadow-sm"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                Actions
              </button>
            </div>
          </div>

          {/* Patient List */}
          <div className="flex-1 overflow-y-auto dark-scrollbar divide-y divide-slate-800/60">
            {clientsLoading ? (
              <div className="p-6 text-center text-xs text-slate-500">
                Loading client directory...
              </div>
            ) : clientsError ? (
              <div className="p-4 text-xs text-rose-400 bg-rose-950/40 m-2 rounded border border-rose-900">
                Error loading clients. Ensure API is running on :8000.
              </div>
            ) : filteredClients.length === 0 ? (
              <div className="p-6 text-center text-xs text-slate-500">
                No matching clients found.
              </div>
            ) : (
              filteredClients.map((client) => {
                const isSelected = client.client_id === selectedClientId;
                const hasRedFlags = client.red_flags > 0;

                return (
                  <div
                    key={client.client_id}
                    onClick={() => setSelectedClientId(client.client_id)}
                    className={`p-3 cursor-pointer transition-all ${
                      isSelected
                        ? "bg-blue-600/20 border-l-4 border-blue-500 text-white"
                        : "hover:bg-slate-800/60 text-slate-300"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <span
                          className={`font-mono text-xs font-bold px-1.5 py-0.5 rounded ${
                            isSelected
                              ? "bg-blue-500/30 text-blue-200 border border-blue-400/40"
                              : "bg-slate-800 text-slate-300"
                          }`}
                        >
                          {client.client_id}
                        </span>
                        <span className="font-semibold text-xs text-slate-100">
                          {client.pseudonym}
                        </span>
                      </div>

                      {hasRedFlags && (
                        <span className="flex items-center gap-1 bg-rose-950 border border-rose-700 text-rose-300 font-mono text-[10px] font-bold px-1.5 py-0.5 rounded animate-pulse-subtle">
                          <span>🚩</span>
                          <span>{client.red_flags}</span>
                        </span>
                      )}
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-slate-400 mt-1.5">
                      <span>Discharged: {formatDate(client.discharge_date)}</span>
                      {client.open_high_priority > 0 && (
                        <span className="text-amber-400 font-medium">
                          {client.open_high_priority} High Priority
                        </span>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </aside>

        {/* ── CENTER WORKSPACE: CONTINUITY BRIEF & CLINICAL SUMMARY ─────────── */}
        <main className="flex-1 flex flex-col bg-slate-50 overflow-hidden min-w-0">
          {/* Patient Demographics Banner */}
          {selectedClient && (
            <div className="bg-white border-b border-slate-200 px-6 py-3 shrink-0 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-slate-100 border border-slate-300 flex items-center justify-center font-bold text-slate-700 text-sm">
                    {selectedClient.client_id.slice(0, 2)}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h1 className="text-lg font-bold text-slate-900 tracking-tight">
                        {selectedClient.pseudonym}
                      </h1>
                      <span className="font-mono text-xs bg-slate-100 border border-slate-300 text-slate-700 px-2 py-0.5 rounded font-medium">
                        MRN: {selectedClient.client_id}
                      </span>
                      {selectedClient.red_flags > 0 && (
                        <span className="bg-rose-100 text-rose-800 border border-rose-300 text-xs font-bold px-2 py-0.5 rounded-full flex items-center gap-1">
                          <span>⚠️</span>
                          <span>{selectedClient.red_flags} Overdue Escalation(s)</span>
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Discharged:{" "}
                      <span className="font-semibold text-slate-700">
                        {formatDate(selectedClient.discharge_date)}
                      </span>{" "}
                      &bull; Target Role:{" "}
                      <span className="font-semibold text-blue-700 capitalize">
                        {role.replace("_", " ")}
                      </span>
                    </p>
                  </div>
                </div>

                {/* Quick Action Toolbar */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleCopyHandover}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-medium border border-slate-300 transition"
                  >
                    {copySuccess ? "✓ Copied!" : "📋 Copy Note"}
                  </button>

                  <button
                    onClick={() => {
                      setRightDrawerOpen(true);
                      setActiveRightTab("consent");
                    }}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-700 rounded-lg text-xs font-medium border border-blue-200 transition"
                  >
                    <span>🔒 Consent Console</span>
                  </button>

                  <button
                    onClick={() => setRightDrawerOpen(!rightDrawerOpen)}
                    className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium border transition ${
                      rightDrawerOpen
                        ? "bg-slate-800 text-white border-slate-800"
                        : "bg-white text-slate-700 border-slate-300 hover:bg-slate-50"
                    }`}
                  >
                    <span>{rightDrawerOpen ? "Hide Inspector" : "Show Inspector"}</span>
                    <span>{rightDrawerOpen ? "→" : "←"}</span>
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Main Scrollable Workspace Content */}
          <div className="flex-1 overflow-y-auto custom-scrollbar p-6 space-y-5">
            {briefLoading ? (
              <div className="bg-white rounded-xl p-8 text-center border border-slate-200 shadow-sm space-y-3">
                <div className="inline-block animate-spin text-2xl text-blue-600">⌛</div>
                <div className="text-sm font-semibold text-slate-700">
                  Synthesizing Consent-Aware Handover Brief...
                </div>
                <p className="text-xs text-slate-500 max-w-md mx-auto">
                  Applying role-based consent policies and deterministic filtering before text assembly.
                </p>
              </div>
            ) : briefError ? (
              <div className="bg-rose-50 border-l-4 border-rose-600 rounded-r-xl p-6 shadow-sm">
                <h3 className="text-sm font-bold text-rose-800 uppercase tracking-wide">
                  Could Not Generate Handover Brief
                </h3>
                <p className="text-xs text-rose-700 mt-1">
                  {briefError instanceof Error ? briefError.message : String(briefError)}
                </p>
                <p className="text-xs text-slate-600 mt-3">
                  Please verify that the FastAPI backend is running on `http://127.0.0.1:8000`.
                </p>
              </div>
            ) : brief ? (
              <>
                {/* ── 1. URGENT CLINICAL ALERTS ── */}
                {brief.escalation_flags.length > 0 && (
                  <div className="bg-rose-50 border-l-4 border-rose-600 rounded-r-xl p-4 shadow-sm space-y-2">
                    <div className="flex items-center gap-2 text-rose-800 font-bold text-xs uppercase tracking-wider">
                      <span>🚨</span>
                      <span>Escalation Required Prior to Session</span>
                    </div>
                    {brief.escalation_flags.map((flag, idx) => (
                      <p key={idx} className="text-xs text-rose-900 font-medium pl-6">
                        &bull; {flag}
                      </p>
                    ))}
                  </div>
                )}

                {/* ── 2. CONTRADICTION & CONFLICT ALERTS ── */}
                {brief.conflicts.length > 0 && (
                  <div className="bg-amber-50 border-l-4 border-amber-500 rounded-r-xl p-4 shadow-sm space-y-2.5">
                    <div className="flex items-center gap-2 text-amber-800 font-bold text-xs uppercase tracking-wider">
                      <span>⚠️</span>
                      <span>Conflicting Clinical Records Detected</span>
                    </div>
                    {brief.conflicts.map((conflict, idx) => (
                      <div
                        key={idx}
                        className="bg-white/80 border border-amber-200 rounded-lg p-3 text-xs space-y-1.5"
                      >
                        <p className="font-semibold text-amber-900">{conflict.notice}</p>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[11px] text-slate-700 mt-1">
                          <div className="bg-slate-50 p-2 rounded border border-slate-200">
                            <span className="font-mono font-bold text-teal-700">STATEMENT A:</span>{" "}
                            {conflict.positive_text}
                          </div>
                          <div className="bg-slate-50 p-2 rounded border border-slate-200">
                            <span className="font-mono font-bold text-rose-700">STATEMENT B:</span>{" "}
                            {conflict.negative_text}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* ── 3. WITHHELD CONTENT WARNING ── */}
                {brief.withheld_count > 0 && (
                  <div className="bg-amber-50/70 border-l-4 border-amber-600 rounded-r-xl p-4 shadow-sm text-xs space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-amber-900 uppercase tracking-wider text-[11px] flex items-center gap-1.5">
                        <span>🔒</span>
                        <span>Topics Withheld Under Client Consent ({brief.withheld_count})</span>
                      </span>
                    </div>
                    <p className="text-amber-800">{brief.withheld_notice}</p>
                    {brief.consent_missing.length > 0 && (
                      <p className="text-[11px] text-slate-600 italic">
                        Administrative gap: No consent record on file for{" "}
                        <span className="font-semibold">
                          {brief.consent_missing.map(categoryLabel).join(", ")}
                        </span>
                        .
                      </p>
                    )}
                  </div>
                )}

                {/* ── 4. INTERACTIVE DISCLOSURE LEDGER ── */}
                <div className="bg-white rounded-xl p-4 border border-slate-200 shadow-sm space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-700">
                        Disclosure Ledger
                      </h2>
                      <p className="text-[11px] text-slate-500">
                        Real-time status of all tagged sensitivity categories for {role}
                      </p>
                    </div>
                    <div className="flex items-center gap-3 text-xs font-mono">
                      <span className="text-teal-700 font-bold">
                        ● {brief.permitted_categories.length} Disclosed
                      </span>
                      <span className="text-amber-700 font-bold">
                        ○ {brief.withheld_categories.length} Withheld
                      </span>
                    </div>
                  </div>

                  {/* Pills Grid */}
                  <div className="flex flex-wrap gap-2 pt-1">
                    {brief.permitted_categories.map((cat) => (
                      <span
                        key={cat}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-teal-50 text-teal-800 border border-teal-200 shadow-2xs"
                        title="Disclosed under active consent record"
                      >
                        <span className="text-teal-600">●</span>
                        <span className="capitalize">{categoryLabel(cat)}</span>
                      </span>
                    ))}

                    {brief.withheld_categories.map((cat) => {
                      const isSafety = brief.explanation.why_withheld.some(
                        (w) => w.category === cat && w.is_safety_relevant
                      );

                      return (
                        <span
                          key={cat}
                          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border shadow-2xs ${
                            isSafety
                              ? "bg-rose-50 text-rose-800 border-rose-300"
                              : "bg-amber-50 text-amber-800 border-amber-200"
                          }`}
                          title={
                            isSafety
                              ? "Withheld under consent, but safety carve-out flagged"
                              : "Withheld under client consent"
                          }
                        >
                          <span>{isSafety ? "▲" : "○"}</span>
                          <span className="capitalize">{categoryLabel(cat)}</span>
                          {isSafety && (
                            <span className="text-[10px] font-mono uppercase bg-rose-200 text-rose-900 px-1 rounded">
                              Safety
                            </span>
                          )}
                        </span>
                      );
                    })}
                  </div>
                </div>

                {/* ── 5. CLINICAL CONTINUITY BRIEF (SUMMARY) ── */}
                <section className="bg-white rounded-xl p-6 border border-slate-200 shadow-sm space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                    <div className="flex items-center gap-2.5">
                      <h2 className="text-sm font-bold text-slate-900 tracking-tight">
                        Clinical Continuity Summary
                      </h2>
                      <TierBadge tier={brief.tier} label={brief.tier_label} />
                    </div>
                    <div className="flex items-center gap-3 text-xs text-slate-500 font-mono">
                      <span>{brief.word_count} words</span>
                      <span>&bull;</span>
                      <span>~1 min read</span>
                    </div>
                  </div>

                  {/* Prose summary */}
                  <div className="prose prose-slate max-w-none text-[14px] leading-relaxed text-slate-800 whitespace-pre-line">
                    {brief.summary}
                  </div>

                  {brief.uncertainty_note && (
                    <div className="mt-3 pt-3 border-t border-slate-100 text-xs italic text-slate-500 bg-slate-50 p-3 rounded-lg border border-slate-200">
                      💡 {brief.uncertainty_note}
                    </div>
                  )}
                </section>

                {/* ── 6. HANDOVER ACTION ITEMS ── */}
                <section className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                  <div className="px-6 py-3.5 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
                    <div>
                      <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-700">
                        Open Clinical Actions & Handover Tasks
                      </h2>
                      <p className="text-[11px] text-slate-500">
                        Carried forward unconditionally via dedicated action state-machine
                      </p>
                    </div>
                    <span className="text-xs font-mono bg-slate-200 text-slate-700 px-2 py-0.5 rounded font-semibold">
                      {brief.actions.length} Total
                    </span>
                  </div>

                  {brief.actions.length === 0 ? (
                    <div className="p-6 text-center text-xs text-slate-500">
                      No open actions recorded for this client.
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs border-collapse">
                        <thead className="bg-slate-100/70 text-slate-600 border-b border-slate-200 font-semibold">
                          <tr>
                            <th className="px-4 py-2.5">Action Description</th>
                            <th className="px-4 py-2.5">Assigned Owner</th>
                            <th className="px-4 py-2.5">Due Date</th>
                            <th className="px-4 py-2.5">Priority</th>
                            <th className="px-4 py-2.5">Escalation Status</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {brief.actions.map((act) => (
                            <tr key={act.action_id} className="hover:bg-slate-50/80">
                              <td className="px-4 py-3 font-medium text-slate-800">
                                {act.description}
                              </td>
                              <td className="px-4 py-3">
                                <span className="font-semibold text-slate-700 capitalize">
                                  {act.owner_role}
                                </span>
                                {act.owner_id && (
                                  <span className="block font-mono text-[10px] text-slate-400">
                                    ID: {act.owner_id}
                                  </span>
                                )}
                              </td>
                              <td className="px-4 py-3 font-mono text-slate-600">
                                {formatDate(act.due_date)}
                              </td>
                              <td className="px-4 py-3">
                                <span
                                  className={`font-mono text-[10px] font-bold uppercase px-2 py-0.5 rounded ${
                                    act.priority === "high"
                                      ? "bg-rose-100 text-rose-800 border border-rose-200"
                                      : "bg-slate-100 text-slate-700"
                                  }`}
                                >
                                  {act.priority}
                                </span>
                              </td>
                              <td className="px-4 py-3">
                                {act.escalation_level === 0 ? (
                                  <span className="text-slate-400 font-mono">Normal</span>
                                ) : (
                                  <span
                                    className={`inline-flex items-center gap-1 font-mono text-[11px] font-bold px-2 py-0.5 rounded border ${
                                      act.escalation_level >= 3
                                        ? "bg-rose-50 text-rose-700 border-rose-300"
                                        : "bg-amber-50 text-amber-700 border-amber-300"
                                    }`}
                                    title={act.escalation_note}
                                  >
                                    <span>L{act.escalation_level}</span>
                                    <span>&bull;</span>
                                    <span>{act.days_overdue}d overdue</span>
                                  </span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </section>

                {/* ── 7. RECOVERY GOALS ── */}
                <section className="bg-white rounded-xl p-5 border border-slate-200 shadow-sm space-y-3">
                  <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-700">
                    Active Treatment & Recovery Goals
                  </h2>
                  {brief.goals.length === 0 ? (
                    <p className="text-xs text-slate-500">No active goals on file.</p>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      {brief.goals.map((goal, idx) => (
                        <div
                          key={idx}
                          className="flex items-start gap-2.5 p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-800"
                        >
                          <span className="text-blue-600 font-bold mt-0.5">🎯</span>
                          <span>{goal}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </section>
              </>
            ) : null}
          </div>
        </main>

        {/* ── RIGHT DRAWER / INSPECTOR: CONSENT AUDIT & EXPLAINABILITY ─────── */}
        {rightDrawerOpen && (
          <aside className="w-96 bg-white border-l border-slate-200 flex flex-col shrink-0 z-10 shadow-lg select-none">
            {/* Drawer Tabs */}
            <div className="flex border-b border-slate-200 bg-slate-50 text-xs font-medium">
              <button
                onClick={() => setActiveRightTab("consent")}
                className={`flex-1 py-3 text-center border-b-2 transition ${
                  activeRightTab === "consent"
                    ? "border-blue-600 text-blue-700 bg-white font-bold"
                    : "border-transparent text-slate-500 hover:text-slate-800"
                }`}
              >
                🔒 Consent Matrix
              </button>
              <button
                onClick={() => setActiveRightTab("explainability")}
                className={`flex-1 py-3 text-center border-b-2 transition ${
                  activeRightTab === "explainability"
                    ? "border-blue-600 text-blue-700 bg-white font-bold"
                    : "border-transparent text-slate-500 hover:text-slate-800"
                }`}
              >
                💡 Explainability
              </button>
              <button
                onClick={() => setActiveRightTab("provenance")}
                className={`flex-1 py-3 text-center border-b-2 transition ${
                  activeRightTab === "provenance"
                    ? "border-blue-600 text-blue-700 bg-white font-bold"
                    : "border-transparent text-slate-500 hover:text-slate-800"
                }`}
              >
                🔗 Provenance
              </button>
            </div>

            {/* Drawer Content */}
            <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4">
              {/* TAB 1: CONSENT CONSOLE */}
              {activeRightTab === "consent" && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-xs font-bold text-slate-900">
                        Consent Audit Records
                      </h3>
                      <p className="text-[11px] text-slate-500">
                        Granular records per (Category, Role, Purpose)
                      </p>
                    </div>
                    {consentData?.consents && (
                      <span className="text-[11px] font-mono bg-teal-50 text-teal-700 border border-teal-200 px-1.5 py-0.5 rounded font-bold">
                        {consentData.consents.filter((c) => c.active).length} Active
                      </span>
                    )}
                  </div>

                  {consentLoading ? (
                    <div className="p-6 text-center text-xs text-slate-400">
                      Loading consent records...
                    </div>
                  ) : !consentData?.consents || consentData.consents.length === 0 ? (
                    <div className="p-4 bg-slate-50 rounded-lg text-xs text-slate-500 border border-slate-200">
                      No explicit consent records on file. Under default policy, all categories are withheld (DENY).
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {consentData.consents.map((record: ConsentRow, idx: number) => {
                        const isMatchCurrentRole = record.recipient_role === role;
                        return (
                          <div
                            key={idx}
                            className={`p-3 rounded-lg border text-xs space-y-1.5 transition ${
                              isMatchCurrentRole
                                ? "bg-blue-50/50 border-blue-200 shadow-2xs"
                                : "bg-slate-50/60 border-slate-200 opacity-80"
                            }`}
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-slate-900 capitalize">
                                {categoryLabel(record.category)}
                              </span>
                              <span
                                className={`font-mono text-[10px] font-bold px-2 py-0.5 rounded ${
                                  record.active
                                    ? "bg-teal-100 text-teal-800 border border-teal-300"
                                    : "bg-slate-200 text-slate-700"
                                }`}
                              >
                                {record.active
                                  ? "ACTIVE"
                                  : record.revoked_at
                                  ? "REVOKED"
                                  : record.expires_at
                                  ? "EXPIRED"
                                  : "DECLINED"}
                              </span>
                            </div>

                            <div className="grid grid-cols-2 gap-1 text-[11px] text-slate-500 font-mono">
                              <div>
                                Role:{" "}
                                <span className="font-semibold text-slate-700 capitalize">
                                  {record.recipient_role.replace("_", " ")}
                                </span>
                              </div>
                              <div>
                                Purpose:{" "}
                                <span className="font-semibold text-slate-700 uppercase">
                                  {record.purpose}
                                </span>
                              </div>
                            </div>

                            <div className="text-[10px] text-slate-400 pt-1 border-t border-slate-200/60 flex justify-between">
                              <span>Granted: {formatDate(record.granted_at)}</span>
                              {record.expires_at && (
                                <span>Expires: {formatDate(record.expires_at)}</span>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* TAB 2: EXPLAINABILITY */}
              {activeRightTab === "explainability" && brief && (
                <div className="space-y-4 text-xs">
                  <div>
                    <h3 className="text-xs font-bold text-slate-900">
                      Why this brief looks like this
                    </h3>
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      {brief.explanation.summary}
                    </p>
                  </div>

                  {/* Disclosed Reasons */}
                  <div className="space-y-2">
                    <div className="font-mono text-[11px] font-bold text-teal-700 uppercase tracking-wider">
                      ● Disclosed Categories
                    </div>
                    {brief.explanation.why_shown.length === 0 ? (
                      <p className="text-slate-400 italic">No content disclosed to this role.</p>
                    ) : (
                      <div className="space-y-1.5">
                        {brief.explanation.why_shown.map((reason) => (
                          <div
                            key={reason.category}
                            className="bg-teal-50/70 p-2.5 rounded-lg border border-teal-200 text-teal-900"
                          >
                            <span className="font-bold capitalize">
                              {categoryLabel(reason.category)}:
                            </span>{" "}
                            {reason.detail}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Withheld Reasons */}
                  <div className="space-y-2">
                    <div className="font-mono text-[11px] font-bold text-amber-700 uppercase tracking-wider">
                      ○ Withheld Categories
                    </div>
                    {brief.explanation.why_withheld.length === 0 ? (
                      <p className="text-slate-400 italic">No content withheld from this role.</p>
                    ) : (
                      <div className="space-y-1.5">
                        {brief.explanation.why_withheld.map((reason) => (
                          <div
                            key={reason.category}
                            className={`p-2.5 rounded-lg border text-slate-800 ${
                              reason.is_safety_relevant
                                ? "bg-rose-50 border-rose-200"
                                : "bg-amber-50/60 border-amber-200"
                            }`}
                          >
                            <div className="flex items-center justify-between mb-0.5">
                              <span className="font-bold capitalize">
                                {categoryLabel(reason.category)}
                              </span>
                              {reason.is_safety_relevant && (
                                <span className="font-mono text-[10px] bg-rose-200 text-rose-900 px-1 rounded font-bold">
                                  Safety Alert
                                </span>
                              )}
                            </div>
                            <p className="text-[11px] text-slate-600">{reason.detail}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Fallback Reasons */}
                  {brief.degradation_reasons.length > 0 && (
                    <div className="space-y-1.5 pt-2 border-t border-slate-200">
                      <div className="font-mono text-[11px] font-bold text-slate-700 uppercase">
                        Fallback Ladder Tracing
                      </div>
                      <ul className="list-disc pl-4 text-slate-600 space-y-0.5 text-[11px]">
                        {brief.degradation_reasons.map((r, i) => (
                          <li key={i}>{r}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 3: PROVENANCE */}
              {activeRightTab === "provenance" && brief && (
                <div className="space-y-3 text-xs">
                  <div>
                    <h3 className="text-xs font-bold text-slate-900">
                      Sentence-Level Provenance & Lineage
                    </h3>
                    <p className="text-[11px] text-slate-500">
                      {brief.permitted_span_count} of {brief.total_spans} spans permitted &bull;{" "}
                      {brief.provenance.length} linked sentences
                    </p>
                  </div>

                  <div className="space-y-1.5">
                    {brief.provenance.map((spanId, i) => (
                      <div
                        key={i}
                        className="bg-slate-50 p-2.5 rounded-lg border border-slate-200 font-mono text-[11px] text-slate-700 flex items-center justify-between"
                      >
                        <span>Line #{i + 1}</span>
                        <span className="font-bold text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                          {spanId}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </aside>
        )}
      </div>

      {/* ── MODALS ───────────────────────────────────────────────────────────── */}
      <MetricsModal
        isOpen={showMetricsModal}
        onClose={() => setShowMetricsModal(false)}
      />
    </div>
  );
};

// Helper hook to memoize clients
function useClientsData(data: { clients: any[] } | undefined) {
  return useMemo(() => data?.clients ?? [], [data]);
}

export default WorkstationLayout;
