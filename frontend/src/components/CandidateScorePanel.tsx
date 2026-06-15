import * as React from "react";
import {
  AlertTriangle,
  Check,
  ChevronDown,
  ListChecks,
  Search,
  ShieldQuestion,
  X,
} from "lucide-react";

import { RecommendationBadge } from "@/components/RecommendationBadge";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/Collapsible";
import { confidenceBand } from "@/lib/candidate-summary";
import { requirementEvidenceStatus } from "@/lib/requirement-evidence";
import { CLAIM_CREDIBILITY_LABELS, S, SUB_SCORE_LABELS } from "@/lib/strings";
import { cn } from "@/lib/utils";
import type {
  CandidateSubScores,
  ClaimCredibility,
  ClaimVerification,
  DecisionDossier,
  EvidenceSpan,
  RequirementResult,
  Recommendation,
  ScoreDimensionExplanation,
  ScorePenaltyExplanation,
} from "@/lib/types";

const SUB_SCORE_WEIGHTS: Record<keyof CandidateSubScores, number> = {
  required_skills: 0.35,
  preferred_skills: 0.15,
  experience_relevance: 0.2,
  project_depth: 0.15,
  ai_engineering_maturity: 0.1,
  communication_clarity: 0.05,
};

const GAP_SIGNAL = /未|缺|不足|尚未|低于|风险|不匹配|存疑|口径|无|弱|拒绝/;

type Tone = "proceed" | "hold" | "reject";

function recommendationTone(rec: Recommendation): Tone {
  return rec === "proceed" ? "proceed" : rec === "hold" ? "hold" : "reject";
}

interface BandInfo {
  label: string;
  bar: string;
  text: string;
}

function bandFromValue(value: number): BandInfo {
  if (value >= 75) return { label: S.scoreBandStrong, bar: "bg-proceed", text: "text-proceed" };
  if (value >= 55) return { label: S.scoreBandAdequate, bar: "bg-hold", text: "text-hold" };
  if (value >= 30) return { label: S.scoreBandWeak, bar: "bg-reject", text: "text-reject" };
  return { label: S.scoreBandAbsent, bar: "bg-reject", text: "text-reject" };
}

function bandFromName(band: ScoreDimensionExplanation["band"]): BandInfo {
  if (band === "strong") return { label: S.scoreBandStrong, bar: "bg-proceed", text: "text-proceed" };
  if (band === "adequate") return { label: S.scoreBandAdequate, bar: "bg-hold", text: "text-hold" };
  if (band === "weak") return { label: S.scoreBandWeak, bar: "bg-reject", text: "text-reject" };
  return { label: S.scoreBandAbsent, bar: "bg-reject", text: "text-reject" };
}

// --- Fallbacks for legacy payloads without `score_explanation` -------------

function riskyClaims(claims: ClaimVerification[]): ClaimVerification[] {
  return claims.filter(
    (c) => c.credibility === "needs_probing" || c.credibility === "suspicious",
  );
}

function buildConcerns(dossier: DecisionDossier): string[] {
  const score = dossier.score;
  const unmet = score.requirement_results
    .filter((req) => !req.met)
    .map((req) => `必备项未满足：${req.display_label}`);
  const negativeReasons = score.match_reasons.filter((r) => GAP_SIGNAL.test(r));
  const lowDims = (Object.keys(SUB_SCORE_LABELS) as (keyof CandidateSubScores)[])
    .filter((key) => score.sub_scores[key] < 55)
    .map((key) => `${SUB_SCORE_LABELS[key]}仅 ${score.sub_scores[key]} 分`);
  return Array.from(
    new Set([...unmet, ...score.risk_flags, ...negativeReasons, ...lowDims]),
  ).slice(0, 4);
}

function buildStrengths(dossier: DecisionDossier): string[] {
  const score = dossier.score;
  const positives = score.match_reasons.filter((r) => !GAP_SIGNAL.test(r));
  const highDims = (Object.keys(SUB_SCORE_LABELS) as (keyof CandidateSubScores)[])
    .filter((key) => score.sub_scores[key] >= 75)
    .map((key) => `${SUB_SCORE_LABELS[key]} ${score.sub_scores[key]} 分`);
  return Array.from(new Set([...positives, ...highDims])).slice(0, 3);
}

function buildVerifyItems(dossier: DecisionDossier): string[] {
  const claimChecks = riskyClaims(dossier.score.claim_verifications).map(
    (c) => c.verification_hint,
  );
  const unmetChecks = dossier.score.requirement_results
    .filter((req) => !req.met)
    .map((req) => `围绕「${req.display_label}」要求候选人补充可验证项目或现场案例。`);
  return Array.from(new Set([...claimChecks, ...unmetChecks])).slice(0, 3);
}

function requirementToneClasses(tone: "proceed" | "hold" | "reject"): {
  border: string;
  icon: string;
  badge: string;
} {
  if (tone === "proceed") {
    return {
      border: "border-emerald-200/70",
      icon: "border-emerald-200 bg-emerald-50 text-proceed",
      badge: "bg-emerald-50 text-proceed",
    };
  }
  if (tone === "hold") {
    return {
      border: "border-hold/30",
      icon: "border-hold/30 bg-hold/10 text-hold",
      badge: "bg-hold/10 text-hold",
    };
  }
  return {
    border: "border-rose-200/80",
    icon: "border-rose-200 bg-rose-50 text-reject",
    badge: "bg-rose-50 text-reject",
  };
}

function evidenceForRequirement(
  refs: EvidenceSpan[],
  requirementId: string,
  sourceType: EvidenceSpan["source_type"],
): EvidenceSpan[] {
  return refs.filter(
    (span) => span.requirement_id === requirementId && span.source_type === sourceType,
  );
}

function EvidenceQuote({
  span,
  tag,
}: {
  span: EvidenceSpan;
  tag: string;
}) {
  return (
    <div className="rounded-xl border border-border/70 bg-white/80 px-3 py-2">
      <div className="mb-1 flex items-center justify-between gap-2 text-[11px] text-muted-foreground">
        <span>{tag}</span>
        <span className="font-mono">
          {span.source_type === "jd" ? "J" : "R"}
          {span.line_no ?? "?"}
        </span>
      </div>
      <p className="line-clamp-3 text-xs leading-5 text-foreground/85">{span.snippet}</p>
    </div>
  );
}

function RequirementEvidenceItem({
  req,
  resumeRefs,
  penalties,
  expanded,
  onToggle,
}: {
  req: RequirementResult;
  resumeRefs: EvidenceSpan[];
  penalties: ScorePenaltyExplanation[];
  expanded: boolean;
  onToggle: () => void;
}) {
  const shouldShowResumeEvidence = req.met;
  const jdRefs = req.jd_evidence_refs ?? [];
  const visibleJdRefs = jdRefs.slice(0, 2);
  const visibleResumeRefs = shouldShowResumeEvidence ? resumeRefs.slice(0, 2) : [];
  const status = requirementEvidenceStatus(req, resumeRefs, penalties);
  const tone = requirementToneClasses(status.tone);

  return (
    <li
      className={cn(
        "overflow-hidden rounded-2xl border bg-card shadow-xs transition duration-200",
        expanded && "border-primary/35 shadow-md",
        tone.border,
      )}
    >
      <button
        type="button"
        aria-expanded={expanded}
        onClick={onToggle}
        className={cn(
          "flex w-full cursor-pointer items-start gap-3 px-4 py-3 text-left transition-colors",
          "hover:bg-muted/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:ring-inset",
        )}
      >
        <span
          className={cn(
            "mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full border",
            tone.icon,
          )}
        >
          {status.tone === "reject" ? (
            <X className="size-3.5" />
          ) : (
            <Check className="size-3.5" />
          )}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium leading-6 text-foreground">
              {req.display_label}
            </span>
            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-[11px] font-medium",
                tone.badge,
              )}
            >
              {status.metLabel}
            </span>
          </span>
          <span className="mt-1 block text-xs text-muted-foreground">{status.reason}</span>
          <span className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
            <span className="rounded-full bg-muted px-2 py-1">JD 引用 {jdRefs.length}</span>
            {shouldShowResumeEvidence ? (
              <span
                className={cn(
                  "rounded-full px-2 py-1",
                  status.resumeGap ? "bg-hold/10 text-hold" : "bg-muted",
                )}
              >
                简历证据 {resumeRefs.length}
              </span>
            ) : null}
            <span className="font-mono text-primary/80">{req.requirement_id}</span>
          </span>
        </span>
        <ChevronDown
          className={cn(
            "mt-1 size-4 shrink-0 text-muted-foreground transition-transform duration-200",
            expanded && "rotate-180",
          )}
        />
      </button>

      {expanded ? (
        <div className="border-t border-border/70 bg-muted/20 px-4 py-3">
          <div className="mb-2 flex items-center justify-between gap-3">
            <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              必备项证据
            </span>
            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-[11px] font-medium",
                tone.badge,
              )}
            >
              {status.metLabel}
            </span>
          </div>
          <div className="rounded-xl bg-background/80 px-3 py-2 text-xs leading-5 text-foreground/80">
            <span className="font-medium text-foreground">判断原因：</span>
            {status.reason}
          </div>
          <div className={cn("mt-3 grid gap-2", shouldShowResumeEvidence && "sm:grid-cols-2")}>
            <div className="space-y-2">
              <p className="text-[11px] font-medium text-muted-foreground">JD 要求</p>
              {visibleJdRefs.length > 0 ? (
                visibleJdRefs.map((span, index) => (
                  <EvidenceQuote
                    key={`${span.line_no}-jd-${index}`}
                    span={span}
                    tag="职位描述"
                  />
                ))
              ) : (
                <div className="space-y-2">
                  <div className="rounded-xl border border-dashed border-border bg-muted/30 px-3 py-2 text-xs leading-5 text-muted-foreground">
                    未找到绑定的 JD 原文引用。
                  </div>
                  <div className="rounded-xl bg-muted/40 px-3 py-2 text-xs leading-5 text-foreground/80">
                    <span className="font-medium text-foreground">必备项表述：</span>
                    {req.display_label}
                  </div>
                </div>
              )}
            </div>
            {shouldShowResumeEvidence ? (
              <div className="space-y-2">
                <p className="text-[11px] font-medium text-muted-foreground">简历证据</p>
                {visibleResumeRefs.length > 0 ? (
                  visibleResumeRefs.map((span, index) => (
                    <EvidenceQuote
                      key={`${span.line_no}-resume-${index}`}
                      span={span}
                      tag="候选人简历"
                    />
                  ))
                ) : (
                  <div className="rounded-xl border border-dashed border-hold/30 bg-hold/10 px-3 py-2 text-xs leading-5 text-hold">
                    模型判定满足，但匹配依据中未绑定简历行引用。
                  </div>
                )}
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </li>
  );
}

interface CandidateScorePanelProps {
  dossier: DecisionDossier;
}

export function CandidateScorePanel({ dossier }: CandidateScorePanelProps) {
  const score = dossier.score;
  const band = confidenceBand(score.confidence);
  const explanation = score.score_explanation ?? {};

  const strengths =
    explanation.fit_reasons && explanation.fit_reasons.length > 0
      ? explanation.fit_reasons
      : buildStrengths(dossier);
  const concerns =
    explanation.gap_reasons && explanation.gap_reasons.length > 0
      ? explanation.gap_reasons
      : buildConcerns(dossier);
  const verifyItems =
    explanation.verification_priorities && explanation.verification_priorities.length > 0
      ? explanation.verification_priorities
      : buildVerifyItems(dossier);
  const verdict = explanation.verdict_summary?.trim() || S.scoreExplanation;
  const claims = score.claim_verifications ?? [];
  const hasEvidenceDetail =
    score.requirement_results.length > 0 || score.evidence_refs.length > 0;

  return (
    <div className="space-y-5">
      <DecisionHero
        dossier={dossier}
        confidenceBandValue={band}
        verdict={verdict}
        confidenceRationale={explanation.confidence_rationale}
        strengths={strengths}
        concerns={concerns}
      />

      <DimensionSection
        subScores={score.sub_scores}
        dimensions={explanation.dimensions}
      />

      <BreakdownSection dossier={dossier} />

      <InterviewFocusSection items={verifyItems} claims={claims} />

      {hasEvidenceDetail ? <EvidenceSection dossier={dossier} /> : null}
    </div>
  );
}

// --- 1. 核心结论 + 优劣势速览 ---------------------------------------------

const TONE_RING: Record<Tone, string> = {
  proceed: "ring-proceed/20",
  hold: "ring-hold/20",
  reject: "ring-reject/20",
};

const TONE_ACCENT: Record<Tone, string> = {
  proceed: "bg-proceed",
  hold: "bg-hold",
  reject: "bg-reject",
};

function DecisionHero({
  dossier,
  confidenceBandValue,
  verdict,
  confidenceRationale,
  strengths,
  concerns,
}: {
  dossier: DecisionDossier;
  confidenceBandValue: "high" | "medium" | "low";
  verdict: string;
  confidenceRationale?: string;
  strengths: string[];
  concerns: string[];
}) {
  const score = dossier.score;
  const tone = recommendationTone(score.recommendation);

  return (
    <section
      className={cn(
        "relative overflow-hidden rounded-xl bg-card shadow-sm ring-1",
        TONE_RING[tone],
      )}
    >
      <span className={cn("absolute inset-y-0 left-0 w-1", TONE_ACCENT[tone])} />

      <div className="space-y-5 px-5 py-5 pl-6">
        <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
          <div className="flex items-baseline gap-1">
            <span className="text-5xl font-semibold leading-none tracking-tight text-foreground">
              {score.overall_score}
            </span>
            <span className="text-base text-muted-foreground">/100</span>
          </div>
          <div className="flex flex-col gap-1.5">
            <RecommendationBadge value={score.recommendation} />
            <span
              className="text-xs text-muted-foreground"
              title={S.confidenceHover(confidenceBandValue)}
            >
              {S.confidenceLabel}：{S.confidenceBandLabel(confidenceBandValue)}
            </span>
          </div>
        </div>

        <div className="space-y-1.5">
          <p className="max-w-3xl text-sm leading-relaxed text-foreground/90">
            {verdict}
          </p>
          {confidenceRationale ? (
            <p className="max-w-3xl text-xs leading-relaxed text-muted-foreground">
              {confidenceRationale}
            </p>
          ) : null}
        </div>

        <div className="grid gap-x-8 gap-y-4 border-t border-border/50 pt-4 sm:grid-cols-2">
          <GlanceColumn
            title={S.scoreStrengths}
            tone="proceed"
            icon={<Check className="size-3.5" />}
            items={strengths}
            empty={S.scoreNoStrengths}
          />
          <GlanceColumn
            title={S.scoreConcerns}
            tone={tone === "proceed" ? "hold" : tone}
            icon={<AlertTriangle className="size-3.5" />}
            items={concerns}
            empty={S.scoreNoConcerns}
          />
        </div>
      </div>
    </section>
  );
}

function GlanceColumn({
  title,
  tone,
  icon,
  items,
  empty,
}: {
  title: string;
  tone: Tone;
  icon: React.ReactNode;
  items: string[];
  empty: string;
}) {
  const iconColor = {
    proceed: "text-proceed",
    hold: "text-hold",
    reject: "text-reject",
  }[tone];

  return (
    <div className="space-y-2.5">
      <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </div>
      {items.length > 0 ? (
        <ul className="space-y-2">
          {items.map((item) => (
            <li key={item} className="flex gap-2 text-sm leading-relaxed text-foreground/85">
              <span className={cn("mt-0.5 shrink-0", iconColor)}>{icon}</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs leading-relaxed text-muted-foreground">{empty}</p>
      )}
    </div>
  );
}

// --- shared section shells -------------------------------------------------

function PanelSection({
  title,
  trailing,
  children,
}: {
  title: string;
  trailing?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-border bg-card px-5 py-4 shadow-xs">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        {trailing}
      </div>
      {children}
    </section>
  );
}

function DisclosureSection({
  title,
  defaultOpen = false,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  return (
    <Collapsible
      defaultOpen={defaultOpen}
      className="overflow-hidden rounded-xl border border-border bg-card shadow-xs"
    >
      <CollapsibleTrigger className="group flex w-full cursor-pointer items-center justify-between gap-3 px-5 py-3.5 text-left transition-colors hover:bg-muted/50">
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        <ChevronDown className="size-4 shrink-0 text-muted-foreground transition-transform duration-200 group-data-[state=open]:rotate-180" />
      </CollapsibleTrigger>
      <CollapsibleContent className="overflow-hidden data-[state=closed]:animate-accordion-up data-[state=open]:animate-accordion-down">
        <div className="border-t border-border px-5 py-4">{children}</div>
      </CollapsibleContent>
    </Collapsible>
  );
}

// --- 2. 关键评分维度 -------------------------------------------------------

function DimensionSection({
  subScores,
  dimensions,
}: {
  subScores: CandidateSubScores;
  dimensions?: ScoreDimensionExplanation[];
}) {
  const [showRationale, setShowRationale] = React.useState(false);
  const keys = Object.keys(SUB_SCORE_LABELS) as (keyof CandidateSubScores)[];
  const hasRationale = (dimensions ?? []).some((d) => d.rationale?.trim());

  return (
    <PanelSection
      title={S.subScoreHeader}
      trailing={
        hasRationale ? (
          <button
            type="button"
            onClick={() => setShowRationale((v) => !v)}
            className="cursor-pointer text-xs text-muted-foreground transition-colors hover:text-foreground"
          >
            {showRationale
              ? S.scoreDimensionRationaleHide
              : S.scoreDimensionRationaleShow}
          </button>
        ) : null
      }
    >
      <div className="space-y-3">
        {keys.map((key) => {
          const dimension = dimensions?.find((item) => item.key === key);
          const value = dimension?.score ?? subScores[key];
          const info = dimension ? bandFromName(dimension.band) : bandFromValue(value);
          const weighted = dimension?.weighted_points ?? value * SUB_SCORE_WEIGHTS[key];
          return (
            <div key={key}>
              <div className="flex items-center gap-3">
                <span className="w-24 shrink-0 text-sm text-foreground/90">
                  {SUB_SCORE_LABELS[key]}
                </span>
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                  <div
                    className={cn("h-full rounded-full", info.bar)}
                    style={{ width: `${value}%` }}
                  />
                </div>
                <span className={cn("w-12 shrink-0 text-right text-xs font-medium", info.text)}>
                  {info.label}
                </span>
                <span className="w-14 shrink-0 text-right text-sm tabular-nums text-foreground">
                  {value}
                  <span className="text-xs text-muted-foreground">/100</span>
                </span>
              </div>
              {showRationale && dimension?.rationale ? (
                <p className="mt-1.5 pl-[7.5rem] pr-[6.5rem] text-xs leading-relaxed text-muted-foreground">
                  <span className="mr-2 text-[11px] text-muted-foreground/70">
                    加权 {weighted.toFixed(1)} 分
                  </span>
                  {dimension.rationale}
                </p>
              ) : null}
            </div>
          );
        })}
      </div>
    </PanelSection>
  );
}

// --- 3. 分数构成（默认收起）-------------------------------------------------

function BreakdownSection({ dossier }: { dossier: DecisionDossier }) {
  const score = dossier.score;
  const breakdown = score.score_explanation?.breakdown;
  const penaltyTotal =
    breakdown?.penalties.reduce((total, p) => total + p.points, 0) ?? 0;

  return (
    <DisclosureSection title={S.scoreFormulaTitle}>
      <div className="space-y-4">
        <div className="flex items-end gap-2 text-sm">
          <FormulaTerm label={S.scoreBaseLabel} value={breakdown ? breakdown.base_score.toFixed(1) : "—"} />
          <span className="pb-1 text-muted-foreground">−</span>
          <FormulaTerm
            label={S.scorePenaltyLabel}
            value={penaltyTotal ? `${penaltyTotal}` : "0"}
            tone={penaltyTotal ? "reject" : undefined}
          />
          <span className="pb-1 text-muted-foreground">=</span>
          <FormulaTerm label={S.scoreFinalLabel} value={`${score.overall_score}`} emphasis />
        </div>

        {breakdown?.penalties && breakdown.penalties.length > 0 ? (
          <ul className="space-y-2 border-t border-border/50 pt-3">
            {breakdown.penalties.map((penalty) => (
              <li
                key={`${penalty.kind}-${penalty.requirement_id ?? penalty.explanation}`}
                className="flex gap-2.5 text-xs leading-relaxed text-foreground/80"
              >
                <span className="shrink-0 font-medium text-reject tabular-nums">
                  −{penalty.points}
                </span>
                <span>{penalty.explanation}</span>
              </li>
            ))}
          </ul>
        ) : null}

        <p className="border-t border-border/50 pt-3 text-xs leading-relaxed text-muted-foreground">
          {breakdown?.recommendation_rule || S.scoreFormulaCopy}
          <span className="mt-1 block">{S.scoreThresholdCopy}</span>
        </p>
      </div>
    </DisclosureSection>
  );
}

function FormulaTerm({
  label,
  value,
  emphasis = false,
  tone,
}: {
  label: string;
  value: string;
  emphasis?: boolean;
  tone?: "reject";
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[11px] text-muted-foreground">{label}</span>
      <span
        className={cn(
          "font-semibold tabular-nums text-foreground",
          emphasis ? "text-2xl" : "text-lg",
          tone === "reject" && "text-reject",
        )}
      >
        {value}
      </span>
    </div>
  );
}

// --- 4. 面试追问重点 + 声明核查（明细收起）---------------------------------

function InterviewFocusSection({
  items,
  claims,
}: {
  items: string[];
  claims: ClaimVerification[];
}) {
  const ordered = [...claims].sort((a, b) => credibilityRank(a) - credibilityRank(b));

  return (
    <PanelSection title={S.scoreInterviewFocus}>
      {items.length > 0 ? (
        <ol className="space-y-2.5">
          {items.map((item, index) => (
            <li key={item} className="flex gap-3 text-sm leading-relaxed text-foreground/90">
              <span className="mt-px flex size-5 shrink-0 items-center justify-center rounded-full bg-hold/15 text-xs font-medium text-hold tabular-nums">
                {index + 1}
              </span>
              <span>{item}</span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="text-xs leading-relaxed text-muted-foreground">{S.scoreNoVerify}</p>
      )}

      {ordered.length > 0 ? (
        <Collapsible className="mt-4 border-t border-border/50 pt-3">
          <CollapsibleTrigger className="group flex w-full cursor-pointer items-center gap-2 text-xs text-muted-foreground transition-colors hover:text-foreground">
            <ShieldQuestion className="size-3.5" />
            {S.scoreClaimDetailToggle(ordered.length)}
            <ChevronDown className="size-3.5 transition-transform duration-200 group-data-[state=open]:rotate-180" />
          </CollapsibleTrigger>
          <CollapsibleContent className="overflow-hidden data-[state=closed]:animate-accordion-up data-[state=open]:animate-accordion-down">
            <div className="mt-3 space-y-2.5">
              {ordered.map((cv, index) => (
                <ClaimRow key={`${cv.claim}-${index}`} claim={cv} />
              ))}
            </div>
          </CollapsibleContent>
        </Collapsible>
      ) : null}
    </PanelSection>
  );
}

const CREDIBILITY_TONE: Record<ClaimCredibility, BandInfo> = {
  well_supported: { label: "", bar: "bg-proceed", text: "text-proceed" },
  plausible: { label: "", bar: "bg-primary", text: "text-primary" },
  needs_probing: { label: "", bar: "bg-hold", text: "text-hold" },
  suspicious: { label: "", bar: "bg-reject", text: "text-reject" },
};

function credibilityRank(c: ClaimVerification): number {
  const rank: Record<ClaimCredibility, number> = {
    suspicious: 0,
    needs_probing: 1,
    plausible: 2,
    well_supported: 3,
  };
  return rank[c.credibility];
}

function ClaimRow({ claim }: { claim: ClaimVerification }) {
  const tone = CREDIBILITY_TONE[claim.credibility];
  return (
    <div className="rounded-lg border border-border bg-muted/50 px-3 py-2.5">
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-medium leading-relaxed text-foreground/90">
          {claim.claim}
        </span>
        <span className={cn("shrink-0 text-xs font-medium", tone.text)}>
          {CLAIM_CREDIBILITY_LABELS[claim.credibility]}
        </span>
      </div>
      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{claim.reason}</p>
      <p className="mt-1.5 flex gap-1.5 text-xs leading-relaxed text-foreground/80">
        <Search className="mt-0.5 size-3 shrink-0 text-hold" />
        <span>
          <span className="text-muted-foreground">{S.claimHowToVerify}</span>
          {claim.verification_hint}
        </span>
      </p>
    </div>
  );
}

// --- 5. 必备项覆盖 + 证据台账（默认收起）-----------------------------------

function EvidenceSection({ dossier }: { dossier: DecisionDossier }) {
  const score = dossier.score;
  const penalties = score.score_explanation?.breakdown?.penalties ?? [];
  const [expandedRequirementId, setExpandedRequirementId] = React.useState<
    string | null
  >(null);

  const toggleRequirement = React.useCallback((requirementId: string) => {
    setExpandedRequirementId((current) =>
      current === requirementId ? null : requirementId,
    );
  }, []);

  return (
    <DisclosureSection title={S.scoreEvidenceToggle(score.evidence_refs.length)}>
      <div className="space-y-4">
        {score.requirement_results.length > 0 ? (
          <div>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <ListChecks className="size-3.5" />
                {S.requirementCoverageTitle}
              </div>
              <div className="text-xs text-muted-foreground">
                {S.requirementCoverageHint}
              </div>
            </div>
            <ul className="grid gap-3">
              {score.requirement_results.map((req) => {
                const resumeRefs = evidenceForRequirement(
                  score.evidence_refs,
                  req.requirement_id,
                  "resume",
                );
                return (
                  <RequirementEvidenceItem
                    key={req.requirement_id}
                    req={req}
                    resumeRefs={resumeRefs}
                    penalties={penalties}
                    expanded={expandedRequirementId === req.requirement_id}
                    onToggle={() => toggleRequirement(req.requirement_id)}
                  />
                );
              })}
            </ul>
          </div>
        ) : null}
      </div>
    </DisclosureSection>
  );
}
