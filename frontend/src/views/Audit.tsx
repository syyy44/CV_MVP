import { AlertTriangle, Loader2 } from "lucide-react";

import { ExportButton } from "@/components/ExportButton";
import { Metric } from "@/components/ui/Metric";
import { useAuditExport } from "@/hooks/queries";
import { ApiError } from "@/lib/api";
import { S } from "@/lib/strings";

export function Audit({ runId }: { runId: string }) {
  const query = useAuditExport(runId, true);

  if (query.isLoading) {
    return (
      <div className="flex items-center gap-2 py-12 text-muted-foreground">
        <Loader2 className="size-4 animate-spin" />
        生成审计导出…
      </div>
    );
  }

  if (query.error) {
    const detail =
      query.error instanceof ApiError ? query.error.display : String(query.error);
    return (
      <div className="rounded-lg border border-hold/40 bg-hold/10 px-4 py-3 text-sm text-hold">
        {detail}
      </div>
    );
  }

  const exp = query.data!;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Metric label={S.exportStatus} value={exp.export_status} />
        <Metric label={S.exportEvents} value={exp.decision_events.length} />
        <Metric label={S.exportDossiers} value={exp.candidate_dossiers.length} />
        <Metric label={S.exportRepairs} value={exp.repair_attempts.length} />
      </div>

      {exp.warnings.length > 0
        ? exp.warnings.map((warning, index) => (
            <div
              key={index}
              className="flex items-center gap-2 rounded-md border border-hold/40 bg-hold/10 px-3 py-2 text-sm text-hold"
            >
              <AlertTriangle className="size-4 shrink-0" />
              {warning}
            </div>
          ))
        : null}

      <div className="flex items-center gap-3">
        <ExportButton runId={runId} />
        <span className="text-xs text-muted-foreground">{S.auditRedaction}</span>
      </div>

      <pre className="max-h-[420px] overflow-auto rounded-lg border border-border bg-background/60 p-4 font-mono text-xs leading-relaxed text-foreground/80">
        {JSON.stringify(
          {
            schema_version: exp.schema_version,
            run: exp.run,
            documents: exp.documents,
          },
          null,
          2,
        )}
      </pre>
    </div>
  );
}
