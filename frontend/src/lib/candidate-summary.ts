import type {
  CandidateRunResult,
  ConfidenceBand,
  DecisionDossier,
  Recommendation,
} from "@/lib/types";
import { isCompletedDossier } from "@/lib/types";

// Thresholds per docs/V2_UI_PROPOSAL.md §5.2. Local fallback only; the backend
// is authoritative and ships `confidence_band` on each candidate.
export function confidenceBand(value: number): ConfidenceBand {
  if (value >= 0.85) return "high";
  if (value >= 0.65) return "medium";
  return "low";
}

export function humanizeReason(text: string): string {
  return text.replace(/\(([A-Z]{1,3}\d+)\)/g, "").replace(/\s+/g, " ").trim();
}

function fallbackSummary(dossier: DecisionDossier): string {
  const raw = dossier.score.match_reasons[0] ?? dossier.candidate_profile.summary;
  return humanizeReason(raw).slice(0, 60);
}

function fallbackVerificationCount(dossier: DecisionDossier): number {
  if (dossier.score.recommendation === "hold") {
    return dossier.follow_ups.length;
  }
  return dossier.candidate_profile.missing_or_ambiguous_claims.length;
}

// Server-first accessors: prefer the derived fields from the API, fall back to
// local computation so the UI degrades gracefully on older payloads.

export function summaryOf(candidate: CandidateRunResult): string {
  if (candidate.decision_summary) return candidate.decision_summary;
  return isCompletedDossier(candidate.dossier)
    ? fallbackSummary(candidate.dossier)
    : "";
}

export function bandOf(candidate: CandidateRunResult): ConfidenceBand {
  if (candidate.confidence_band) return candidate.confidence_band;
  return isCompletedDossier(candidate.dossier)
    ? confidenceBand(candidate.dossier.score.confidence)
    : "low";
}

export function riskCountOf(candidate: CandidateRunResult): number {
  if (typeof candidate.risk_count === "number" && candidate.risk_count > 0) {
    return candidate.risk_count;
  }
  return isCompletedDossier(candidate.dossier)
    ? candidate.dossier.score.risk_flags.length
    : 0;
}

export function verifyCountOf(candidate: CandidateRunResult): number {
  if (typeof candidate.verification_count === "number") {
    return candidate.verification_count;
  }
  return isCompletedDossier(candidate.dossier)
    ? fallbackVerificationCount(candidate.dossier)
    : 0;
}

export function effectiveRecommendation(
  candidate: CandidateRunResult,
): Recommendation | null {
  if (candidate.human_override) return candidate.human_override.recommendation;
  return isCompletedDossier(candidate.dossier)
    ? candidate.dossier.score.recommendation
    : null;
}

export function prepCtaLabel(recommendation: Recommendation): string {
  switch (recommendation) {
    case "proceed":
      return "准备面试";
    case "hold":
      return "先做核实";
    case "reject":
      return "查看原因";
  }
}

export function completedCandidates(
  candidates: CandidateRunResult[],
): CandidateRunResult[] {
  return candidates.filter(
    (c) => c.status === "completed" && isCompletedDossier(c.dossier),
  );
}
