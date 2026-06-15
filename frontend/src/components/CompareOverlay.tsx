// 1v1 deep comparison overlay: a single decision surface built on the shared
// run rubric. Facts are reused from each dossier; the relative verdict, winners,
// differentiators, scenarios and verification focus come from the backend
// /compare endpoint (LLM in one context, deterministic fallback). Opens from the
// board multi-select; transient state, not routed.

import {
  AlertTriangle,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Loader2,
  Minus,
  Scale,
  X,
} from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/Button";
import { ApiError } from "@/lib/api";
import { prepCtaLabel } from "@/lib/candidate-summary";
import { useCompare } from "@/hooks/queries";
import type {
  CandidateComparison,
  CandidateRunResult,
  CompareMargin,
  CompareSideRef,
  DimensionComparison,
  ScoreBand,
} from "@/lib/types";
import { cn } from "@/lib/utils";

interface CompareOverlayProps {
  runId: string;
  a: CandidateRunResult;
  b: CandidateRunResult;
  onClose: () => void;
  onPrep: (candidateId: string) => void;
}

const MARGIN_LABEL: Record<CompareMargin, string> = {
  decisive: "决定性",
  clear: "明显",
  slight: "略优",
  even: "持平",
};

const BAND_BAR: Record<ScoreBand, string> = {
  strong: "bg-proceed",
  adequate: "bg-hold",
  weak: "bg-reject",
  absent: "bg-reject/60",
};

const CONFIDENCE: Record<
  CandidateComparison["verdict"]["confidence"],
  { label: string; dot: string }
> = {
  clear: { label: "结论明确", dot: "bg-proceed" },
  leaning: { label: "有倾向", dot: "bg-hold" },
  too_close: { label: "接近 · 建议面试区分", dot: "bg-primary" },
};

export function CompareOverlay({ runId, a, b, onClose, onPrep }: CompareOverlayProps) {
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const query = useCompare(runId, a.candidate_id, b.candidate_id);
  const data = query.data;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-label="1v1 对比"
    >
      <div
        className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />
      <div className="relative flex max-h-[88vh] w-full max-w-3xl flex-col overflow-hidden rounded-xl border border-border bg-card shadow-xl">
        <div className="flex items-start justify-between gap-3 border-b border-border px-6 py-4">
          <div className="flex items-center gap-2.5">
            <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary ring-1 ring-inset ring-primary/15">
              <Scale className="size-4" />
            </span>
            <div className="leading-tight">
              <div className="text-sm font-semibold tracking-tight text-foreground">
                1v1 对比
              </div>
              <div className="text-xs text-muted-foreground">
                {data?.role_title
                  ? `同一标准 · ${data.role_title}`
                  : "基于同一岗位标准的深度对比"}
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭"
            className="cursor-pointer rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <X className="size-4" />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          {query.isLoading ? (
            <LoadingState />
          ) : query.isError ? (
            <ErrorState error={query.error} onRetry={() => query.refetch()} />
          ) : data ? (
            <ComparisonBody comparison={data} onPrep={onPrep} />
          ) : null}
        </div>
      </div>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="space-y-6">
      <div className="flex flex-col items-center justify-center gap-3 py-8 text-center">
        <Loader2 className="size-6 animate-spin text-primary" />
        <div>
          <p className="text-sm font-medium text-foreground">
            正在按统一标准做深度对比…
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            首次对比需约 30–60 秒，结果会被缓存，再次打开即时显示。
          </p>
        </div>
      </div>
      <div className="space-y-2">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-9 animate-pulse rounded-lg bg-muted/70" />
        ))}
      </div>
    </div>
  );
}

function ErrorState({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const detail = error instanceof ApiError ? error.display : "对比生成失败，请重试。";
  return (
    <div className="flex flex-col items-center gap-3 py-10 text-center">
      <AlertTriangle className="size-6 text-hold" />
      <p className="max-w-sm text-sm text-muted-foreground">{detail}</p>
      <Button variant="outline" size="sm" onClick={onRetry}>
        重新对比
      </Button>
    </div>
  );
}

function ComparisonBody({
  comparison,
  onPrep,
}: {
  comparison: CandidateComparison;
  onPrep: (candidateId: string) => void;
}) {
  const c = comparison;
  const nameOf = (side: CompareSideRef) => (side === "a" ? c.a.candidate_name : c.b.candidate_name);

  return (
    <div className="space-y-6">
      <VerdictBanner comparison={c} />

      {c.differentiators.length > 0 ? (
        <Section title="关键差异">
          <ul className="space-y-2">
            {c.differentiators.map((d, i) => (
              <li key={i} className="flex items-start gap-2.5">
                <SideTag side={d.favors} name={nameOf(d.favors)} />
                <span className="text-sm leading-relaxed text-foreground/85">{d.text}</span>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      <Section
        title="维度对比"
        trailing={
          <span className="text-[11px] text-muted-foreground">分数为独立标定，仅作参考</span>
        }
      >
        <div className="overflow-hidden rounded-xl border border-border">
          <div className="flex items-center gap-3 border-b border-border bg-muted/50 px-3 py-2 text-[11px] font-medium text-muted-foreground">
            <span className="w-24 shrink-0">维度 · 权重</span>
            <span className="flex-1 text-right">{c.a.candidate_name}</span>
            <span className="w-16 shrink-0" />
            <span className="flex-1">{c.b.candidate_name}</span>
            <span className="w-4 shrink-0" />
          </div>
          {c.dimensions.map((dim) => (
            <DimensionRow key={dim.key} dim={dim} />
          ))}
        </div>
      </Section>

      {c.must_haves.length > 0 ? (
        <Section title="必备项对照">
          <MustHaveTable comparison={c} />
        </Section>
      ) : null}

      {c.a_unique_strengths.length > 0 || c.b_unique_strengths.length > 0 ? (
        <Section title="独有优势">
          <div className="grid gap-4 sm:grid-cols-2">
            <BulletColumn
              title={c.a.candidate_name}
              items={c.a_unique_strengths}
              icon={<Check className="size-3.5 text-proceed" />}
            />
            <BulletColumn
              title={c.b.candidate_name}
              items={c.b_unique_strengths}
              icon={<Check className="size-3.5 text-proceed" />}
            />
          </div>
        </Section>
      ) : null}

      {c.a_risks.length > 0 || c.b_risks.length > 0 ? (
        <Section title="相对风险">
          <div className="grid gap-4 sm:grid-cols-2">
            <BulletColumn
              title={c.a.candidate_name}
              items={c.a_risks}
              icon={<AlertTriangle className="size-3.5 text-hold" />}
            />
            <BulletColumn
              title={c.b.candidate_name}
              items={c.b_risks}
              icon={<AlertTriangle className="size-3.5 text-hold" />}
            />
          </div>
        </Section>
      ) : null}

      {c.scenario_fit.length > 0 ? (
        <Section title="适用场景">
          <div className="space-y-2">
            {c.scenario_fit.map((s, i) => (
              <div key={i} className="flex items-start gap-2.5">
                <SideTag side={s.prefer} name={nameOf(s.prefer)} prefix="更适合" />
                <span className="text-sm leading-relaxed text-foreground/85">{s.when}</span>
              </div>
            ))}
          </div>
        </Section>
      ) : null}

      {c.verification_focus.length > 0 ? (
        <Section title="定档前需核实">
          <ol className="space-y-2.5">
            {c.verification_focus.map((v, i) => (
              <li key={i} className="flex gap-3">
                <span className="mt-px flex size-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-medium tabular-nums text-primary">
                  {i + 1}
                </span>
                <div className="space-y-0.5">
                  <p className="text-sm leading-relaxed text-foreground/90">
                    {v.item}
                    {v.could_flip ? (
                      <span className="ml-2 inline-flex items-center gap-1 rounded-full border border-hold/20 bg-hold/10 px-1.5 py-px text-[10px] font-medium text-hold">
                        可能反转
                      </span>
                    ) : null}
                  </p>
                  {v.why_it_matters ? (
                    <p className="text-xs leading-relaxed text-muted-foreground">
                      {v.why_it_matters}
                    </p>
                  ) : null}
                </div>
              </li>
            ))}
          </ol>
        </Section>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
        <span className="text-[11px] text-muted-foreground">
          {c.generated_with === "deterministic"
            ? "规则对比（未启用模型）"
            : "统一标准 · 深度对比"}
        </span>
        <div className="flex flex-wrap justify-end gap-2">
          {(["a", "b"] as const).map((side) => {
            const ref = side === "a" ? c.a : c.b;
            const isPick = c.verdict.pick === side;
            return (
              <Button
                key={ref.candidate_id}
                type="button"
                size="sm"
                variant={isPick ? "default" : "outline"}
                onClick={() => onPrep(ref.candidate_id)}
              >
                {prepCtaLabel(ref.recommendation_ref)}：{ref.candidate_name}
                <ChevronRight className="size-4" />
              </Button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// --- verdict ----------------------------------------------------------------

function VerdictBanner({ comparison }: { comparison: CandidateComparison }) {
  const v = comparison.verdict;
  const pickName =
    v.pick === "a"
      ? comparison.a.candidate_name
      : v.pick === "b"
        ? comparison.b.candidate_name
        : null;

  const tone =
    v.pick === "neither" ? "reject" : v.pick === "either" ? "even" : "pick";
  const accent =
    tone === "pick" ? "bg-primary" : tone === "reject" ? "bg-reject" : "bg-muted-foreground/40";
  const ring =
    tone === "pick"
      ? "ring-primary/15"
      : tone === "reject"
        ? "ring-reject/15"
        : "ring-border";
  const label =
    v.pick === "either" ? "势均力敌" : v.pick === "neither" ? "均不建议推进" : "推荐";
  const conf = CONFIDENCE[v.confidence];

  return (
    <section className={cn("relative overflow-hidden rounded-xl bg-card shadow-xs ring-1", ring)}>
      <span className={cn("absolute inset-y-0 left-0 w-1", accent)} />
      <div className="space-y-3 px-5 py-4 pl-6">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-baseline gap-2">
            <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {label}
            </span>
            {pickName ? (
              <span className="text-lg font-semibold tracking-tight text-foreground">
                {pickName}
              </span>
            ) : null}
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-2.5 py-0.5 text-xs text-muted-foreground">
            <span className={cn("size-1.5 rounded-full", conf.dot)} />
            {conf.label}
          </span>
        </div>

        {v.headline ? (
          <p className="text-sm font-medium leading-relaxed text-foreground">{v.headline}</p>
        ) : null}
        {v.rationale ? (
          <p className="text-sm leading-relaxed text-muted-foreground">{v.rationale}</p>
        ) : null}

        <div className="space-y-1 border-t border-border/60 pt-3 text-xs leading-relaxed">
          {v.tie_breaker ? (
            <MetaLine label="决胜点" value={v.tie_breaker} />
          ) : null}
          {v.would_change_if ? (
            <MetaLine label="可能反转" value={v.would_change_if} />
          ) : null}
          {v.overridden_by_rule ? (
            <MetaLine label="规则裁定" value={v.overridden_by_rule} tone="hold" />
          ) : null}
        </div>
      </div>
    </section>
  );
}

function MetaLine({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "hold";
}) {
  return (
    <p className="flex gap-1.5">
      <span
        className={cn(
          "shrink-0 font-medium",
          tone === "hold" ? "text-hold" : "text-foreground/70",
        )}
      >
        {label}：
      </span>
      <span className="text-muted-foreground">{value}</span>
    </p>
  );
}

// --- dimensions -------------------------------------------------------------

function DimensionRow({ dim }: { dim: DimensionComparison }) {
  const [open, setOpen] = React.useState(false);
  const hasDetail = Boolean(dim.rationale || dim.a_basis || dim.b_basis);
  const aWin = dim.winner === "a";
  const bWin = dim.winner === "b";

  return (
    <div className="border-b border-border/70 last:border-b-0">
      <button
        type="button"
        onClick={() => hasDetail && setOpen((v) => !v)}
        className={cn(
          "flex w-full items-center gap-3 px-3 py-2.5 text-left transition-colors",
          hasDetail && "cursor-pointer hover:bg-muted/40",
        )}
      >
        <div className="w-24 shrink-0">
          <div className="text-sm text-foreground/90">{dim.label}</div>
          <div className="text-[11px] tabular-nums text-muted-foreground">
            权重 {Math.round(dim.weight * 100)}%
          </div>
        </div>

        <div className="flex flex-1 items-center justify-end gap-2">
          <span
            className={cn(
              "text-sm tabular-nums",
              aWin ? "font-semibold text-primary" : "text-foreground/70",
            )}
          >
            {dim.a_score_ref}
          </span>
          <Bar value={dim.a_score_ref} band={dim.a_band} align="right" />
        </div>

        <div className="flex w-16 shrink-0 justify-center">
          <WinnerChip winner={dim.winner} margin={dim.margin} />
        </div>

        <div className="flex flex-1 items-center gap-2">
          <Bar value={dim.b_score_ref} band={dim.b_band} align="left" />
          <span
            className={cn(
              "text-sm tabular-nums",
              bWin ? "font-semibold text-primary" : "text-foreground/70",
            )}
          >
            {dim.b_score_ref}
          </span>
        </div>

        <ChevronDown
          className={cn(
            "size-4 shrink-0 text-muted-foreground transition-transform duration-200",
            !hasDetail && "opacity-0",
            open && "rotate-180",
          )}
        />
      </button>

      {open && hasDetail ? (
        <div className="space-y-3 bg-muted/30 px-3 pb-3 pt-1">
          {dim.rationale ? (
            <p className="text-xs leading-relaxed text-foreground/80">{dim.rationale}</p>
          ) : null}
          <div className="grid gap-3 sm:grid-cols-2">
            {dim.a_basis ? <BasisBlock label={dim.label} basis={dim.a_basis} /> : null}
            {dim.b_basis ? <BasisBlock label={dim.label} basis={dim.b_basis} /> : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Bar({
  value,
  band,
  align,
}: {
  value: number;
  band: ScoreBand;
  align: "left" | "right";
}) {
  return (
    <div
      className={cn(
        "flex h-1.5 w-full max-w-[120px] overflow-hidden rounded-full bg-muted",
        align === "right" ? "justify-end" : "justify-start",
      )}
    >
      <div
        className={cn("h-full rounded-full", BAND_BAR[band])}
        style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
      />
    </div>
  );
}

function WinnerChip({
  winner,
  margin,
}: {
  winner: DimensionComparison["winner"];
  margin: CompareMargin;
}) {
  if (winner === "tie") {
    return <span className="text-[11px] text-muted-foreground">持平</span>;
  }
  return (
    <span className="inline-flex items-center gap-0.5 whitespace-nowrap text-[11px] font-medium text-primary">
      {winner === "a" ? <ChevronLeft className="size-3" /> : null}
      {MARGIN_LABEL[margin]}
      {winner === "b" ? <ChevronRight className="size-3" /> : null}
    </span>
  );
}

function BasisBlock({ label, basis }: { label: string; basis: string }) {
  return (
    <div className="rounded-md border border-border bg-card px-3 py-2">
      <div className="mb-1 text-[11px] font-medium text-muted-foreground">{label}依据</div>
      <p className="text-xs leading-relaxed text-foreground/80">{basis}</p>
    </div>
  );
}

// --- must-have face-off -----------------------------------------------------

function MustHaveTable({ comparison }: { comparison: CandidateComparison }) {
  return (
    <div className="overflow-hidden rounded-xl border border-border">
      <div className="flex items-center gap-3 border-b border-border bg-muted/50 px-3 py-2 text-[11px] font-medium text-muted-foreground">
        <span className="flex-1">必备要求</span>
        <span className="w-16 shrink-0 text-center">{comparison.a.candidate_name}</span>
        <span className="w-16 shrink-0 text-center">{comparison.b.candidate_name}</span>
      </div>
      {comparison.must_haves.map((mh) => {
        const asymmetric = mh.a_met !== mh.b_met;
        return (
          <div
            key={mh.requirement_id}
            className={cn(
              "flex items-center gap-3 border-b border-border/70 px-3 py-2 text-sm last:border-b-0",
              asymmetric && "bg-hold/[0.05]",
            )}
          >
            <span className="flex-1 text-foreground/85">{mh.display_label}</span>
            <span className="flex w-16 shrink-0 justify-center">
              <MetCell met={mh.a_met} />
            </span>
            <span className="flex w-16 shrink-0 justify-center">
              <MetCell met={mh.b_met} />
            </span>
          </div>
        );
      })}
    </div>
  );
}

function MetCell({ met }: { met: boolean }) {
  return met ? (
    <Check className="size-4 text-proceed" />
  ) : (
    <Minus className="size-4 text-muted-foreground/50" />
  );
}

// --- shared bits ------------------------------------------------------------

function Section({
  title,
  trailing,
  children,
}: {
  title: string;
  trailing?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section>
      <div className="mb-2.5 flex items-center justify-between gap-3">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {title}
        </h4>
        {trailing}
      </div>
      {children}
    </section>
  );
}

function SideTag({
  side,
  name,
  prefix,
}: {
  side: CompareSideRef;
  name: string;
  prefix?: string;
}) {
  return (
    <span className="mt-px inline-flex shrink-0 items-center gap-1 rounded-full border border-border bg-muted px-2 py-0.5 text-[11px] font-medium text-foreground/75">
      {side === "a" ? (
        <ChevronLeft className="size-3 text-muted-foreground" />
      ) : null}
      {prefix ? <span className="text-muted-foreground">{prefix}</span> : null}
      {name}
      {side === "b" ? (
        <ChevronRight className="size-3 text-muted-foreground" />
      ) : null}
    </span>
  );
}

function BulletColumn({
  title,
  items,
  icon,
}: {
  title: string;
  items: string[];
  icon: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <div className="text-xs font-medium text-foreground/80">{title}</div>
      {items.length > 0 ? (
        <ul className="space-y-1.5">
          {items.map((item, i) => (
            <li key={i} className="flex gap-2 text-sm leading-relaxed text-foreground/85">
              <span className="mt-0.5 shrink-0">{icon}</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-muted-foreground">—</p>
      )}
    </div>
  );
}
