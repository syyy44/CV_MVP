import * as React from "react";

import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/utils";

interface MetricProps {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
  mono?: boolean;
}

export function Metric({ label, value, hint, icon, className, mono }: MetricProps) {
  return (
    <Card className={cn("p-4", className)}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {label}
        </span>
        {icon ? <span className="text-muted-foreground/70">{icon}</span> : null}
      </div>
      <div
        className={cn(
          "mt-2 text-2xl font-semibold tracking-tight tabular-nums text-foreground",
          mono && "font-mono text-xl",
        )}
      >
        {value}
      </div>
      {hint ? (
        <div className="mt-1 text-xs text-muted-foreground">{hint}</div>
      ) : null}
    </Card>
  );
}
