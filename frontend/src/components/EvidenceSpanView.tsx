import { Badge } from "@/components/ui/Badge";
import { S } from "@/lib/strings";
import type { EvidenceSpan } from "@/lib/types";

const OFFSET_VARIANT: Record<string, "proceed" | "warn" | "outline"> = {
  verified: "proceed",
  approximate: "warn",
  unavailable: "outline",
};

export function EvidenceSpanView({ span }: { span: EvidenceSpan }) {
  const tag = span.source_type === "jd" ? "J" : "R";
  return (
    <div className="rounded-md border border-border/70 bg-background/40 p-3">
      <blockquote className="border-l-2 border-primary/60 pl-3 text-sm leading-relaxed text-foreground/90">
        {span.snippet}
      </blockquote>
      <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
        <Badge variant="outline" className="font-mono">
          [{tag}
          {span.line_no ?? "?"}]
        </Badge>
        <Badge variant={OFFSET_VARIANT[span.offset_status] ?? "outline"}>
          溯源 {span.offset_status}
        </Badge>
        {span.requirement_id ? (
          <Badge variant="info" className="font-mono">
            {S.requirementTag(span.requirement_id).trim()}
          </Badge>
        ) : null}
        {span.section ? (
          <span className="text-muted-foreground">{span.section}</span>
        ) : null}
      </div>
    </div>
  );
}
