import { Activity, FileSearch, RefreshCw, Zap } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { APP_TITLE, S } from "@/lib/strings";
import type { HealthResponse } from "@/lib/types";

interface TopBarProps {
  health: HealthResponse | undefined;
  onReset: () => void;
  showReset: boolean;
}

export function TopBar({ health, onReset, showReset }: TopBarProps) {
  const isReplay = health?.mode === "replay";
  const langfuseLabel = health?.langfuse_enabled
    ? S.langfuseEnabled
    : S.langfuseFallback;
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background/80 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 lg:px-6">
        <div className="flex items-center gap-3">
          <div className="flex size-9 items-center justify-center rounded-lg bg-primary/15 text-primary">
            <FileSearch className="size-5" />
          </div>
          <div>
            <div className="text-sm font-semibold leading-tight">{APP_TITLE}</div>
            <div className="text-xs text-muted-foreground">
              {health ? S.langfuseCaption(langfuseLabel) : ""}
            </div>
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
          ) : (
            <Badge variant="reject">
              <Activity className="size-3.5" />
              API 离线
            </Badge>
          )}
          {health ? (
            <Badge variant="outline" className="font-mono">
              v{health.version}
            </Badge>
          ) : null}
          {showReset ? (
            <Button variant="outline" size="sm" onClick={onReset}>
              新建运行
            </Button>
          ) : null}
        </div>
      </div>
    </header>
  );
}
