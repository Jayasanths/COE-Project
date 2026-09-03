/**
 * API client and response types.
 *
 * Types mirror the Pydantic response models in `src/routers/briefs.py`.
 */

export const API_BASE = "/api";

export type RecipientRole = "counsellor" | "social_worker" | "psychiatrist" | "nurse";

export const ROLES: { value: RecipientRole; label: string; icon: string; desc: string }[] = [
  { value: "counsellor", label: "Counsellor", icon: "💬", desc: "Psychological support & therapy" },
  { value: "social_worker", label: "Social Worker", icon: "🤝", desc: "Community & housing resources" },
  { value: "psychiatrist", label: "Psychiatrist", icon: "🩺", desc: "Diagnostic & medical management" },
  { value: "nurse", label: "Ward Nurse", icon: "📋", desc: "Direct nursing & inpatient care" },
];

export interface ClientRow {
  client_id: string;
  pseudonym: string;
  discharge_date: string;
  open_high_priority: number;
  red_flags: number;
}

export interface ActionItem {
  action_id: string;
  description: string;
  owner_role: string;
  owner_id: string;
  due_date: string;
  priority: string;
  status: string;
  escalation_level: number;
  days_overdue: number;
  escalation_note: string;
}

export interface WithheldReason {
  category: string;
  reason_code: string;
  detail: string;
  is_safety_relevant: boolean;
}

export interface Conflict {
  category: string;
  positive_label: string;
  negative_label: string;
  positive_text: string;
  negative_text: string;
  notice: string;
}

export interface Brief {
  client_id: string;
  pseudonym: string;
  recipient_role: string;
  purpose: string;
  generated_at: string;

  tier: number;
  tier_label: string;
  summary: string;
  facts: Record<string, unknown> | null;
  word_count: number;

  permitted_categories: string[];
  withheld_count: number;
  withheld_categories: string[];
  withheld_notice: string;

  escalation_flags: string[];
  notifications: string[];
  conflicts: Conflict[];
  conflict_notices: string[];
  consent_missing: string[];

  actions: ActionItem[];
  goals: string[];

  explanation: {
    summary: string;
    why_shown: { category: string; detail: string }[];
    why_withheld: WithheldReason[];
  };
  uncertainty_note: string;
  provenance: string[];
  degradation_reasons: string[];
  total_spans: number;
  permitted_span_count: number;
}

export interface ConsentRow {
  category: string;
  recipient_role: string;
  purpose: string;
  granted: boolean;
  granted_at: string;
  expires_at: string | null;
  revoked_at: string | null;
  active: boolean;
}

export interface MetricItem {
  metric: string;
  definition: string;
  target: string;
  baseline: number;
  prototype: number;
  delta: number;
  passed: boolean;
  error_analysis: string;
}

export interface MetricsReport {
  eval_date: string;
  role: string;
  purpose: string;
  n_clients: number;
  tier_distribution: Record<string, number>;
  metrics: MetricItem[];
  all_passed: boolean;
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* fallback */
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export const api = {
  listClients: () => getJson<{ clients: ClientRow[] }>("/clients/"),
  getBrief: (clientId: string, role: RecipientRole, tier?: number | null) => {
    const tierQuery = tier ? `&tier=${tier}` : "";
    return getJson<Brief>(`/briefs/${clientId}?role=${role}&purpose=handover${tierQuery}`);
  },
  getConsent: (clientId: string) =>
    getJson<{ client_id: string; pseudonym: string; consents: ConsentRow[] }>(
      `/consent/${clientId}`,
    ),
};

/** Render a sensitivity category id as a human label. */
export function categoryLabel(category: string): string {
  return category.replace(/_/g, " ");
}

/** Date formatting with time option */
export function formatDate(iso: string, includeTime = false): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso.slice(0, 10);
  
  if (includeTime) {
    return date.toLocaleDateString(undefined, {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }
  return date.toLocaleDateString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}
