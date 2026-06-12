import * as React from "react";

import { cn } from "@/lib/utils";

interface SectionTitleProps {
  children: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
  trailing?: React.ReactNode;
}

export function SectionTitle({
  children,
  icon,
  className,
  trailing,
}: SectionTitleProps) {
  return (
    <div className={cn("mb-3 flex items-center justify-between gap-3", className)}>
      <h3 className="flex items-center gap-2 text-sm font-semibold text-foreground">
        {icon ? <span className="text-primary">{icon}</span> : null}
        {children}
      </h3>
      {trailing}
    </div>
  );
}
