// TS port of ui/progress.py. Pure functions, unit-tested in progress.test.ts.

import {
  CANDIDATE_STAGE_LABELS,
  EVENT_TYPE_LABELS,
  NODE_LABELS,
  S,
} from "@/lib/strings";
import type {
  CandidateRunResult,
  DecisionEvent,
  DocumentSummary,
  RunSummary,
} from "@/lib/types";

const COMPLETION_BY_NODE: Record<string, string> = {
  extract_jd_rubric: "rubric_extracted",
  extract_candidate_profile: "candidate_profile_extracted",
  score_candidate: "recommendation_derived",
  generate_interview_pack: "questions_generated",
};

export interface ActivityRow {
  time: string;
  label: string;
  latency_ms: number | null;
}

export interface CandidateRow {
  label: string;
  stage: string;
  done: boolean;
}

export interface ProgressSnapshot {
  headline: string;
  step_label: string;
  progress: number;
  elapsed_s: number;
  idle_s: number;
  resume_total: number;
  completed_count: number;
  event_count: number;
  pending_llm: boolean;
  activity_rows: ActivityRow[];
  candidate_rows: CandidateRow[];
}

// Loose event shape: the python version reads plain dicts. We accept partials so
// the unit tests can mirror test_ui_progress.py exactly.
type LooseEvent = Partial<DecisionEvent> & {
  event_type?: string;
  node_name?: string;
  candidate_id?: string | null;
  timestamp?: string;
  metadata?: Record<string, unknown> | null;
  latency_ms?: number | null;
};

type LooseRun = Partial<RunSummary> & {
  status?: string;
  started_at?: string | null;
  created_at?: string | null;
};

type LooseDocument = Partial<DocumentSummary> & {
  source_type?: string;
  filename?: string;
};

type LooseCandidate = Partial<CandidateRunResult> & {
  candidate_id?: string;
  status?: string;
};

function parseTs(value: string): Date {
  // Accept ISO strings; treat naive timestamps as UTC, mirroring _parse_ts.
  const text = value.replace("Z", "+00:00");
  const hasTz = /[+-]\d{2}:?\d{2}$/.test(text) || text.endsWith("+00:00");
  return new Date(hasTz ? text : `${text}Z`);
}

function metaName(event: LooseEvent): string | undefined {
  const name = event.metadata?.["candidate_name"];
  return typeof name === "string" ? name : undefined;
}

export function eventLabel(event: LooseEvent): string {
  const eventType = event.event_type ?? "";
  const base = EVENT_TYPE_LABELS[eventType] ?? eventType;
  const nodeName = event.node_name ?? "";
  const node = NODE_LABELS[nodeName] ?? nodeName;
  let name = metaName(event);
  if (!name && event.candidate_id) {
    name = event.candidate_id.slice(0, 8);
  }
  const parts = [base];
  if (node) parts.push(node);
  if (name) parts.push(`「${name}」`);
  let label = parts.join(" · ");
  if (eventType === "schema_validation_failed") {
    const errors = (event.metadata?.["errors"] as unknown[]) ?? [];
    if (errors.length > 0) {
      let detail = String(errors[0]).replace(/\n/g, " ");
      if (detail.length > 100) detail = detail.slice(0, 97) + "…";
      label = `${label} — ${detail}`;
    }
  }
  return label;
}

function resumeFilenames(documents: LooseDocument[]): string[] {
  return documents
    .filter((doc) => doc.source_type === "resume")
    .map((doc) => doc.filename ?? "");
}

function candidateNames(events: LooseEvent[]): Record<string, string> {
  const names: Record<string, string> = {};
  for (const event of events) {
    const candidateId = event.candidate_id;
    if (!candidateId) continue;
    const name = metaName(event);
    if (name) names[candidateId] = name;
  }
  return names;
}

function pendingLlm(events: LooseEvent[]): LooseEvent | null {
  for (let index = events.length - 1; index >= 0; index--) {
    const event = events[index];
    if (event.event_type !== "llm_call_started") continue;
    const node = event.node_name ?? "";
    const completion = COMPLETION_BY_NODE[node];
    const candidateId = event.candidate_id ?? null;
    let completed = false;
    for (const later of events.slice(index + 1)) {
      if (completion && later.event_type === completion) {
        if (candidateId === null || later.candidate_id === candidateId) {
          completed = true;
          break;
        }
      }
      if (
        later.event_type === "dossier_completed" &&
        later.candidate_id === candidateId
      ) {
        completed = true;
        break;
      }
    }
    if (!completed) return event;
  }
  return null;
}

function candidateStage(events: LooseEvent[], candidateId: string): string {
  const types = new Set(
    events
      .filter((event) => event.candidate_id === candidateId)
      .map((event) => event.event_type),
  );
  if (types.has("dossier_completed")) return "done";
  if (types.has("questions_generated")) return "assemble";
  if (types.has("recommendation_derived")) return "interview";
  if (types.has("candidate_profile_extracted")) return "score";
  return "profile";
}

export function buildProgressSnapshot(args: {
  run: LooseRun;
  documents: LooseDocument[];
  candidates: LooseCandidate[];
  events: LooseEvent[];
  now?: Date;
}): ProgressSnapshot {
  const { run, documents, candidates, events } = args;
  const now = args.now ?? new Date();

  const startedAt = run.started_at || run.created_at;
  let elapsedS = 0;
  if (startedAt) {
    elapsedS = Math.max(0, (now.getTime() - parseTs(startedAt).getTime()) / 1000);
  }

  const eventTypes = new Set(events.map((event) => event.event_type));
  const resumes = resumeFilenames(documents);
  const resumeTotal = Math.max(resumes.length, 1);
  const names = candidateNames(events);
  const pending = pendingLlm(events);

  const completedIds = new Set<string>();
  for (const event of events) {
    if (event.event_type === "dossier_completed" && event.candidate_id) {
      completedIds.add(event.candidate_id);
    }
  }
  for (const candidate of candidates) {
    if (
      candidate.status &&
      ["completed", "needs_review", "failed"].includes(candidate.status) &&
      candidate.candidate_id
    ) {
      completedIds.add(candidate.candidate_id);
    }
  }

  const activeIds: string[] = [];
  const seenIds = new Set<string>();
  for (const event of events) {
    const candidateId = event.candidate_id;
    if (candidateId && !seenIds.has(candidateId)) {
      seenIds.add(candidateId);
      activeIds.push(candidateId);
    }
  }

  let headline: string;
  let stepLabel: string;
  let progress: number;

  if (run.status === "queued") {
    headline = S.progressQueued;
    stepLabel = S.progressStepIngest;
    progress = 0.02;
  } else if (!eventTypes.has("rubric_extracted")) {
    headline = S.progressRubric;
    stepLabel = S.progressStepRubric;
    progress = 0.08;
    if (pending && pending.node_name === "extract_jd_rubric") {
      headline = S.progressLlmWait(NODE_LABELS["extract_jd_rubric"]);
      progress = 0.12;
    }
  } else if (completedIds.size >= resumeTotal) {
    headline = S.progressAggregating;
    stepLabel = S.progressStepRubric;
    progress = 0.98;
  } else {
    progress = 0.2 + 0.75 * (completedIds.size / resumeTotal);
    if (pending) {
      const node = pending.node_name ?? "";
      const step = NODE_LABELS[node] ?? node;
      const who = names[pending.candidate_id ?? ""] ?? "";
      headline = who
        ? S.progressLlmWait(`${step}（${who}）`)
        : S.progressLlmWait(step);
      stepLabel = step;
    } else {
      headline = S.progressWaiting(completedIds.size, resumeTotal);
      stepLabel = S.progressStepRubric;
    }
  }

  const lastEvent = events.length ? events[events.length - 1] : null;
  let idleS = 0;
  if (lastEvent?.timestamp) {
    idleS = Math.max(
      0,
      (now.getTime() - parseTs(lastEvent.timestamp).getTime()) / 1000,
    );
  }

  const activityRows: ActivityRow[] = [];
  for (const event of [...events.slice(-12)].reverse()) {
    const ts = event.timestamp ? parseTs(event.timestamp) : now;
    activityRows.push({
      time: ts.toLocaleTimeString("zh-CN", { hour12: false }),
      label: eventLabel(event),
      latency_ms: event.latency_ms ?? null,
    });
  }

  const candidateRows: CandidateRow[] = [];
  resumes.forEach((filename, index) => {
    const candidateId = index < activeIds.length ? activeIds[index] : null;
    let stage: string;
    let label: string;
    if (candidateId) {
      stage = candidateStage(events, candidateId);
      label = names[candidateId] ?? filename;
      if (completedIds.has(candidateId)) stage = "done";
    } else {
      stage = "queued";
      label = filename;
    }
    candidateRows.push({
      label,
      stage: CANDIDATE_STAGE_LABELS[stage] ?? stage,
      done: stage === "done",
    });
  });

  return {
    headline,
    step_label: stepLabel,
    progress: Math.min(progress, 0.99),
    elapsed_s: elapsedS,
    idle_s: idleS,
    resume_total: resumeTotal,
    completed_count: completedIds.size,
    event_count: events.length,
    pending_llm: pending !== null,
    activity_rows: activityRows,
    candidate_rows: candidateRows,
  };
}
