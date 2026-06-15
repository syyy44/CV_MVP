import { AlertTriangle, Ban, ChevronRight, PenLine } from "lucide-react";
import * as React from "react";

import { CompareOverlay } from "@/components/CompareOverlay";
import { RecommendationBadge } from "@/components/RecommendationBadge";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  bandOf,
  effectiveRecommendation,
  prepCtaLabel,
  riskCountOf,
  summaryOf,
  verifyCountOf,
} from "@/lib/candidate-summary";
import { RECOMMENDATION_LABELS, S } from "@/lib/strings";
import {
  isCompletedDossier,
  type CandidateRunResult,
  type Recommendation,
} from "@/lib/types";
import { cn } from "@/lib/utils";

interface RankingProps {
  candidates: CandidateRunResult[];
  onSelect: (candidateId: string) => void;
  runId: string;
}

type Chip = "all" | Recommendation;

function scoreOf(c: CandidateRunResult): number {
  return isCompletedDossier(c.dossier) ? c.dossier.score.overall_score : -1;
}

function recommendationOf(c: CandidateRunResult): Recommendation | null {
  return effectiveRecommendation(c);
}

export function Ranking({ candidates, onSelect, runId }: RankingProps) {
  const [chip, setChip] = React.useState<Chip>("all");
  const [selected, setSelected] = React.useState<string[]>([]);
  const [compareOpen, setCompareOpen] = React.useState(false);

  if (candidates.length === 0) {
    return <p className="text-sm text-muted-foreground">{S.noCandidates}</p>;
  }

  const ordered = [...candidates].sort((a, b) => scoreOf(b) - scoreOf(a));
  const counts: Record<Recommendation, number> = { proceed: 0, hold: 0, reject: 0 };
  for (const c of ordered) {
    const rec = recommendationOf(c);
    if (rec) counts[rec] += 1;
  }

  const visible =
    chip === "all"
      ? ordered
      : ordered.filter((c) => recommendationOf(c) === chip);

  function toggleSelect(id: string) {
    setSelected((prev) =>
      prev.includes(id)
        ? prev.filter((x) => x !== id)
        : prev.length >= 2
          ? prev
          : [...prev, id],
    );
  }

  const selectedCandidates = ordered.filter((c) =>
    selected.includes(c.candidate_id),
  );

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold tracking-tight text-foreground">
          {S.boardHeader(candidates.length)}
        </h2>
        <p className="mt-0.5 text-sm text-muted-foreground">{S.boardCaption}</p>
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <FilterChip active={chip === "all"} onClick={() => setChip("all")}>
          {S.chipAll}
        </FilterChip>
        {(["proceed", "hold", "reject"] as const).map((rec) => (
          <FilterChip
            key={rec}
            active={chip === rec}
            onClick={() => setChip(rec)}
            disabled={counts[rec] === 0}
          >
            {RECOMMENDATION_LABELS[rec]} {counts[rec]}
          </FilterChip>
        ))}
      </div>

      <div className="overflow-hidden rounded-xl border border-border bg-card shadow-xs">
        {visible.length === 0 ? (
          <p className="px-4 py-6 text-sm text-muted-foreground">{S.noCandidates}</p>
        ) : (
          visible.map((candidate) => (
            <CandidateRow
              key={candidate.candidate_id}
              candidate={candidate}
              rank={ordered.indexOf(candidate) + 1}
              checked={selected.includes(candidate.candidate_id)}
              checkboxDisabled={
                !selected.includes(candidate.candidate_id) && selected.length >= 2
              }
              onToggle={() => toggleSelect(candidate.candidate_id)}
              onSelect={onSelect}
            />
          ))
        )}
      </div>

      {selectedCandidates.length === 2 ? (
        <div className="sticky bottom-4 z-20 flex items-center justify-between gap-3 rounded-xl border border-border bg-card/95 px-4 py-2.5 shadow-lg backdrop-blur">
          <span className="text-sm text-muted-foreground">
            {S.compareSelected(selectedCandidates.length)} ·{" "}
            {selectedCandidates
              .map((c) => c.candidate_name || c.candidate_id)
              .join(" vs ")}
          </span>
          <Button
            type="button"
            size="sm"
            className="cursor-pointer"
            onClick={() => setCompareOpen(true)}
          >
            {S.compareOpen}
            <ChevronRight className="size-4" />
          </Button>
        </div>
      ) : null}

      {compareOpen && selectedCandidates.length === 2 ? (
        <CompareOverlay
          runId={runId}
          a={selectedCandidates[0]}
          b={selectedCandidates[1]}
          onClose={() => setCompareOpen(false)}
          onPrep={(id) => {
            setCompareOpen(false);
            onSelect(id);
          }}
        />
      ) : null}
    </div>
  );
}

function FilterChip({
  active,
  disabled,
  onClick,
  children,
}: {
  active: boolean;
  disabled?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "cursor-pointer rounded-full border px-3 py-1 text-xs font-medium transition-colors",
        active
          ? "border-primary/30 bg-primary/10 text-primary"
          : "border-border bg-card text-muted-foreground hover:bg-muted hover:text-foreground",
        disabled &&
          "cursor-not-allowed opacity-40 hover:bg-card hover:text-muted-foreground",
      )}
    >
      {children}
    </button>
  );
}

function CandidateRow({
  candidate,
  rank,
  checked,
  checkboxDisabled,
  onToggle,
  onSelect,
}: {
  candidate: CandidateRunResult;
  rank: number;
  checked: boolean;
  checkboxDisabled: boolean;
  onToggle: () => void;
  onSelect: (id: string) => void;
}) {
  const [showError, setShowError] = React.useState(false);
  const name = candidate.candidate_name || candidate.candidate_id;
  const dossier = isCompletedDossier(candidate.dossier) ? candidate.dossier : null;

  // §4.0：needs_review / failed 行。
  if (!dossier) {
    const isFailed = candidate.status === "failed";
    const reason = isFailed
      ? candidate.errors.join("; ")
      : candidate.dossier?.status === "needs_review"
        ? candidate.dossier.reviewer_message
        : "";
    return (
      <div className="border-b border-border px-4 py-3 transition-colors last:border-b-0 hover:bg-muted/40">
        <div className="flex items-center gap-3">
          <span className="w-8 shrink-0 text-sm tabular-nums text-muted-foreground">
            #{rank}
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="truncate font-medium">{name}</span>
              {isFailed ? (
                <Badge variant="reject">
                  <Ban className="size-3" />
                  {S.failedBadge}
                </Badge>
              ) : (
                <Badge variant="warn">
                  <AlertTriangle className="size-3" />
                  {S.needsReviewBadge}
                </Badge>
              )}
            </div>
            <p className="mt-0.5 truncate text-sm text-muted-foreground">
              {reason.slice(0, 80)}
            </p>
          </div>
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="shrink-0 cursor-pointer"
            onClick={() =>
              isFailed ? setShowError((v) => !v) : onSelect(candidate.candidate_id)
            }
          >
            {isFailed && showError ? S.hideReason : S.showReason}
          </Button>
        </div>
        {isFailed && showError ? (
          <p className="mt-2 rounded-md border border-border bg-muted/60 px-3 py-2 text-sm text-muted-foreground">
            {reason}
          </p>
        ) : null}
      </div>
    );
  }

  const score = dossier.score;
  const band = bandOf(candidate);
  const riskCount = riskCountOf(candidate);
  const verifyCount = verifyCountOf(candidate);
  const override = candidate.human_override;
  const effective = override ? override.recommendation : score.recommendation;

  return (
    <div className="flex items-center gap-3 border-b border-border px-4 py-3 transition-colors last:border-b-0 hover:bg-muted/40">
      <input
        type="checkbox"
        checked={checked}
        disabled={checkboxDisabled}
        onChange={onToggle}
        aria-label={`选择 ${name} 进行对比`}
        className="size-4 shrink-0 cursor-pointer accent-primary disabled:cursor-not-allowed"
      />
      <span className="w-8 shrink-0 text-sm tabular-nums text-muted-foreground">
        #{rank}
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="truncate font-medium">{name}</span>
          <span className="text-xl font-semibold tabular-nums">
            {score.overall_score}
          </span>
          <RecommendationBadge value={effective} />
          {override ? (
            <Badge variant="warn" title={S.overrideBy(override.actor, RECOMMENDATION_LABELS[effective])}>
              <PenLine className="size-3" />
              {S.overrideBadge}
            </Badge>
          ) : null}
          <span
            className={cn(
              "text-xs",
              riskCount > 0 ? "text-hold" : "text-muted-foreground",
            )}
          >
            {S.boardRiskCount(riskCount)} ·{" "}
            {S.boardVerifyCount(verifyCount)}
          </span>
          <span
            className="cursor-help text-xs text-muted-foreground underline decoration-dotted underline-offset-2"
            title={S.confidenceHover(band)}
          >
            {S.confidenceBandLabel(band)}
          </span>
        </div>
        <p className="mt-0.5 truncate text-sm text-muted-foreground">
          {summaryOf(candidate)}
        </p>
      </div>

      <Button
        type="button"
        size="sm"
        variant="outline"
        className="shrink-0 cursor-pointer"
        onClick={() => onSelect(candidate.candidate_id)}
      >
        {prepCtaLabel(effective)}
        <ChevronRight className="size-4" />
      </Button>
    </div>
  );
}
