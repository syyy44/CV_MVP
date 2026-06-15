import { ClipboardCheck, RefreshCw, Zap } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { APP_TAGLINE, APP_TITLE, S } from "@/lib/strings";
import type { HealthResponse } from "@/lib/types";

interface TopBarProps {
  health: HealthResponse | undefined;
  onReset: () => void;
  showReset: boolean;
}

export function TopBar({ health, onReset, showReset }: TopBarProps) {
  const isReplay = health?.mode === "replay";
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background/85 backdrop-blur supports-[backdrop-filter]:bg-background/70">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 lg:px-6">
        <div className="flex items-center gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary ring-1 ring-inset ring-primary/15">
            <ClipboardCheck className="size-[18px]" />
          </span>
          <div className="leading-tight">
            <div className="text-sm font-semibold tracking-tight text-foreground">
              {APP_TITLE}
            </div>
            <div className="text-xs text-muted-foreground">{APP_TAGLINE}</div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {health ? (
            isReplay ? (
              <Badge variant="info">
                <RefreshCw className="size-3.5" />
                {S.runBadgeReplay}
              </Badge>
            ) : (
              <Badge variant="proceed">
                <Zap className="size-3.5" />
                {S.runBadgeLive}
              </Badge>
            )
          ) : null}
          {health ? (
            <Badge variant="outline" className="font-mono">
              v{health.version}
            </Badge>
          ) : null}
          {showReset ? (
            <Button variant="outline" size="sm" className="cursor-pointer" onClick={onReset}>
              新建运行
            </Button>
          ) : null}
        </div>
      </div>
    </header>
  );
}
