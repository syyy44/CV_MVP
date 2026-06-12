import { AlertTriangle, Ban, ChevronRight } from "lucide-react";

import { RecommendationBadge } from "@/components/RecommendationBadge";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { S } from "@/lib/strings";
import { isCompletedDossier, type CandidateRunResult } from "@/lib/types";
import { cn } from "@/lib/utils";

interface RankingProps {
  candidates: CandidateRunResult[];
  onSelect: (candidateId: string) => void;
}

function scoreOf(c: CandidateRunResult): number {
  return isCompletedDossier(c.dossier) ? c.dossier.score.overall_score : -1;
}

export function Ranking({ candidates, onSelect }: RankingProps) {
  if (candidates.length === 0) {
    return <p className="text-sm text-muted-foreground">{S.noCandidates}</p>;
  }

  const ordered = [...candidates].sort((a, b) => scoreOf(b) - scoreOf(a));

  return (
    <div className="space-y-3">
      {ordered.map((candidate, index) => {
        const name = candidate.candidate_name || candidate.candidate_id;
        const completedDossier = isCompletedDossier(candidate.dossier)
          ? candidate.dossier
          : null;
        const score = completedDossier?.score ?? null;
        const clickable = candidate.status === "completed" && completedDossier !== null;

        return (
          <Card
            key={candidate.candidate_id}
            className={cn(
              "p-4 transition-colors",
              clickable && "cursor-pointer hover:border-primary/40 hover:bg-secondary/30",
            )}
            onClick={clickable ? () => onSelect(candidate.candidate_id) : undefined}
            role={clickable ? "button" : undefined}
            tabIndex={clickable ? 0 : undefined}
            onKeyDown={
              clickable
                ? (e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelect(candidate.candidate_id);
                    }
                  }
                : undefined
            }
          >
            <div className="flex items-center gap-4">
              <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-secondary text-sm font-semibold text-muted-foreground">
                {index + 1}
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="truncate font-medium">{name}</span>
                  {candidate.status === "needs_review" ? (
                    <Badge variant="warn">
                      <AlertTriangle className="size-3" />
                      {S.needsReviewBadge}
                    </Badge>
                  ) : null}
                  {candidate.status === "failed" ? (
                    <Badge variant="reject">
                      <Ban className="size-3" />
                      {S.failedBadge}
                    </Badge>
                  ) : null}
                </div>
                {score ? (
                  <p className="mt-1 truncate text-sm text-muted-foreground">
                    {score.match_reasons[0] ?? ""}
                  </p>
                ) : (
                  <p className="mt-1 truncate text-sm text-muted-foreground">
                    {candidate.errors.join("; ").slice(0, 200)}
                  </p>
                )}
                {score && score.risk_flags.length > 0 ? (
                  <p className="mt-1 flex items-center gap-1 truncate text-xs text-hold">
                    <AlertTriangle className="size-3 shrink-0" />
                    {score.risk_flags[0]}
                  </p>
                ) : null}
              </div>

              {score ? (
                <div className="flex shrink-0 items-center gap-4">
                  <div className="text-right">
                    <div className="text-2xl font-semibold tabular-nums">
                      {score.overall_score}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {S.confidenceFmt(score.confidence)}
                    </div>
                  </div>
                  <RecommendationBadge value={score.recommendation} />
                  {clickable ? (
                    <ChevronRight className="size-4 text-muted-foreground" />
                  ) : null}
                </div>
              ) : null}
            </div>
          </Card>
        );
      })}
    </div>
  );
}
