import { Download } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { ApiError, api } from "@/lib/api";
import { useAuditExport } from "@/hooks/queries";
import { S } from "@/lib/strings";

interface ExportButtonProps {
  runId: string;
}

export function ExportButton({ runId }: ExportButtonProps) {
  const exportQuery = useAuditExport(runId, true);

  if (exportQuery.isLoading) {
    return <Button variant="outline" size="sm" disabled>…</Button>;
  }

  if (exportQuery.error) {
    const detail =
      exportQuery.error instanceof ApiError
        ? exportQuery.error.display
        : String(exportQuery.error);
    return (
      <span className="text-xs text-muted-foreground">
        {S.exportUnavailable(detail)}
      </span>
    );
  }

  return (
    <Button variant="outline" size="sm" asChild>
      <a href={api.auditExportUrl(runId)} download={`audit-export-${runId}.json`}>
        <Download className="size-4" />
        {S.downloadAudit}
      </a>
    </Button>
  );
}
