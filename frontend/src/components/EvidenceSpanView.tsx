import { Badge } from "@/components/ui/Badge";
import { S } from "@/lib/strings";
import type { EvidenceSpan } from "@/lib/types";
import { cn } from "@/lib/utils";

const OFFSET_LABEL: Record<string, string> = {
  verified: "已验证",
  approximate: "近似定位",
  unavailable: "不可定位",
};

const OFFSET_CHIP_CLASS: Record<string, string> = {
  verified: "border-emerald-200 bg-emerald-50/80 text-emerald-700",
  approximate: "border-amber-200 bg-amber-50/80 text-amber-700",
  unavailable: "border-slate-200 bg-slate-50/90 text-slate-500",
};

export function EvidenceSpanView({ span }: { span: EvidenceSpan }) {
  const tag = span.source_type === "jd" ? "J" : "R";
  const sourceLabel = span.source_type === "jd" ? "JD" : "简历";
  const contextLines =
    span.context_lines && span.context_lines.length > 0
      ? span.context_lines
      : span.line_no
        ? [{ line_no: span.line_no, text: span.snippet, is_focus: true }]
        : [];

  return (
    <div className="rounded-md border border-border bg-muted/40 p-3">
      <blockquote className="border-l-2 border-primary/60 pl-3 text-sm leading-relaxed text-foreground/90">
        {span.snippet}
      </blockquote>
      <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
        <span className="group relative inline-flex">
          <button
            type="button"
            className={cn(
              "inline-flex cursor-help items-center overflow-hidden rounded-full border text-xs font-medium leading-5 shadow-xs transition-colors hover:bg-card focus-visible:ring-2 focus-visible:ring-ring/50",
              OFFSET_CHIP_CLASS[span.offset_status] ??
                "border-border bg-card text-muted-foreground",
            )}
            aria-label={`${sourceLabel}引用 ${tag}${span.line_no ?? "未知行"}，${
              OFFSET_LABEL[span.offset_status] ?? span.offset_status
            }`}
          >
            <span className="border-r border-current/15 bg-white/50 px-2 font-mono">
              {tag}
              {span.line_no ?? "?"}
            </span>
            <span className="px-2">{OFFSET_LABEL[span.offset_status] ?? span.offset_status}</span>
          </button>
          {contextLines.length > 0 ? (
            <span className="pointer-events-none invisible absolute bottom-full left-0 z-30 mb-2 w-80 translate-y-1 rounded-2xl border border-border/80 bg-white/95 p-2.5 text-foreground opacity-0 shadow-xl shadow-slate-900/10 backdrop-blur transition duration-150 ease-out group-focus-within:visible group-focus-within:translate-y-0 group-focus-within:opacity-100 group-hover:visible group-hover:translate-y-0 group-hover:opacity-100 sm:w-[26rem]">
              <span className="mb-2 flex items-center justify-between gap-3 px-1">
                <span className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
                  引用上下文
                </span>
                <span className="font-mono text-[11px] text-muted-foreground">
                  {sourceLabel} · {tag}
                  {span.line_no ?? "?"}
                </span>
              </span>
              <span className="block space-y-0.5">
                {contextLines.map((line) => (
                  <span
                    key={line.line_no}
                    className={cn(
                      "grid grid-cols-[2.25rem_1fr] gap-2 rounded-xl px-2.5 py-2 text-left",
                      line.is_focus
                        ? "border border-primary/10 bg-primary/[0.07] text-foreground"
                        : "text-muted-foreground",
                    )}
                  >
                    <span
                      className={cn(
                        "pt-0.5 font-mono text-[11px]",
                        line.is_focus ? "text-primary" : "text-muted-foreground/70",
                      )}
                    >
                      {tag}
                      {line.line_no}
                    </span>
                    <span className="text-xs leading-5">{line.text}</span>
                  </span>
                ))}
              </span>
            </span>
          ) : null}
        </span>
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
