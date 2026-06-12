import { ListTree, TestTube2 } from "lucide-react";

import { SectionTitle } from "@/components/SectionTitle";
import { Badge } from "@/components/ui/Badge";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Metric } from "@/components/ui/Metric";
import { useEvals, useEvents } from "@/hooks/queries";
import { eventLabel } from "@/lib/progress";
import { S } from "@/lib/strings";
import type { DecisionEvent, EvalResultSummary, RunSummary } from "@/lib/types";

interface ObservabilityProps {
  runId: string;
  run: RunSummary;
}

function fmtTime(ts: string): string {
  const date = new Date(ts.endsWith("Z") || /[+-]\d\d:?\d\d$/.test(ts) ? ts : `${ts}Z`);
  return date.toLocaleTimeString("zh-CN", { hour12: false });
}

const STATUS_VARIANT: Record<string, "proceed" | "reject" | "outline"> = {
  pass: "proceed",
  fail: "reject",
  skipped: "outline",
};

const VALIDATION_VARIANT: Record<string, "proceed" | "hold" | "reject"> = {
  valid: "proceed",
  repaired: "hold",
  failed: "reject",
};

export function Observability({ runId, run }: ObservabilityProps) {
  const eventsQuery = useEvents(runId, false);
  const evalsQuery = useEvals(true);

  const metrics = run.metrics ?? {
    llm_calls: 0,
    input_tokens: 0,
    output_tokens: 0,
    cost_estimate_usd: 0,
    duration_s: 0,
  };
  const events = eventsQuery.data ?? [];
  const evals = evalsQuery.data ?? [];

  const ledgerColumns: Column<DecisionEvent>[] = [
    {
      key: "ts",
      header: S.ledgerColTs,
      sortable: true,
      className: "font-mono text-xs text-muted-foreground whitespace-nowrap",
      sortValue: (e) => e.timestamp,
      render: (e) => fmtTime(e.timestamp),
    },
    {
      key: "event",
      header: S.ledgerColEvent,
      sortable: true,
      sortValue: (e) => e.event_type,
      render: (e) => eventLabel(e),
    },
    {
      key: "candidate",
      header: S.ledgerColCandidate,
      className: "font-mono text-xs",
      render: (e) =>
        (e.metadata?.["candidate_name"] as string) ||
        (e.candidate_id ? e.candidate_id.slice(0, 8) : "—"),
    },
    { key: "node", header: S.ledgerColNode, render: (e) => e.node_name },
    { key: "actor", header: S.ledgerColActor, render: (e) => e.actor },
    {
      key: "model",
      header: S.ledgerColModel,
      className: "font-mono text-xs",
      render: (e) => e.model || "—",
    },
    {
      key: "prompt",
      header: S.ledgerColPrompt,
      className: "font-mono text-xs",
      render: (e) =>
        e.prompt_name ? `${e.prompt_name}@${e.prompt_version}` : "—",
    },
    {
      key: "latency",
      header: S.ledgerColLatency,
      align: "right",
      sortable: true,
      className: "font-mono text-xs",
      sortValue: (e) => e.latency_ms ?? -1,
      render: (e) => e.latency_ms ?? "—",
    },
    {
      key: "validation",
      header: S.ledgerColValidation,
      render: (e) =>
        e.validation_status ? (
          <Badge variant={VALIDATION_VARIANT[e.validation_status] ?? "outline"}>
            {e.validation_status}
          </Badge>
        ) : (
          "—"
        ),
    },
  ];

  const evalColumns: Column<EvalResultSummary>[] = [
    { key: "name", header: S.evalColCheck, render: (e) => e.name },
    {
      key: "status",
      header: S.evalColStatus,
      render: (e) => (
        <Badge variant={STATUS_VARIANT[e.status] ?? "outline"}>{e.status}</Badge>
      ),
    },
    {
      key: "value",
      header: S.evalColValue,
      align: "right",
      className: "font-mono text-xs",
      render: (e) => (e.value ?? "—"),
    },
    {
      key: "details",
      header: S.evalColDetails,
      className: "text-xs text-muted-foreground",
      render: (e) => e.details.slice(0, 120),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <Metric label={S.obsLlmCalls} value={metrics.llm_calls} />
        <Metric label={S.obsInputTokens} value={metrics.input_tokens} />
        <Metric label={S.obsOutputTokens} value={metrics.output_tokens} />
        <Metric
          label={S.obsCost}
          value={metrics.cost_estimate_usd.toFixed(4)}
          mono
        />
        <Metric label={S.obsDuration} value={metrics.duration_s} />
      </div>
      <p className="text-xs text-muted-foreground">{S.obsReplayNote}</p>

      <div>
        <SectionTitle icon={<ListTree className="size-4" />}>
          {S.decisionLedger(events.length)}
        </SectionTitle>
        <DataTable
          columns={ledgerColumns}
          rows={events}
          rowKey={(e, index) => String(e.id ?? index)}
          maxHeight={360}
          initialSort={{ key: "ts", dir: "asc" }}
        />
      </div>

      <div>
        <SectionTitle icon={<TestTube2 className="size-4" />}>
          {S.evalResults}
        </SectionTitle>
        {evals.length > 0 ? (
          <DataTable
            columns={evalColumns}
            rows={evals}
            rowKey={(e, index) => `${e.name}-${index}`}
            maxHeight={320}
          />
        ) : (
          <p className="text-sm text-muted-foreground">{S.noEvalResults}</p>
        )}
      </div>
    </div>
  );
}
