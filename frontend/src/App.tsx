import { ClipboardList, Loader2, Trophy } from "lucide-react";
import * as React from "react";

import { Launcher } from "@/components/Launcher";
import { RunHistory } from "@/components/RunHistory";
import { TopBar } from "@/components/TopBar";
import { Badge } from "@/components/ui/Badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { useHealth, useRun, useStartRun } from "@/hooks/queries";
import { ApiError } from "@/lib/api";
import { RUN_STATUS_LABELS, S } from "@/lib/strings";
import { buildSearch, parseNav, type MainTab, type NavState } from "@/lib/url-state";
import { InterviewPrep } from "@/views/InterviewPrep";
import { LiveProgress } from "@/views/LiveProgress";
import { Ranking } from "@/views/Ranking";

const RUN_KEY = "ra.run_id";

function initialNav(): NavState {
  const nav = parseNav(window.location.search);
  if (!nav.run) {
    const stored = sessionStorage.getItem(RUN_KEY);
    if (stored) return { ...nav, run: stored };
  }
  return nav;
}

export default function App() {
  const healthQuery = useHealth();
  const [nav, setNav] = React.useState<NavState>(initialNav);

  const navigate = React.useCallback(
    (next: NavState, mode: "push" | "replace" = "push") => {
      setNav(next);
      const url = buildSearch(next) || window.location.pathname;
      if (mode === "push") window.history.pushState(null, "", url);
      else window.history.replaceState(null, "", url);
      if (next.run) sessionStorage.setItem(RUN_KEY, next.run);
      else sessionStorage.removeItem(RUN_KEY);
    },
    [],
  );

  // Reflect the restored session run in the URL once on mount.
  React.useEffect(() => {
    const search = buildSearch(nav);
    if (window.location.search !== search) {
      window.history.replaceState(null, "", search || window.location.pathname);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  React.useEffect(() => {
    const onPop = () => setNav(parseNav(window.location.search));
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const setRun = React.useCallback(
    (id: string | null) => navigate({ run: id, tab: "board", candidate: null }, "replace"),
    [navigate],
  );

  const startRun = useStartRun((id) => setRun(id));
  const runQuery = useRun(nav.run);
  const reset = React.useCallback(() => setRun(null), [setRun]);

  const selectCandidate = React.useCallback(
    (id: string) => navigate({ run: nav.run, tab: "prep", candidate: id }),
    [navigate, nav.run],
  );

  const changeTab = React.useCallback(
    (tab: string) => {
      const next: MainTab = tab === "prep" ? "prep" : "board";
      navigate({ run: nav.run, tab: next, candidate: nav.candidate });
    },
    [navigate, nav.run, nav.candidate],
  );

  return (
    <div className="min-h-screen">
      <TopBar
        health={healthQuery.data}
        onReset={reset}
        showReset={Boolean(nav.run)}
      />

      <main className="mx-auto max-w-7xl px-4 py-6 lg:px-6">
        {healthQuery.isError ? (
          <div className="mb-5 rounded-lg border border-reject/40 bg-reject/10 px-4 py-3 text-sm text-reject">
            {S.apiUnreachable(window.location.origin)}
          </div>
        ) : null}

        {!nav.run ? (
          <div className="space-y-8">
            <Launcher
              onStart={(input) => startRun.mutate(input)}
              pending={startRun.isPending}
              error={startRun.error}
            />
            <div className="mx-auto max-w-5xl">
              <RunHistory onOpen={setRun} />
            </div>
          </div>
        ) : runQuery.isLoading ? (
          <div className="flex items-center justify-center gap-2 py-20 text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            加载运行…
          </div>
        ) : runQuery.isError ? (
          <RunError error={runQuery.error} onReset={reset} />
        ) : runQuery.data ? (
          <RunView
            runId={nav.run}
            data={runQuery.data}
            selectedCandidate={nav.candidate}
            onSelectCandidate={selectCandidate}
            activeTab={nav.tab}
            onTabChange={changeTab}
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
        <Ranking candidates={candidates} onSelect={onSelectCandidate} runId={runId} />
      </div>
    );
  }

  if (run.status === "cancelled") {
    return (
      <div className="space-y-4">
        <RunHeader runId={runId} mode={run.mode} status={run.status} />
        <div className="rounded-lg border border-muted bg-muted/40 px-4 py-3 text-sm text-muted-foreground">
          {S.runCancelled(run.error)}
        </div>
        <Ranking candidates={candidates} onSelect={onSelectCandidate} runId={runId} />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <RunHeader runId={runId} mode={run.mode} status={run.status} />
      <Tabs value={activeTab} onValueChange={onTabChange}>
        <TabsList>
          <TabsTrigger value="board">
            <Trophy className="size-4" />
            {S.tabBoard}
          </TabsTrigger>
          <TabsTrigger value="prep">
            <ClipboardList className="size-4" />
            {S.tabPrep}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="board">
          <Ranking candidates={candidates} onSelect={onSelectCandidate} runId={runId} />
        </TabsContent>
        <TabsContent value="prep">
          <InterviewPrep
            candidates={candidates}
            selectedId={selectedCandidate}
            onSelect={onSelectCandidate}
            runId={runId}
          />
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
