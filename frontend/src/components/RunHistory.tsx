import { Clock, ExternalLink, History, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { type Column, DataTable } from "@/components/ui/DataTable";
import { useRunHistory } from "@/hooks/queries";
import { RUN_STATUS_LABELS, S } from "@/lib/strings";
import type { RunListItem, RunStatus } from "@/lib/types";

interface RunHistoryProps {
  onOpen: (runId: string) => void;
}

function formatWhen(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function statusVariant(
  status: RunStatus,
): "proceed" | "hold" | "reject" | "info" | "outline" {
  if (status === "completed") return "proceed";
  if (status === "needs_review") return "hold";
  if (status === "failed") return "reject";
  if (status === "queued" || status === "running") return "info";
  return "outline";
}

export function RunHistory({ onOpen }: RunHistoryProps) {
  const historyQuery = useRunHistory();

  const columns: Column<RunListItem>[] = [
    {
      key: "created_at",
      header: "时间",
      sortable: true,
      sortValue: (row) => row.run.created_at,
      render: (row) => (
        <span className="whitespace-nowrap text-foreground">
          {formatWhen(row.run.created_at)}
        </span>
      ),
    },
    {
      key: "jd",
      header: "职位描述",
      render: (row) => (
        <span className="line-clamp-2 text-foreground">
          {row.jd_filename || S.historyJdUnknown}
        </span>
      ),
    },
    {
      key: "resumes",
      header: "简历",
      align: "right",
      sortable: true,
      sortValue: (row) => row.resume_count,
      render: (row) => S.historyResumeCount(row.resume_count),
    },
    {
      key: "status",
      header: "状态",
      render: (row) => (
        <Badge variant={statusVariant(row.run.status)}>
          {RUN_STATUS_LABELS[row.run.status] ?? row.run.status}
        </Badge>
      ),
    },
    {
      key: "top",
      header: "最高分",
      render: (row) =>
        row.top_candidate_name && row.top_score != null ? (
          <span className="text-foreground">
            {S.historyTopCandidate(row.top_candidate_name, row.top_score)}
          </span>
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
    {
      key: "action",
      header: "",
      align: "right",
      className: "w-24",
      render: (row) => (
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="cursor-pointer"
          onClick={() => onOpen(row.run.run_id)}
        >
          <ExternalLink className="size-3.5" />
          {S.historyOpen}
        </Button>
      ),
    },
  ];

  return (
    <Card>
      <CardContent className="space-y-4 pt-5">
        <div className="flex items-start gap-2">
          <History className="mt-0.5 size-4 shrink-0 text-primary" />
          <div>
            <h2 className="text-sm font-semibold text-foreground">{S.historyHeader}</h2>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              {S.historyCaption}
            </p>
          </div>
        </div>

        {historyQuery.isLoading ? (
          <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            加载历史记录…
          </div>
        ) : historyQuery.isError ? (
          <div className="rounded-lg border border-reject/40 bg-reject/10 px-4 py-3 text-sm text-reject">
            无法加载历史记录
          </div>
        ) : (
          <DataTable
            columns={columns}
            rows={historyQuery.data ?? []}
            rowKey={(row) => row.run.run_id}
            initialSort={{ key: "created_at", dir: "desc" }}
            emptyLabel={S.historyEmpty}
            maxHeight={280}
          />
        )}

        {historyQuery.data && historyQuery.data.length > 0 ? (
          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Clock className="size-3.5" />
            共 {historyQuery.data.length} 条记录，按创建时间倒序
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
