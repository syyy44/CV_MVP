import { Activity, CheckCircle2, Clock, Hourglass, Loader2 } from "lucide-react";

import { SectionTitle } from "@/components/SectionTitle";
import { Card, CardContent } from "@/components/ui/Card";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Metric } from "@/components/ui/Metric";
import { Progress } from "@/components/ui/Progress";
import { useEvents, useRun } from "@/hooks/queries";
import {
  buildProgressSnapshot,
  type ActivityRow,
} from "@/lib/progress";
import { S } from "@/lib/strings";

interface LiveProgressProps {
  runId: string;
}

export function LiveProgress({ runId }: LiveProgressProps) {
  const runQuery = useRun(runId);
  const eventsQuery = useEvents(runId, true);

  const run = runQuery.data?.run;
  if (!run) {
    return (
      <div className="flex items-center justify-center gap-2 py-20 text-muted-foreground">
        <Loader2 className="size-4 animate-spin" />
        加载运行状态…
      </div>
    );
  }

  const snapshot = buildProgressSnapshot({
    run,
    documents: runQuery.data?.documents ?? [],
    candidates: runQuery.data?.candidates ?? [],
    events: eventsQuery.data ?? [],
  });
  const metrics = run.metrics ?? {
    llm_calls: 0,
    input_tokens: 0,
    output_tokens: 0,
    cost_estimate_usd: 0,
    duration_s: 0,
  };

  const minutes = Math.floor(snapshot.elapsed_s / 60);
  const seconds = Math.floor(snapshot.elapsed_s % 60);

  const activityColumns: Column<ActivityRow>[] = [
    {
      key: "time",
      header: S.activityColTime,
      className: "font-mono text-xs text-muted-foreground whitespace-nowrap",
      render: (row) => row.time,
    },
    { key: "label", header: S.activityColEvent, render: (row) => row.label },
    {
      key: "latency",
      header: S.activityColLatency,
      align: "right",
      className: "font-mono text-xs",
      render: (row) => row.latency_ms ?? "—",
    },
  ];

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="space-y-4 pt-5">
          <div className="flex items-center gap-2 text-base font-semibold">
            <Loader2 className="size-4 animate-spin text-primary" />
            {snapshot.headline}
          </div>
          <Progress value={snapshot.progress} />
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{snapshot.step_label}</span>
            <span>{Math.round(snapshot.progress * 100)}%</span>
          </div>
          {snapshot.pending_llm && snapshot.idle_s >= 15 ? (
            <div className="rounded-md border border-hold/40 bg-hold/10 px-3 py-2 text-xs text-hold">
              {S.progressLlmIdle}
            </div>
          ) : null}
        </CardContent>
      </Card>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Metric
          label={S.progressMetricDone}
          value={snapshot.completed_count}
          icon={<CheckCircle2 className="size-4" />}
        />
        <Metric
          label={S.progressMetricTotal}
          value={snapshot.resume_total}
          icon={<Hourglass className="size-4" />}
        />
        <Metric
          label={S.progressMetricEvents}
          value={snapshot.event_count}
          icon={<Activity className="size-4" />}
        />
        <Metric
          label={S.progressMetricElapsed}
          value={S.progressElapsed(minutes, seconds)}
          hint={S.progressLastEvent(Math.round(snapshot.idle_s))}
          icon={<Clock className="size-4" />}
        />
      </div>

      {snapshot.candidate_rows.length > 0 ? (
        <div>
          <SectionTitle icon={<Hourglass className="size-4" />}>
            {S.progressCandidatesHeader}
          </SectionTitle>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {snapshot.candidate_rows.map((row, index) => (
              <Card key={`${row.label}-${index}`} className="p-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="flex min-w-0 items-center gap-2 text-sm font-medium">
                    {row.done ? (
                      <CheckCircle2 className="size-4 shrink-0 text-proceed" />
                    ) : (
                      <Loader2 className="size-4 shrink-0 animate-spin text-muted-foreground" />
                    )}
                    <span className="truncate">{row.label}</span>
                  </span>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {row.stage}
                  </span>
                </div>
              </Card>
            ))}
          </div>
        </div>
      ) : null}

      <div>
        <SectionTitle
          icon={<Activity className="size-4" />}
          trailing={
            <span className="text-xs text-muted-foreground">
              {S.progressAutoRefresh}
            </span>
          }
        >
          {S.progressActivityHeader}
        </SectionTitle>
        {snapshot.activity_rows.length > 0 ? (
          <DataTable
            columns={activityColumns}
            rows={snapshot.activity_rows}
            rowKey={(_, index) => String(index)}
            maxHeight={300}
          />
        ) : (
          <p className="text-sm text-muted-foreground">
            {S.runInProgressCaption}
          </p>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Metric label={S.obsLlmCalls} value={metrics.llm_calls} />
        <Metric label={S.obsInputTokens} value={metrics.input_tokens} />
        <Metric label={S.obsOutputTokens} value={metrics.output_tokens} />
        <Metric label={S.obsDuration} value={metrics.duration_s} />
      </div>
    </div>
  );
}
