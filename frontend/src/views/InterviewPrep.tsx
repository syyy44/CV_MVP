import {
  AlertTriangle,
  Check,
  ChevronDown,
  ClipboardCopy,
  ClipboardList,
  HelpCircle,
  Loader2,
  PenLine,
} from "lucide-react";
import * as React from "react";

import { CandidateProfilePanel } from "@/components/CandidateProfilePanel";
import { CandidateScorePanel } from "@/components/CandidateScorePanel";
import { RecommendationBadge } from "@/components/RecommendationBadge";
import { SectionTitle } from "@/components/SectionTitle";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/Accordion";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { useAddNote, useInterviewScript, useNotes, usePatchDecision } from "@/hooks/queries";
import { bandOf } from "@/lib/candidate-summary";
import { formatScriptMarkdown } from "@/lib/interview-script";
import {
  ARCHETYPE_LABELS,
  DIFFICULTY_LABELS,
  RECOMMENDATION_LABELS,
  S,
} from "@/lib/strings";
import {
  isCompletedDossier,
  type CandidateRunResult,
  type CandidateProfile,
  type DecisionDossier,
  type EvidenceSpan,
  type FollowUpQuestion,
  type InterviewScriptResponse,
  type NeedsReviewDossier,
  type Recommendation,
  type ScriptQuestion,
} from "@/lib/types";
import { cn, joinZhClauses } from "@/lib/utils";

interface InterviewPrepProps {
  candidates: CandidateRunResult[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  runId: string | null;
}

function scoreOf(c: CandidateRunResult): number {
  return isCompletedDossier(c.dossier) ? c.dossier.score.overall_score : -1;
}

function dropdownLabel(c: CandidateRunResult): string {
  const name = c.candidate_name || c.candidate_id;
  if (isCompletedDossier(c.dossier)) {
    const rec = c.human_override?.recommendation ?? c.dossier.score.recommendation;
    return `${name} · ${S.recommendationShort(rec)} · ${c.dossier.score.overall_score}`;
  }
  return `${name} · ${S.needsReviewBadge}`;
}

export function InterviewPrep({
  candidates,
  selectedId,
  onSelect,
  runId,
}: InterviewPrepProps) {
  // 与看板同序（分数降序），prep 无 candidate 参数时默认看板第 1 位（§3.3）。
  const withDossier = candidates
    .filter((c) => c.dossier)
    .sort((a, b) => scoreOf(b) - scoreOf(a));
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
                {dropdownLabel(c)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {current.status === "needs_review" && current.dossier ? (
        <NeedsReviewNotice dossier={current.dossier as NeedsReviewDossier} />
      ) : isCompletedDossier(current.dossier) ? (
        <PrepContent key={current.candidate_id} candidate={current} runId={runId} />
      ) : (
        <p className="text-sm text-muted-foreground">{S.noDossiers}</p>
      )}
    </div>
  );
}

function PrepContent({
  candidate,
  runId,
}: {
  candidate: CandidateRunResult;
  runId: string | null;
}) {
  const dossier = candidate.dossier as DecisionDossier;
  const scriptQuery = useInterviewScript(candidate.candidate_id);
  const [copied, setCopied] = React.useState(false);
  const score = dossier.score;
  const band = bandOf(candidate);
  const override = candidate.human_override;
  const effective = override ? override.recommendation : score.recommendation;
  const script = scriptQuery.data;

  async function copyScript() {
    if (!script) return;
    const md = formatScriptMarkdown(script);
    try {
      await navigator.clipboard.writeText(md);
    } catch {
      // 非安全上下文 / 文档未聚焦时回退到 execCommand。
      const textarea = document.createElement("textarea");
      textarea.value = md;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      textarea.remove();
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-xl font-semibold tracking-tight text-foreground">
              {dossier.candidate_name}
            </h2>
            <RecommendationBadge value={effective} />
            {override ? (
              <Badge variant="warn">
                <PenLine className="size-3" />
                {S.overrideBadge}
              </Badge>
            ) : null}
            <Badge variant="outline">{score.overall_score} 分</Badge>
            <Badge variant="outline" title={S.confidenceHover(band)} className="cursor-help">
              {S.confidenceBandLabel(band)}
            </Badge>
          </div>
          {script ? (
            <p className="text-sm text-muted-foreground">
              {S.scriptDurationHint(
                script.suggested_duration_min,
                script.must_ask.length,
                script.follow_ups.length,
              )}
            </p>
          ) : null}
        </div>
        <div className="flex flex-col items-end gap-1">
          <Button
            type="button"
            variant="default"
            className="cursor-pointer"
            disabled={!script}
            onClick={copyScript}
          >
            {copied ? <Check className="size-4" /> : <ClipboardCopy className="size-4" />}
            {copied ? S.scriptCopied : S.copyScript}
          </Button>
          {copied ? (
            <p className="text-xs text-muted-foreground">{S.scriptCopiedToast}</p>
          ) : null}
        </div>
      </div>

      {effective === "hold" && script ? (
        <HoldActionCard dossier={dossier} script={script} />
      ) : null}

      {scriptQuery.isLoading ? (
        <div className="flex items-center gap-2 py-10 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          {S.scriptLoading}
        </div>
      ) : scriptQuery.isError || !script ? (
        <div className="rounded-lg border border-reject/40 bg-reject/10 px-4 py-3 text-sm text-reject">
          {S.scriptError}
        </div>
      ) : (
        <Tabs defaultValue={effective === "reject" ? "score" : "script"}>
          <TabsList>
            <TabsTrigger value="script">{S.prepTabScript}</TabsTrigger>
            <TabsTrigger value="score">{S.prepTabScore}</TabsTrigger>
            <TabsTrigger value="profile">{S.prepTabProfile}</TabsTrigger>
          </TabsList>

          <TabsContent value="script" className="space-y-6 pt-2">
            <ScriptSection title={S.scriptMustAsk} items={script.must_ask} defaultOpen />

            {script.follow_ups.length > 0 ? (
              <FollowUpSection dossier={dossier} followUps={script.follow_ups} />
            ) : null}

            {script.optional.length > 0 ? (
              <Accordion type="single" collapsible>
                <AccordionItem value="optional">
                  <AccordionTrigger>{S.scriptOptional(script.optional.length)}</AccordionTrigger>
                  <AccordionContent className="space-y-3">
                    {script.optional.map((item) => (
                      <QuestionCard key={item.index} item={item} />
                    ))}
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            ) : null}
          </TabsContent>

          <TabsContent value="score" className="pt-2">
            <CandidateScorePanel dossier={dossier} />
          </TabsContent>

          <TabsContent value="profile" className="pt-2">
            <CandidateProfilePanel dossier={dossier} />
          </TabsContent>
        </Tabs>
      )}

      <PostInterviewPanel
        candidate={candidate}
        runId={runId}
        modelRecommendation={score.recommendation}
      />
    </div>
  );
}

function HoldActionCard({
  dossier,
  script,
}: {
  dossier: DecisionDossier;
  script: InterviewScriptResponse;
}) {
  const holdReasons = Array.from(
    new Set([
      ...dossier.score.risk_flags,
      ...dossier.score.match_reasons.filter((reason) =>
        /未|缺口|不足|尚未|低于|风险|不匹配/.test(reason),
      ),
    ]),
  );

  return (
    <Card className="space-y-4 border-hold/25 bg-hold/[0.05] p-4">
      <div className="flex items-center gap-2 font-semibold text-hold">
        <AlertTriangle className="size-4" />
        {S.holdWhyTitle}
      </div>
      {holdReasons.length > 0 ? (
        <ul className="space-y-1.5 text-sm leading-relaxed text-foreground/90">
          {holdReasons.map((reason, index) => (
            <li key={index} className="flex gap-2">
              <span className="mt-[0.5em] size-1 shrink-0 rounded-full bg-hold/60" />
              <span>{reason}</span>
            </li>
          ))}
        </ul>
      ) : null}
      <div>
        <p className="mb-2 text-sm font-medium">
          {S.holdVerifyTitle(script.verification_checklist.length)}
        </p>
        <ol className="space-y-2 text-sm">
          {script.verification_checklist.map((item, index) => (
            <li key={index} className="rounded-md border border-border bg-muted/50 px-3 py-2">
              {index + 1}. {item.item}
            </li>
          ))}
        </ol>
      </div>
      <p className="text-sm text-muted-foreground">{script.pass_criteria}</p>
    </Card>
  );
}

interface ProfileContextBlock {
  kind: "项目" | "经历" | "证据";
  title: string;
  subtitle?: string;
  lines: string[];
  score: number;
}

function compactText(value: string): string {
  return value.replace(/\s+/g, "").toLowerCase();
}

function textSimilarity(a: string, b: string): number {
  const left = compactText(a);
  const right = compactText(b);
  if (!left || !right) return 0;
  if (left.includes(right.slice(0, Math.min(18, right.length)))) return 1;
  if (right.includes(left.slice(0, Math.min(18, left.length)))) return 1;

  const grams = (text: string) => {
    const set = new Set<string>();
    for (let index = 0; index < text.length - 1; index += 1) {
      set.add(text.slice(index, index + 2));
    }
    return set;
  };
  const aGrams = grams(left);
  const bGrams = grams(right);
  if (aGrams.size === 0 || bGrams.size === 0) return 0;
  let overlap = 0;
  for (const gram of aGrams) {
    if (bGrams.has(gram)) overlap += 1;
  }
  return overlap / Math.min(aGrams.size, bGrams.size);
}

function evidenceText(followUp: FollowUpQuestion): string {
  return followUp.evidence_refs
    .flatMap((span) => [
      span.snippet,
      ...(span.context_lines ?? []).map((line) => line.text),
    ])
    .join(" ");
}

function profileBlocks(profile: CandidateProfile): ProfileContextBlock[] {
  const workBlocks = profile.work_experiences.map((work) => ({
    kind: "经历" as const,
    title: work.company ? `${work.company} · ${work.title}` : work.title,
    subtitle: work.duration,
    lines: work.highlights.slice(0, 4),
    score: 0,
  }));
  const projectBlocks = profile.projects.map((project) => ({
    kind: "项目" as const,
    title: project.name,
    subtitle: project.role_in_project || project.source_work_experience,
    lines: [
      project.description,
      ...(project.quantified_claims ?? []),
      ...(project.tech_decisions ?? []),
    ].filter(Boolean).slice(0, 4),
    score: 0,
  }));
  return [...projectBlocks, ...workBlocks];
}

function contextForFollowUp(
  profile: CandidateProfile,
  followUp: FollowUpQuestion,
): ProfileContextBlock {
  const evidenceQueries = followUp.evidence_refs.flatMap((span) => [
    span.snippet,
    ...(span.context_lines ?? []).map((line) => line.text),
  ]);
  const fallbackQuery = [
    followUp.question,
    followUp.ambiguity,
    followUp.what_to_listen_for,
    evidenceText(followUp),
  ].join(" ");

  const ranked = profileBlocks(profile)
    .map((block) => ({
      ...block,
      score: Math.max(
        ...evidenceQueries.map((query) =>
          Math.max(
            textSimilarity([block.title, block.subtitle, ...block.lines].join(" "), query) * 2,
            ...block.lines.map((line) => textSimilarity(line, query) * 3),
          ),
        ),
        textSimilarity([block.title, block.subtitle, ...block.lines].join(" "), fallbackQuery),
      ),
    }))
    .sort((a, b) => b.score - a.score);

  if (ranked[0] && ranked[0].score >= 0.12) return ranked[0];

  const firstEvidence = followUp.evidence_refs[0];
  const contextLines =
    firstEvidence?.context_lines?.map((line) => line.text) ??
    (firstEvidence ? [firstEvidence.snippet] : []);
  return {
    kind: "证据",
    title: "简历原文上下文",
    subtitle: firstEvidence
      ? `${firstEvidence.source_type === "jd" ? "JD" : "简历"} · ${
          firstEvidence.source_type === "jd" ? "J" : "R"
        }${firstEvidence.line_no ?? "?"}`
      : undefined,
    lines: contextLines.slice(0, 4),
    score: 0,
  };
}

function EvidenceContextLines({ span }: { span?: EvidenceSpan }) {
  if (!span) return null;
  const tag = span.source_type === "jd" ? "J" : "R";
  const lines =
    span.context_lines && span.context_lines.length > 0
      ? span.context_lines
      : span.line_no
        ? [{ line_no: span.line_no, text: span.snippet, is_focus: true }]
        : [];
  if (lines.length === 0) return null;
  return (
    <div className="space-y-1.5 rounded-xl border border-border/70 bg-muted/45 p-2">
      <p className="px-1 text-[11px] font-medium text-muted-foreground">原始引用定位</p>
      {lines.map((line) => (
        <div
          key={line.line_no}
          className={cn(
            "grid grid-cols-[2.5rem_1fr] gap-2 rounded-lg px-2 py-1.5 text-xs leading-5",
            line.is_focus ? "bg-primary/[0.08] text-foreground" : "text-muted-foreground",
          )}
        >
          <span className="font-mono text-primary/75">
            {tag}
            {line.line_no}
          </span>
          <span>{line.text}</span>
        </div>
      ))}
    </div>
  );
}

function FollowUpCard({
  followUp,
  index,
  profile,
}: {
  followUp: FollowUpQuestion;
  index: number;
  profile: CandidateProfile;
}) {
  const [expanded, setExpanded] = React.useState(false);
  const block = contextForFollowUp(profile, followUp);
  const primaryEvidence = followUp.evidence_refs[0];
  return (
    <li
      className={cn(
        "overflow-hidden rounded-2xl border bg-card shadow-xs transition duration-200",
        expanded && "border-primary/35 shadow-md",
      )}
    >
      <button
        type="button"
        aria-expanded={expanded}
        onClick={() => setExpanded((open) => !open)}
        className="flex w-full cursor-pointer items-start gap-3 px-4 py-3.5 text-left transition-colors hover:bg-muted/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:ring-inset"
      >
        <span className="min-w-0 flex-1">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs text-primary">F{index + 1}</span>
            <Badge variant="outline">{block.kind}上下文</Badge>
            <span className="text-xs text-muted-foreground">点击查看人物画像局部块</span>
          </div>
          <p className="text-sm font-semibold leading-relaxed text-foreground">
            {followUp.question}
          </p>
          <div className="mt-2 grid gap-2 text-xs leading-5 text-muted-foreground sm:grid-cols-2">
            <p>
              <span className="font-medium text-foreground/70">{S.ambiguityLabel}</span>
              {followUp.ambiguity}
            </p>
            <p>
              <span className="font-medium text-foreground/70">{S.listenFor}</span>
              {followUp.what_to_listen_for}
            </p>
          </div>
        </span>
        <ChevronDown
          className={cn(
            "mt-1 size-4 shrink-0 text-muted-foreground transition-transform duration-200",
            expanded && "rotate-180",
          )}
        />
      </button>

      {expanded ? (
        <div className="border-t border-border/70 px-4 pb-4 pt-3">
          <div className="rounded-2xl border border-border/80 bg-white/95 p-3 shadow-lg shadow-slate-900/8 backdrop-blur">
            <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  人物画像局部上下文
                </p>
                <p className="mt-1 text-sm font-semibold text-foreground">
                  {block.kind}：{block.title}
                </p>
                {block.subtitle ? (
                  <p className="mt-0.5 text-xs text-muted-foreground">{block.subtitle}</p>
                ) : null}
              </div>
              {primaryEvidence ? (
                <span className="rounded-full bg-primary/10 px-2 py-1 font-mono text-[11px] text-primary">
                  {primaryEvidence.source_type === "jd" ? "J" : "R"}
                  {primaryEvidence.line_no ?? "?"}
                </span>
              ) : null}
            </div>
            <div className="grid gap-3 lg:grid-cols-[1fr_0.9fr]">
              <div className="rounded-xl border border-border/70 bg-card px-3 py-2">
                <p className="mb-1.5 text-[11px] font-medium text-muted-foreground">
                  画像块摘录
                </p>
                <ul className="space-y-1.5 text-xs leading-5 text-foreground/85">
                  {block.lines.map((line, lineIndex) => (
                    <li key={lineIndex} className="flex gap-2">
                      <span className="mt-[0.65em] size-1 shrink-0 rounded-full bg-primary/45" />
                      <span>{line}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <EvidenceContextLines span={primaryEvidence} />
            </div>
          </div>
        </div>
      ) : null}
    </li>
  );
}

function FollowUpSection({
  dossier,
  followUps,
}: {
  dossier: DecisionDossier;
  followUps: FollowUpQuestion[];
}) {
  return (
    <div>
      <SectionTitle icon={<HelpCircle className="size-4" />}>
        {S.scriptFollowUps(followUps.length)}
      </SectionTitle>
      <ol className="space-y-3">
        {followUps.map((followUp, index) => (
          <FollowUpCard
            key={`${followUp.question}-${index}`}
            followUp={followUp}
            index={index}
            profile={dossier.candidate_profile}
          />
        ))}
      </ol>
    </div>
  );
}

function ScriptSection({
  title,
  items,
  defaultOpen = false,
}: {
  title: string;
  items: ScriptQuestion[];
  defaultOpen?: boolean;
}) {
  return (
    <div>
      <SectionTitle icon={<ClipboardList className="size-4" />}>{title}</SectionTitle>
      <div className="space-y-3">
        {items.map((item) => (
          <QuestionCard key={item.index} item={item} defaultOpen={defaultOpen} />
        ))}
      </div>
    </div>
  );
}

function QuestionCard({
  item,
  defaultOpen = true,
}: {
  item: ScriptQuestion;
  defaultOpen?: boolean;
}) {
  const q = item.question;
  if (defaultOpen) {
    return (
      <Card className="space-y-2.5 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-xs text-primary">Q{item.index}</span>
          <span className="font-medium">{q.competency}</span>
          {q.archetype ? (
            <Badge variant="info">{ARCHETYPE_LABELS[q.archetype]}</Badge>
          ) : null}
          <Badge variant="outline">{DIFFICULTY_LABELS[q.difficulty]}</Badge>
          <Badge variant="outline">{S.scriptMinutes(item.suggested_minutes)}</Badge>
        </div>
        <p className="text-sm font-medium leading-relaxed">{q.question}</p>
        {q.target_claim ? (
          <p className="rounded-md border-l-2 border-primary/50 bg-primary/5 px-3 py-1.5 text-xs text-muted-foreground">
            <span className="font-medium">{S.targetClaimLabel}</span>
            {q.target_claim}
          </p>
        ) : null}
        {q.follow_up_probes && q.follow_up_probes.length > 0 ? (
          <div className="text-sm">
            <p className="mb-1 text-xs font-medium text-muted-foreground">
              {S.probeChainLabel(q.follow_up_probes.length)}
            </p>
            <ol className="space-y-1">
              {q.follow_up_probes.map((probe, i) => (
                <li key={i} className="flex gap-2 text-foreground/85">
                  <span className="shrink-0 font-mono text-xs text-primary/70">
                    ↳{i + 1}
                  </span>
                  <span>{probe}</span>
                </li>
              ))}
            </ol>
          </div>
        ) : null}
        <p className="text-sm text-muted-foreground">
          <span className="font-medium">{S.scriptKeyPoints}</span>
          {joinZhClauses(q.scoring_criteria.slice(0, 2))}
        </p>
        {q.good_answer_signals.length > 0 ? (
          <p className="text-sm text-proceed/90">
            <span className="font-medium">{S.authenticSignals}</span>
            {joinZhClauses(q.good_answer_signals)}
          </p>
        ) : null}
        {q.red_flags.length > 0 ? (
          <p className="text-sm text-hold">
            <span className="font-medium">{S.recitedSignals}</span>
            {joinZhClauses(q.red_flags)}
          </p>
        ) : null}
      </Card>
    );
  }

  return (
    <Accordion type="single" collapsible>
      <AccordionItem value={`q-${item.index}`}>
        <AccordionTrigger>{q.question}</AccordionTrigger>
        <AccordionContent>
          <QuestionCard item={item} defaultOpen />
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}

function PostInterviewPanel({
  candidate,
  runId,
  modelRecommendation,
}: {
  candidate: CandidateRunResult;
  runId: string | null;
  modelRecommendation: Recommendation;
}) {
  return (
    <div className="grid grid-cols-1 gap-4 border-t border-border pt-5 lg:grid-cols-2">
      <NotesPanel candidateId={candidate.candidate_id} />
      <DecisionOverridePanel
        candidate={candidate}
        runId={runId}
        modelRecommendation={modelRecommendation}
      />
    </div>
  );
}

const TEXTAREA_CLASS =
  "min-h-[72px] w-full resize-y rounded-md border border-input bg-card px-3 py-2 text-sm shadow-xs outline-none transition-colors placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-ring/25";

function NotesPanel({ candidateId }: { candidateId: string }) {
  const notesQuery = useNotes(candidateId);
  const addNote = useAddNote(candidateId);
  const [body, setBody] = React.useState("");
  const notes = notesQuery.data ?? [];

  function submit() {
    const trimmed = body.trim();
    if (!trimmed) return;
    addNote.mutate(
      { body: trimmed, author: S.notesAuthorDefault },
      { onSuccess: () => setBody("") },
    );
  }

  return (
    <Card className="space-y-3 p-4">
      <SectionTitle icon={<PenLine className="size-4" />}>{S.notesTitle}</SectionTitle>
      {notes.length === 0 ? (
        <p className="text-sm text-muted-foreground">{S.notesEmpty}</p>
      ) : (
        <ul className="space-y-2">
          {notes.map((note) => (
            <li
              key={note.id}
              className="rounded-md border border-border bg-muted/50 px-3 py-2 text-sm"
            >
              <p className="whitespace-pre-wrap">{note.body}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {note.author} · {new Date(note.created_at).toLocaleString()}
              </p>
            </li>
          ))}
        </ul>
      )}
      <textarea
        className={TEXTAREA_CLASS}
        placeholder={S.notesPlaceholder}
        value={body}
        onChange={(e) => setBody(e.target.value)}
      />
      <div className="flex justify-end">
        <Button
          type="button"
          size="sm"
          className="cursor-pointer"
          disabled={!body.trim() || addNote.isPending}
          onClick={submit}
        >
          {addNote.isPending ? S.notesAdding : S.notesAdd}
        </Button>
      </div>
    </Card>
  );
}

const RECOMMENDATION_OPTIONS: Recommendation[] = ["proceed", "hold", "reject"];

function DecisionOverridePanel({
  candidate,
  runId,
  modelRecommendation,
}: {
  candidate: CandidateRunResult;
  runId: string | null;
  modelRecommendation: Recommendation;
}) {
  const patch = usePatchDecision(candidate.candidate_id, runId);
  const savedOverride = candidate.human_override;
  const current = savedOverride?.recommendation ?? modelRecommendation;
  const [choice, setChoice] = React.useState<Recommendation>(current);
  const [rationale, setRationale] = React.useState("");
  const [done, setDone] = React.useState(false);

  React.useEffect(() => {
    setChoice(current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candidate.candidate_id]);

  function submit() {
    const trimmed = rationale.trim();
    if (!trimmed) return;
    patch.mutate(
      { recommendation: choice, rationale: trimmed },
      {
        onSuccess: () => {
          setRationale("");
          setDone(true);
          window.setTimeout(() => setDone(false), 2500);
        },
      },
    );
  }

  return (
    <Card className="space-y-3 p-4">
      <SectionTitle icon={<PenLine className="size-4" />}>
        {S.changeDecisionTitle}
      </SectionTitle>
      <p className="text-sm text-muted-foreground">{S.changeDecisionHint}</p>
      <p className="text-xs text-muted-foreground">
        {S.decisionModelRec(RECOMMENDATION_LABELS[modelRecommendation])}
        {savedOverride ? ` · ${S.decisionCurrent(RECOMMENDATION_LABELS[current])}` : ""}
      </p>

      {savedOverride?.rationale.trim() ? (
        <div className="rounded-md border border-border bg-muted/50 px-3 py-2">
          <p className="text-xs font-medium text-muted-foreground">
            {S.decisionSavedRationaleTitle}
          </p>
          <p className="mt-1 whitespace-pre-wrap text-sm">{savedOverride.rationale}</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {S.decisionOverrideMeta(
              savedOverride.actor,
              new Date(savedOverride.at).toLocaleString(),
            )}
          </p>
        </div>
      ) : null}

      <div className="max-w-[180px]">
        <Select value={choice} onValueChange={(v) => setChoice(v as Recommendation)}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {RECOMMENDATION_OPTIONS.map((rec) => (
              <SelectItem key={rec} value={rec}>
                {RECOMMENDATION_LABELS[rec]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <textarea
        className={TEXTAREA_CLASS}
        placeholder={S.decisionRationalePlaceholder}
        value={rationale}
        onChange={(e) => setRationale(e.target.value)}
      />
      <div className="flex items-center justify-end gap-2">
        {done ? (
          <span className="text-xs text-proceed">{S.decisionRecordedToast}</span>
        ) : null}
        <Button
          type="button"
          size="sm"
          className="cursor-pointer"
          disabled={!rationale.trim() || patch.isPending}
          onClick={submit}
        >
          {patch.isPending ? S.decisionSubmitting : S.decisionSubmit}
        </Button>
      </div>
    </Card>
  );
}

function NeedsReviewNotice({ dossier }: { dossier: NeedsReviewDossier }) {
  return (
    <div className="rounded-lg border border-hold/40 bg-hold/10 px-4 py-3 text-sm text-hold">
      {S.needsReview(dossier.reviewer_message || S.validationFailedDefault)}
    </div>
  );
}
