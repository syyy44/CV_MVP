import {
  AlertTriangle,
  BarChart3,
  BookOpen,
  ChevronDown,
  ClipboardList,
  ExternalLink,
  HelpCircle,
  ListChecks,
  MessageSquareQuote,
  ShieldCheck,
  UserRound,
} from "lucide-react";

import { EvidenceSpanView } from "@/components/EvidenceSpanView";
import { ExportButton } from "@/components/ExportButton";
import { RecommendationBadge } from "@/components/RecommendationBadge";
import { ScoreBreakdown } from "@/components/ScoreBreakdown";
import { SectionTitle } from "@/components/SectionTitle";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/Accordion";
import { Badge } from "@/components/ui/Badge";
import { Card, CardContent } from "@/components/ui/Card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/Collapsible";
import { Metric } from "@/components/ui/Metric";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { useInterviewPreview } from "@/hooks/queries";
import { ApiError } from "@/lib/api";
import { DIFFICULTY_LABELS, S, VALIDATION_STATUS_LABELS } from "@/lib/strings";
import {
  isCompletedDossier,
  type CandidateRunResult,
  type DecisionDossier,
  type NeedsReviewDossier,
  type ValidationSummary,
} from "@/lib/types";
import { cn } from "@/lib/utils";

interface DossierProps {
  runId: string;
  candidates: CandidateRunResult[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function Dossier({ runId, candidates, selectedId, onSelect }: DossierProps) {
  const withDossier = candidates.filter((c) => c.dossier);
  if (withDossier.length === 0) {
    return <p className="text-sm text-muted-foreground">{S.noDossiers}</p>;
  }

  const current =
    withDossier.find((c) => c.candidate_id === selectedId) ?? withDossier[0];

  return (
    <div className="space-y-5">
      <div className="max-w-sm">
        <Select value={current.candidate_id} onValueChange={onSelect}>
          <SelectTrigger>
            <SelectValue placeholder={S.candidateSelect} />
          </SelectTrigger>
          <SelectContent>
            {withDossier.map((c) => (
              <SelectItem key={c.candidate_id} value={c.candidate_id}>
                {(c.candidate_name || c.candidate_id) +
                  ` (${c.status})`}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {current.status === "needs_review" && current.dossier ? (
        <NeedsReviewView dossier={current.dossier as NeedsReviewDossier} />
      ) : isCompletedDossier(current.dossier) ? (
        <CompletedView
          runId={runId}
          candidateId={current.candidate_id}
          dossier={current.dossier}
        />
      ) : (
        <p className="text-sm text-muted-foreground">{S.noDossiers}</p>
      )}
    </div>
  );
}

function CompletedView({
  runId,
  candidateId,
  dossier,
}: {
  runId: string;
  candidateId: string;
  dossier: DecisionDossier;
}) {
  const score = dossier.score;
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Metric label={S.scoreLabel} value={`${score.overall_score} / 100`} />
        <Card className="flex flex-col justify-center p-4">
          <span className="text-xs font-medium text-muted-foreground">
            {S.recommendationLabel}
          </span>
          <div className="mt-2">
            <RecommendationBadge value={score.recommendation} />
          </div>
        </Card>
        <Metric label={S.confidenceLabel} value={score.confidence.toFixed(2)} />
      </div>
      <p className="text-xs text-muted-foreground">{S.scoreExplanation}</p>

      <Card>
        <CardContent className="pt-5">
          <SectionTitle icon={<BarChart3 className="size-4" />}>
            {S.subScoreHeader}
          </SectionTitle>
          <ScoreBreakdown subScores={score.sub_scores} />
        </CardContent>
      </Card>

      {/* Reasons + evidence ledger */}
      <div>
        <SectionTitle icon={<ListChecks className="size-4" />}>
          {S.whyThisScore}
        </SectionTitle>
        <ol className="space-y-2">
          {score.match_reasons.map((reason, index) => (
            <li
              key={index}
              className="flex gap-2 rounded-md border border-border/60 bg-card/50 px-3 py-2 text-sm"
            >
              <span className="font-mono text-xs text-primary">{index + 1}</span>
              <span>{reason}</span>
            </li>
          ))}
        </ol>

        <Collapsible className="mt-3">
          <CollapsibleTrigger className="group flex w-full cursor-pointer items-center justify-between rounded-md border border-border bg-card px-3 py-2 text-sm font-medium transition-colors hover:border-primary/40">
            <span className="flex items-center gap-2">
              <MessageSquareQuote className="size-4 text-primary" />
              {S.evidenceLedger(score.evidence_refs.length)}
            </span>
            <ChevronDown className="size-4 text-muted-foreground transition-transform group-data-[state=open]:rotate-180" />
          </CollapsibleTrigger>
          <CollapsibleContent className="overflow-hidden data-[state=closed]:animate-accordion-up data-[state=open]:animate-accordion-down">
            <div className="mt-2 space-y-2">
              {score.evidence_refs.map((span, index) => (
                <EvidenceSpanView key={index} span={span} />
              ))}
            </div>
          </CollapsibleContent>
        </Collapsible>
      </div>

      {score.risk_flags.length > 0 ? (
        <div>
          <SectionTitle icon={<AlertTriangle className="size-4 text-hold" />}>
            {S.riskFlags}
          </SectionTitle>
          <div className="space-y-2">
            {score.risk_flags.map((flag, index) => (
              <div
                key={index}
                className="rounded-md border border-hold/40 bg-hold/10 px-3 py-2 text-sm text-hold"
              >
                {flag}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <CandidateProfileView dossier={dossier} />

      {/* Interview pack */}
      <div>
        <SectionTitle icon={<ClipboardList className="size-4" />}>
          {S.interviewPack(dossier.questions.length)}
        </SectionTitle>
        <Accordion type="multiple" className="space-y-2">
          {dossier.questions.map((q, index) => (
            <AccordionItem key={index} value={`q-${index}`}>
              <AccordionTrigger>
                <span className="flex items-center gap-2 text-left">
                  <span className="font-mono text-xs text-primary">
                    Q{index + 1}
                  </span>
                  <span>{q.competency}</span>
                  <Badge variant="outline">
                    {DIFFICULTY_LABELS[q.difficulty]}
                  </Badge>
                </span>
              </AccordionTrigger>
              <AccordionContent className="space-y-2">
                <p className="font-medium">{q.question}</p>
                <LabeledList label={S.scoringCriteria} items={q.scoring_criteria} />
                <LabeledList label={S.goodSignals} items={q.good_answer_signals} />
                {q.red_flags.length > 0 ? (
                  <LabeledList
                    label={S.redFlagsLabel}
                    items={q.red_flags}
                    tone="hold"
                  />
                ) : null}
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </div>

      {/* Follow-ups */}
      <div>
        <SectionTitle icon={<HelpCircle className="size-4" />}>
          {S.followUps(dossier.follow_ups.length)}
        </SectionTitle>
        <Accordion type="multiple" className="space-y-2">
          {dossier.follow_ups.map((f, index) => (
            <AccordionItem key={index} value={`f-${index}`}>
              <AccordionTrigger>{f.question}</AccordionTrigger>
              <AccordionContent className="space-y-2">
                <p className="text-sm">
                  <span className="font-medium text-muted-foreground">
                    {S.ambiguityLabel}
                  </span>
                  {f.ambiguity}
                </p>
                <p className="text-sm">
                  <span className="font-medium text-muted-foreground">
                    {S.listenFor}
                  </span>
                  {f.what_to_listen_for}
                </p>
                {f.evidence_refs.map((span, i) => (
                  <EvidenceSpanView key={i} span={span} />
                ))}
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </div>

      <InterviewPreview candidateId={candidateId} />

      {/* Validation provenance */}
      <div>
        <SectionTitle icon={<ShieldCheck className="size-4" />}>
          {S.validationProvenance}
        </SectionTitle>
        <ValidationRows summaries={dossier.validation_summaries} />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          {dossier.trace_url ? (
            <a
              href={dossier.trace_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 text-sm text-primary transition-colors hover:underline"
            >
              <ExternalLink className="size-4" />
              {S.langfuseTrace}
            </a>
          ) : (
            <span className="text-xs text-muted-foreground">
              {S.langfuseDisabled}
            </span>
          )}
          <ExportButton runId={runId} />
        </div>
      </div>
    </div>
  );
}

function CandidateProfileView({ dossier }: { dossier: DecisionDossier }) {
  const profile = dossier.candidate_profile;
  return (
    <Collapsible>
      <CollapsibleTrigger className="group flex w-full cursor-pointer items-center justify-between rounded-md border border-border bg-card px-3 py-2 text-sm font-medium transition-colors hover:border-primary/40">
        <span className="flex items-center gap-2">
          <UserRound className="size-4 text-primary" />
          {S.profileHeader}
        </span>
        <ChevronDown className="size-4 text-muted-foreground transition-transform group-data-[state=open]:rotate-180" />
      </CollapsibleTrigger>
      <CollapsibleContent className="overflow-hidden data-[state=closed]:animate-accordion-up data-[state=open]:animate-accordion-down">
        <div className="mt-2 space-y-3 rounded-md border border-border/60 bg-card/40 p-4 text-sm">
          <p className="leading-relaxed text-foreground/90">{profile.summary}</p>
          {profile.skills.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {profile.skills.map((skill) => (
                <Badge key={skill} variant="outline">
                  {skill}
                </Badge>
              ))}
            </div>
          ) : null}
          {profile.work_experiences.length > 0 ? (
            <div>
              <div className="mb-1 text-xs font-medium text-muted-foreground">
                {S.profileExperience}
              </div>
              <ul className="space-y-1">
                {profile.work_experiences.map((exp, i) => (
                  <li key={i} className="text-foreground/90">
                    <span className="font-medium">{exp.title}</span> · {exp.company}{" "}
                    <span className="text-muted-foreground">({exp.duration})</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {profile.projects.length > 0 ? (
            <div>
              <div className="mb-1 text-xs font-medium text-muted-foreground">
                {S.profileProjects}
              </div>
              <ul className="space-y-1">
                {profile.projects.map((proj, i) => (
                  <li key={i} className="text-foreground/90">
                    <span className="font-medium">{proj.name}</span> —{" "}
                    {proj.description}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {profile.education.length > 0 ? (
            <p>
              <span className="text-xs font-medium text-muted-foreground">
                {S.profileEducation}：
              </span>
              {profile.education.join("；")}
            </p>
          ) : null}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}

function LabeledList({
  label,
  items,
  tone,
}: {
  label: string;
  items: string[];
  tone?: "hold";
}) {
  return (
    <p className={cn("text-sm", tone === "hold" && "text-hold")}>
      <span className="font-medium text-muted-foreground">{label}</span>
      {items.join("；")}
    </p>
  );
}

function ValidationRows({ summaries }: { summaries: ValidationSummary[] }) {
  if (summaries.length === 0) {
    return <p className="text-xs text-muted-foreground">—</p>;
  }
  return (
    <div className="space-y-1.5">
      {summaries.map((summary, index) => {
        const ok = summary.status === "valid";
        return (
          <div
            key={index}
            className="flex items-center gap-2 text-xs text-muted-foreground"
          >
            {ok ? (
              <ShieldCheck className="size-3.5 text-proceed" />
            ) : (
              <AlertTriangle className="size-3.5 text-hold" />
            )}
            <span className="font-mono">
              {S.validationRow(
                summary.node_name,
                summary.schema_name,
                VALIDATION_STATUS_LABELS[summary.status] ?? summary.status,
                summary.repair_attempts,
              )}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function InterviewPreview({ candidateId }: { candidateId: string }) {
  const query = useInterviewPreview(candidateId);

  if (query.error) {
    const detail =
      query.error instanceof ApiError ? query.error.display : String(query.error);
    return (
      <p className="text-xs text-muted-foreground">
        {S.previewUnavailable(detail)}
      </p>
    );
  }
  if (!query.data) return null;
  const preview = query.data;

  return (
    <div>
      <SectionTitle icon={<BookOpen className="size-4" />}>
        {S.interviewPreviewTitle}
      </SectionTitle>
      <p className="mb-2 text-xs text-muted-foreground">
        {S.interviewPreviewCaption}
      </p>
      <Card className="space-y-2 p-4 text-sm">
        <p>
          <span className="font-medium text-muted-foreground">
            {S.personaLabel}
          </span>
          {preview.interviewer_persona}
        </p>
        <p>
          <span className="font-medium text-muted-foreground">
            {S.openingLabel}
          </span>
          {preview.opening_question}
        </p>
        <p className="flex flex-wrap items-center gap-1.5">
          <span className="font-medium text-muted-foreground">
            {S.focusLabel}
          </span>
          {preview.focus_areas.map((area, i) => (
            <Badge key={i} variant="outline">
              {area}
            </Badge>
          ))}
        </p>
      </Card>
    </div>
  );
}

function NeedsReviewView({ dossier }: { dossier: NeedsReviewDossier }) {
  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-hold/40 bg-hold/10 px-4 py-3 text-sm text-hold">
        <div className="flex items-center gap-2 font-medium">
          <AlertTriangle className="size-4" />
          {S.needsReview(dossier.reviewer_message || S.validationFailedDefault)}
        </div>
      </div>

      {dossier.partial_sub_scores ? (
        <Card>
          <CardContent className="pt-5">
            <SectionTitle icon={<BarChart3 className="size-4" />}>
              {S.subScoreHeader}
            </SectionTitle>
            <ScoreBreakdown subScores={dossier.partial_sub_scores} />
          </CardContent>
        </Card>
      ) : null}

      {dossier.missing_fields.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {dossier.missing_fields.map((field) => (
            <Badge key={field} variant="reject">
              {field}
            </Badge>
          ))}
        </div>
      ) : null}

      <div>
        <SectionTitle icon={<ShieldCheck className="size-4" />}>
          {S.validationProvenance}
        </SectionTitle>
        <ValidationRows summaries={dossier.validation_summaries} />
      </div>
    </div>
  );
}
