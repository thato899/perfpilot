/**
 * Investigation event mapping — issue #37 (P2-UI-1).
 *
 * The server is the only source of timeline truth. #35 persists an
 * append-only `investigation_event` table and exposes it through
 * `GET /api/investigations/{id}` as an ordered `events` array, each carrying a
 * per-investigation monotonic `sequence`. This module turns those rows into
 * something renderable and does nothing else: it never infers a transition the
 * server did not record, never fills a gap, and never advances state on a
 * timer.
 *
 * docs/phase2/p2-api-2-investigation-state.md is explicit about the one rule
 * that matters here: "consume `experiment_budget`, typed statuses, stable
 * entity IDs, and ordered `events`; do not infer timeline order from array
 * position". Everything below sorts on `sequence`.
 */

import type { InvestigationEvent, InvestigationState } from "@perfpilot/schemas/types";

/**
 * The event types #35 emits today, in the order `InvestigationEventType`
 * declares them (packages/schemas/python/entities.py).
 *
 * This list is a presentation concern, not a validator. A server that adds a
 * type is not an error — see `describeEvent`, which renders an unrecognised
 * type rather than dropping it. Dropping would be the one genuinely unsafe
 * option: the user would see a gap in history with no indication anything was
 * missing.
 */
export const KNOWN_EVENT_TYPES = [
  "investigation_created",
  "test_run_queued",
  "test_run_started",
  "test_run_completed",
  "finding_recorded",
  "hypothesis_recorded",
  "experiment_proposed",
  "experiment_approved",
  "experiment_started",
  "experiment_completed",
  "recommendation_recorded",
  "budget_exhausted",
  "continue_requested",
  "report_persisted",
] as const;

export type KnownEventType = (typeof KNOWN_EVENT_TYPES)[number];

/** Coarse grouping, used only for visual grouping and the a11y label. */
export type TimelinePhase =
  "planning" | "execution" | "analysis" | "approval" | "reporting" | "control";

export interface RelatedId {
  label: string;
  value: string;
}

export interface TimelineEntry {
  /** The server event's UUID. Stable across polls, so it is the React key. */
  id: string;
  /** Per-investigation monotonic ordinal. The sort key, and displayed. */
  sequence: number;
  type: string;
  /** False when the server sent a type this build does not know about. */
  known: boolean;
  label: string;
  /** Built only from payload fields that are actually present. */
  detail?: string;
  phase: TimelinePhase;
  occurredAt: string;
  relatedIds: RelatedId[];
  idempotencyKey?: string;
}

interface EventPresentation {
  label: string;
  phase: TimelinePhase;
}

const PRESENTATION: Record<KnownEventType, EventPresentation> = {
  investigation_created: { label: "Investigation created", phase: "planning" },
  test_run_queued: { label: "Test run queued", phase: "execution" },
  test_run_started: { label: "Test run started", phase: "execution" },
  test_run_completed: { label: "Test run completed", phase: "execution" },
  finding_recorded: { label: "Finding recorded", phase: "analysis" },
  hypothesis_recorded: { label: "Hypothesis recorded", phase: "analysis" },
  experiment_proposed: { label: "Experiment proposed", phase: "analysis" },
  experiment_approved: { label: "Experiment approved", phase: "approval" },
  experiment_started: { label: "Experiment started", phase: "execution" },
  experiment_completed: { label: "Experiment completed", phase: "execution" },
  recommendation_recorded: { label: "Recommendation recorded", phase: "reporting" },
  budget_exhausted: { label: "Experiment budget exhausted", phase: "control" },
  continue_requested: { label: "Continuation requested", phase: "control" },
  report_persisted: { label: "Report persisted", phase: "reporting" },
};

const KNOWN_EVENT_SET: ReadonlySet<string> = new Set<string>(KNOWN_EVENT_TYPES);

export function isKnownEventType(type: string): type is KnownEventType {
  return KNOWN_EVENT_SET.has(type);
}

/** "experiment_budget_exhausted" -> "Experiment budget exhausted". */
function humanise(value: string): string {
  const spaced = value.replaceAll("_", " ").trim();
  if (!spaced) return value;
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

function readString(payload: Record<string, unknown>, key: string): string | undefined {
  const value = payload[key];
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function readNumber(payload: Record<string, unknown>, key: string): number | undefined {
  const value = payload[key];
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

/**
 * Pull the stable entity IDs out of a payload for display.
 *
 * Deliberately keyed on the exact field names the API writes rather than
 * "anything ending in _id": a rename on the server should show up as a missing
 * ID in the UI, not as a silently reinterpreted one.
 */
const ID_FIELDS: ReadonlyArray<readonly [string, string]> = [
  ["test_run_id", "Run"],
  ["experiment_id", "Experiment"],
  ["hypothesis_id", "Hypothesis"],
  ["finding_id", "Finding"],
  ["recommendation_id", "Recommendation"],
  ["investigation_id", "Investigation"],
  ["target_id", "Target"],
];

function relatedIds(payload: Record<string, unknown>): RelatedId[] {
  const out: RelatedId[] = [];
  for (const [field, label] of ID_FIELDS) {
    const value = readString(payload, field);
    if (value) out.push({ label, value });
  }
  return out;
}

/**
 * The human sentence for one event.
 *
 * Every branch reads from the payload and returns undefined when the field is
 * absent. There is no default sentence: a detail line the server did not
 * supply is a fabricated detail line, which is exactly what this ticket says
 * the client must never produce.
 */
function detailFor(type: string, payload: Record<string, unknown>): string | undefined {
  switch (type) {
    case "investigation_created": {
      const objective = readString(payload, "objective");
      return objective ? `Objective: ${humanise(objective).toLowerCase()}` : undefined;
    }
    case "test_run_queued": {
      const kind = readString(payload, "kind");
      return kind ? `Queued as the ${kind} run` : undefined;
    }
    case "test_run_completed":
    case "experiment_completed": {
      const status = readString(payload, "status");
      return status ? `Reported ${humanise(status).toLowerCase()}` : undefined;
    }
    case "continue_requested": {
      const next = readString(payload, "next_action");
      return next ? `Orchestrator chose: ${humanise(next).toLowerCase()}` : undefined;
    }
    case "budget_exhausted": {
      const consumed = readNumber(payload, "consumed");
      const max = readNumber(payload, "max_experiments");
      return consumed !== undefined && max !== undefined
        ? `${consumed} of ${max} experiments used`
        : undefined;
    }
    default:
      return undefined;
  }
}

export function describeEvent(event: InvestigationEvent): TimelineEntry {
  // Narrowed through the type guard rather than through a separate boolean:
  // `known` would not tell the compiler anything about `event.type`.
  const type = event.type;
  const known = isKnownEventType(type);
  const presentation = known
    ? PRESENTATION[type]
    : // An unrecognised type still gets a row, a sequence and a timestamp. It
      // is marked so the UI can say "this build does not recognise this event"
      // instead of implying the row is fully understood.
      { label: humanise(type), phase: "control" as TimelinePhase };
  const payload = event.payload ?? {};

  return {
    id: event.id,
    sequence: event.sequence,
    type: event.type,
    known,
    label: presentation.label,
    detail: detailFor(event.type, payload),
    phase: presentation.phase,
    occurredAt: event.occurredAt,
    relatedIds: relatedIds(payload),
    idempotencyKey: event.idempotencyKey,
  };
}

/**
 * Order the server's events for display.
 *
 * Three things happen here, all of them load-bearing:
 *
 * 1. Sorting is on `sequence`, never on array position. The API happens to
 *    return them ordered today; relying on that would make the UI silently
 *    wrong the first time a page, a merge or a reconnect delivered them in
 *    another order.
 * 2. Duplicate event IDs collapse to one row. A reconnect or an overlapping
 *    poll can deliver the same event twice; rendering it twice would read as
 *    two transitions that never happened.
 * 3. A tie on `sequence` — which the server's per-investigation counter should
 *    make impossible — falls back to the event ID so the order is at least
 *    stable between renders rather than flickering.
 */
export function toTimeline(events: readonly InvestigationEvent[] | undefined): TimelineEntry[] {
  if (!events || events.length === 0) return [];

  const byId = new Map<string, InvestigationEvent>();
  for (const event of events) {
    if (!byId.has(event.id)) byId.set(event.id, event);
  }

  return [...byId.values()]
    .sort((a, b) =>
      a.sequence === b.sequence ? a.id.localeCompare(b.id) : a.sequence - b.sequence,
    )
    .map(describeEvent);
}

/**
 * True when the sequences are not 1..n with no holes.
 *
 * A gap means this client is looking at a partial history — a page boundary,
 * or events the server has not returned. The UI says so rather than presenting
 * an incomplete timeline as the whole story.
 */
export function hasSequenceGap(entries: readonly TimelineEntry[]): boolean {
  if (entries.length === 0) return false;
  if (entries[0].sequence !== 1) return true;
  return entries.some(
    (entry, index) => index > 0 && entry.sequence !== entries[index - 1].sequence + 1,
  );
}

export function latestSequence(entries: readonly TimelineEntry[]): number | undefined {
  return entries.length ? entries[entries.length - 1].sequence : undefined;
}

/**
 * What the investigation is doing right now, read from the server's status.
 *
 * Derived from `status` rather than from the last event on purpose: the status
 * column is what the Orchestrator owns and writes, while the last event is
 * only the most recent thing that happened to have been recorded. When a run
 * is mid-flight those two can disagree, and the status is the one the backend
 * considers authoritative.
 */
export function currentAction(status: InvestigationState["status"]): string {
  switch (status) {
    case "planning":
      return "Planning the next test";
    case "running":
      return "Running a test";
    case "investigating":
      return "Analysing results";
    case "experimenting":
      return "Running an approved experiment";
    case "reporting":
      return "Writing the report";
    case "complete":
      return "Complete";
    case "failed":
      return "Failed";
    default:
      return humanise(status);
  }
}

export function isTerminalStatus(status: InvestigationState["status"]): boolean {
  return status === "complete" || status === "failed";
}

/**
 * Render a server timestamp as a fixed, locale-independent UTC string.
 *
 * `toLocaleString` would render differently per machine, which makes the
 * component tests depend on the runner's timezone. Timestamps are shown in
 * UTC, labelled as such, with the raw ISO value kept in the <time> element's
 * dateTime attribute for anyone who needs the exact value.
 */
export function formatTimestamp(iso: string): string {
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return iso;
  return `${parsed.toISOString().slice(0, 19).replace("T", " ")} UTC`;
}
