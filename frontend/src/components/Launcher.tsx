import { FileText, Rocket, Upload, X, Zap } from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { ApiError } from "@/lib/api";
import { MAIN_CAPTION, MAIN_TITLE, S } from "@/lib/strings";
import { cn } from "@/lib/utils";

interface LauncherProps {
  onStart: (input: { mode: "replay" | "live"; jd?: File | null; resumes?: File[] }) => void;
  pending: boolean;
  error: unknown;
}

const ACCEPT = ".pdf,.docx,.txt";

export function Launcher({ onStart, pending, error }: LauncherProps) {
  const [jd, setJd] = React.useState<File | null>(null);
  const [resumes, setResumes] = React.useState<File[]>([]);

  function addResumes(files: FileList | null) {
    if (!files) return;
    setResumes((prev) => [...prev, ...Array.from(files)].slice(0, 5));
  }

  function submitLive(e: React.FormEvent) {
    e.preventDefault();
    onStart({ mode: "live", jd, resumes });
  }

  const errorMessage =
    error instanceof ApiError ? error.display : error ? String(error) : null;

  return (
    <div className="mx-auto max-w-5xl animate-fade-in space-y-6">
      <div className="text-center">
        <h1 className="text-3xl font-semibold tracking-tight">{MAIN_TITLE}</h1>
        <p className="mx-auto mt-3 max-w-2xl text-sm leading-relaxed text-muted-foreground">
          {MAIN_CAPTION}
        </p>
      </div>

      {errorMessage ? (
        <div className="rounded-lg border border-reject/40 bg-reject/10 px-4 py-3 text-sm text-reject">
          {errorMessage}
        </div>
      ) : null}

      <div className="grid gap-5 md:grid-cols-2">
        {/* Demo */}
        <Card className="flex flex-col">
          <CardContent className="flex flex-1 flex-col gap-4 pt-5">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <Rocket className="size-4 text-primary" />
              {S.sidebarDemoHeader}
            </div>
            <p className="flex-1 text-sm text-muted-foreground">{S.loadDemoHelp}</p>
            <Button
              size="lg"
              className="w-full"
              disabled={pending}
              onClick={() => onStart({ mode: "replay" })}
            >
              <Rocket className="size-4" />
              {S.loadDemoButton}
            </Button>
          </CardContent>
        </Card>

        {/* Live */}
        <Card className="flex flex-col">
          <CardContent className="pt-5">
            <form className="flex flex-col gap-4" onSubmit={submitLive}>
              <div className="flex items-center gap-2 text-sm font-semibold">
                <Zap className="size-4 text-primary" />
                {S.sidebarLiveHeader}
              </div>

              <FileField
                label={S.jdUploader}
                accept={ACCEPT}
                file={jd}
                onPick={(files) => setJd(files?.[0] ?? null)}
                onClear={() => setJd(null)}
              />

              <div className="space-y-2">
                <label className="block text-xs font-medium text-muted-foreground">
                  {S.resumeUploader}
                </label>
                <label
                  className={cn(
                    "flex cursor-pointer items-center justify-center gap-2 rounded-md border border-dashed border-border bg-background/40 px-3 py-3 text-sm text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground",
                    resumes.length >= 5 && "pointer-events-none opacity-50",
                  )}
                >
                  <Upload className="size-4" />
                  选择简历（最多 5 份）
                  <input
                    type="file"
                    accept={ACCEPT}
                    multiple
                    className="hidden"
                    onChange={(e) => addResumes(e.target.files)}
                  />
                </label>
                {resumes.length > 0 ? (
                  <ul className="space-y-1">
                    {resumes.map((file, index) => (
                      <li
                        key={`${file.name}-${index}`}
                        className="flex items-center justify-between gap-2 rounded-md bg-secondary/50 px-2.5 py-1.5 text-xs"
                      >
                        <span className="flex min-w-0 items-center gap-1.5">
                          <FileText className="size-3.5 shrink-0 text-muted-foreground" />
                          <span className="truncate">{file.name}</span>
                        </span>
                        <button
                          type="button"
                          className="cursor-pointer rounded p-0.5 text-muted-foreground transition-colors hover:text-reject"
                          aria-label={`移除 ${file.name}`}
                          onClick={() =>
                            setResumes((prev) =>
                              prev.filter((_, i) => i !== index),
                            )
                          }
                        >
                          <X className="size-3.5" />
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>

              <Button
                type="submit"
                variant="secondary"
                className="w-full"
                disabled={pending || !jd || resumes.length === 0}
              >
                <Zap className="size-4" />
                {S.runLiveButton}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>

      <p className="text-center text-xs leading-relaxed text-muted-foreground">
        {S.uploadContract}
      </p>
    </div>
  );
}

interface FileFieldProps {
  label: string;
  accept: string;
  file: File | null;
  onPick: (files: FileList | null) => void;
  onClear: () => void;
}

function FileField({ label, accept, file, onPick, onClear }: FileFieldProps) {
  return (
    <div className="space-y-2">
      <label className="block text-xs font-medium text-muted-foreground">
        {label}
      </label>
      {file ? (
        <div className="flex items-center justify-between gap-2 rounded-md bg-secondary/50 px-2.5 py-2 text-xs">
          <span className="flex min-w-0 items-center gap-1.5">
            <FileText className="size-3.5 shrink-0 text-muted-foreground" />
            <span className="truncate">{file.name}</span>
          </span>
          <button
            type="button"
            className="cursor-pointer rounded p-0.5 text-muted-foreground transition-colors hover:text-reject"
            aria-label="移除文件"
            onClick={onClear}
          >
            <X className="size-3.5" />
          </button>
        </div>
      ) : (
        <label className="flex cursor-pointer items-center justify-center gap-2 rounded-md border border-dashed border-border bg-background/40 px-3 py-3 text-sm text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground">
          <Upload className="size-4" />
          选择文件
          <input
            type="file"
            accept={accept}
            className="hidden"
            onChange={(e) => onPick(e.target.files)}
          />
        </label>
      )}
    </div>
  );
}
