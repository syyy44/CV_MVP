import { Activity, FileText, Loader2, ScrollText, Trophy } from "lucide-react";
import * as React from "react";

import { Launcher } from "@/components/Launcher";
import { TopBar } from "@/components/TopBar";
import { Badge } from "@/components/ui/Badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { useHealth, useRun, useStartRun } from "@/hooks/queries";
import { ApiError } from "@/lib/api";
import { RUN_STATUS_LABELS, S } from "@/lib/strings";
import { Audit } from "@/views/Audit";
import { Dossier } from "@/views/Dossier";
import { LiveProgress } from "@/views/LiveProgress";
import { Observability } from "@/views/Observability";
import { Ranking } from "@/views/Ranking";

const RUN_KEY = "ra.run_id";

export default function App() {
  const healthQuery = useHealth();
  const [runId, setRunId] = React.useState<string | null>(
    () => sessionStorage.getItem(RUN_KEY) || null,
  );
  const [selectedCandidate, setSelectedCandidate] = React.useState<string | null>(
    null,
  );
  const [activeTab, setActiveTab] = React.useState("ranking");

  const setRun = React.useCallback((id: string | null) => {
    setRunId(id);
    setSelectedCandidate(null);
    setActiveTab("ranking");
    if (id) sessionStorage.setItem(RUN_KEY, id);
    else sessionStorage.removeItem(RUN_KEY);
  }, []);

  const startRun = useStartRun((id) => setRun(id));
  const runQuery = useRun(runId);

  const reset = React.useCallback(() => setRun(null), [setRun]);

  function selectCandidate(id: string) {
    setSelectedCandidate(id);
    setActiveTab("dossier");
  }

  return (
    <div className="min-h-screen">
      <TopBar
        health={healthQuery.data}
        onReset={reset}
        showReset={Boolean(runId)}
      />

      <main className="mx-auto max-w-7xl px-4 py-6 lg:px-6">
        {healthQuery.isError ? (
          <div className="mb-5 rounded-lg border border-reject/40 bg-reject/10 px-4 py-3 text-sm text-reject">
            {S.apiUnreachable(window.location.origin)}
          </div>
        ) : null}

        {!runId ? (
          <Launcher
            onStart={(input) => startRun.mutate(input)}
            pending={startRun.isPending}
            error={startRun.error}
          />
        ) : runQuery.isLoading ? (
          <div className="flex items-center justify-center gap-2 py-20 text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            加载运行…
          </div>
        ) : runQuery.isError ? (
          <RunError error={runQuery.error} onReset={reset} />
        ) : runQuery.data ? (
          <RunView
            runId={runId}
            data={runQuery.data}
            selectedCandidate={selectedCandidate}
            onSelectCandidate={selectCandidate}
            activeTab={activeTab}
            onTabChange={setActiveTab}
          />
        ) : null}
      </main>
    </div>
  );
}

function RunError({ error, onReset }: { error: unknown; onReset: () => void }) {
  const detail = error instanceof ApiError ? error.display : String(error);
  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-reject/40 bg-reject/10 px-4 py-3 text-sm text-reject">
        {detail}
      </div>
      <button
        type="button"
        onClick={onReset}
        className="cursor-pointer text-sm text-primary hover:underline"
      >
        返回首页
      </button>
    </div>
  );
}

function RunView({
  runId,
  data,
  selectedCandidate,
  onSelectCandidate,
  activeTab,
  onTabChange,
}: {
  runId: string;
  data: import("@/lib/types").RunStatusResponse;
  selectedCandidate: string | null;
  onSelectCandidate: (id: string) => void;
  activeTab: string;
  onTabChange: (tab: string) => void;
}) {
  const { run, candidates } = data;

  if (run.status === "queued" || run.status === "running") {
    return (
      <div className="space-y-4">
        <RunHeader runId={runId} mode={run.mode} status={run.status} />
        <LiveProgress runId={runId} />
      </div>
    );
  }

  if (run.status === "failed") {
    const candidateErrors = candidates
      .filter((c) => c.errors.length > 0)
      .map(
        (c) =>
          `${c.candidate_name || c.candidate_id}: ${c.errors.join("; ")}`,
      );
    const detail = run.error || candidateErrors[0] || S.unknownError;
    return (
      <div className="space-y-4">
        <RunHeader runId={runId} mode={run.mode} status={run.status} />
        <div className="rounded-lg border border-reject/40 bg-reject/10 px-4 py-3 text-sm text-reject">
          {S.runFailed(detail)}
        </div>
        <Observability runId={runId} run={run} />
        <Ranking candidates={candidates} onSelect={onSelectCandidate} />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <RunHeader runId={runId} mode={run.mode} status={run.status} />
      <Tabs value={activeTab} onValueChange={onTabChange}>
        <TabsList>
          <TabsTrigger value="ranking">
            <Trophy className="size-4" />
            {S.tabRanking}
          </TabsTrigger>
          <TabsTrigger value="dossier">
            <FileText className="size-4" />
            {S.tabDossier}
          </TabsTrigger>
          <TabsTrigger value="observability">
            <Activity className="size-4" />
            {S.tabObservability}
          </TabsTrigger>
          <TabsTrigger value="audit">
            <ScrollText className="size-4" />
            {S.tabAudit}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="ranking">
          <Ranking candidates={candidates} onSelect={onSelectCandidate} />
        </TabsContent>
        <TabsContent value="dossier">
          <Dossier
            runId={runId}
            candidates={candidates}
            selectedId={selectedCandidate}
            onSelect={onSelectCandidate}
          />
        </TabsContent>
        <TabsContent value="observability">
          <Observability runId={runId} run={run} />
        </TabsContent>
        <TabsContent value="audit">
          <Audit runId={runId} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function RunHeader({
  runId,
  mode,
  status,
}: {
  runId: string;
  mode: string;
  status: string;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
      <span>运行</span>
      <code className="rounded bg-secondary px-1.5 py-0.5 font-mono text-xs text-foreground">
        {runId}
      </code>
      <Badge variant={mode === "replay" ? "info" : "proceed"}>
        {mode === "replay" ? S.runBadgeReplay : S.runBadgeLive}
      </Badge>
      <Badge variant="outline">
        {RUN_STATUS_LABELS[status as keyof typeof RUN_STATUS_LABELS] ?? status}
      </Badge>
    </div>
  );
}
