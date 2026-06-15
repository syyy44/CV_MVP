import { FileText, FolderOpen, Upload, X, Zap } from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { ApiError } from "@/lib/api";
import { MAIN_CAPTION, MAIN_TITLE, S } from "@/lib/strings";
import { loadTestDataFiles } from "@/lib/test-data";
import { cn } from "@/lib/utils";

interface LauncherProps {
  onStart: (input: {
    mode: "replay" | "live";
    jd?: File | null;
    jdText?: string;
    resumes?: File[];
    source?: "upload" | "test";
  }) => void;
  pending: boolean;
  error: unknown;
}

const ACCEPT = ".pdf,.docx,.txt";
const JD_TEXTAREA_CLASS =
  "min-h-[88px] w-full resize-y rounded-md border border-input bg-card px-3 py-2 text-sm shadow-xs outline-none transition-colors placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-ring/25";
const DROPZONE_CLASS =
  "flex cursor-pointer items-center justify-center gap-2 rounded-md border border-dashed border-input bg-muted/40 px-3 py-3 text-sm text-muted-foreground transition-colors hover:border-primary/50 hover:bg-primary/[0.04] hover:text-foreground";

type JdMode = "file" | "text";

export function Launcher({ onStart, pending, error }: LauncherProps) {
  const showReplayDemo = import.meta.env.VITE_SHOW_REPLAY_DEMO === "true";
  const [jdMode, setJdMode] = React.useState<JdMode>("file");
  const [jd, setJd] = React.useState<File | null>(null);
  const [jdText, setJdText] = React.useState("");
  const [resumes, setResumes] = React.useState<File[]>([]);
  const [loadingTestData, setLoadingTestData] = React.useState(false);
  const [testDataError, setTestDataError] = React.useState<string | null>(null);

  async function loadTestData() {
    setLoadingTestData(true);
    setTestDataError(null);
    try {
      const files = await loadTestDataFiles();
      setJdMode("file");
      setJd(files.jd);
      setJdText("");
      setResumes(files.resumes);
    } catch (err) {
      setTestDataError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoadingTestData(false);
    }
  }

  function addResumes(files: FileList | null) {
    if (!files) return;
    setResumes((prev) => [...prev, ...Array.from(files)].slice(0, 5));
  }

  function submitLive(e: React.FormEvent) {
    e.preventDefault();
    onStart({
      mode: "live",
      jd: jdMode === "file" ? jd : null,
      jdText: jdMode === "text" ? jdText.trim() : undefined,
      resumes,
    });
  }

  const hasJd = jdMode === "file" ? Boolean(jd) : Boolean(jdText.trim());

  const errorMessage =
    error instanceof ApiError ? error.display : error ? String(error) : null;

  return (
    <div className="mx-auto max-w-5xl animate-fade-in space-y-8 py-4">
      <div className="text-center">
        <h1 className="text-3xl font-semibold tracking-tight text-foreground sm:text-[2rem]">
          {MAIN_TITLE}
        </h1>
        <p className="mx-auto mt-3 max-w-2xl text-[15px] leading-relaxed text-muted-foreground">
          {MAIN_CAPTION}
        </p>
      </div>

      {errorMessage ? (
        <div className="rounded-lg border border-reject/40 bg-reject/10 px-4 py-3 text-sm text-reject">
          {errorMessage}
        </div>
      ) : null}

      <div className="mx-auto max-w-xl">
        <Card className="flex flex-col">
          <CardContent className="pt-5">
            <form className="flex flex-col gap-4" onSubmit={submitLive}>
              {showReplayDemo ? (
                <>
                  <div className="flex items-center gap-2 text-sm font-semibold">
                    <Zap className="size-4 text-primary" />
                    {S.sidebarDemoHeader}
                  </div>
                  <p className="text-xs leading-relaxed text-muted-foreground">
                    {S.loadDemoHelp}
                  </p>
                  <Button
                    type="button"
                    variant="secondary"
                    className="w-full"
                    disabled={pending}
                    onClick={() => onStart({ mode: "replay" })}
                  >
                    <Zap className="size-4" />
                    {S.loadDemoButton}
                  </Button>

                  <div className="h-px bg-border" />
                </>
              ) : null}

              <div className="flex items-center gap-2 text-sm font-semibold">
                <Zap className="size-4 text-primary" />
                {S.sidebarLiveHeader}
              </div>
              <p className="text-xs leading-relaxed text-muted-foreground">
                {S.loadTestDataHelp}
              </p>
              <div className="grid gap-2 sm:grid-cols-2">
                <Button
                  type="button"
                  variant="outline"
                  className="w-full"
                  disabled={pending || loadingTestData}
                  onClick={() => void loadTestData()}
                >
                  <FolderOpen className="size-4" />
                  {loadingTestData ? "加载中…" : S.loadTestDataButton}
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  className="w-full"
                  disabled={pending || loadingTestData}
                  onClick={() => onStart({ mode: "live", source: "test" })}
                >
                  <Zap className="size-4" />
                  {S.runTestLiveButton}
                </Button>
              </div>
              {testDataError ? (
                <p className="text-xs text-reject">{testDataError}</p>
              ) : null}

              <JdField
                mode={jdMode}
                onModeChange={setJdMode}
                file={jd}
                text={jdText}
                onPick={(files) => {
                  setJdMode("file");
                  setJd(files?.[0] ?? null);
                  setJdText("");
                }}
                onClearFile={() => setJd(null)}
                onTextChange={setJdText}
              />

              <div className="space-y-2">
                <label className="block text-xs font-medium text-muted-foreground">
                  {S.resumeUploader}
                </label>
                <label
                  className={cn(
                    DROPZONE_CLASS,
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
                        className="flex items-center justify-between gap-2 rounded-md border border-border bg-muted/60 px-2.5 py-1.5 text-xs"
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
                disabled={pending || !hasJd || resumes.length === 0}
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

interface JdFieldProps {
  mode: JdMode;
  onModeChange: (mode: JdMode) => void;
  file: File | null;
  text: string;
  onPick: (files: FileList | null) => void;
  onClearFile: () => void;
  onTextChange: (text: string) => void;
}

function JdField({
  mode,
  onModeChange,
  file,
  text,
  onPick,
  onClearFile,
  onTextChange,
}: JdFieldProps) {
  return (
    <div className="space-y-2">
      <label className="block text-xs font-medium text-muted-foreground">
        {S.jdUploader}
      </label>
      <Tabs
        value={mode}
        onValueChange={(value) => onModeChange(value as JdMode)}
      >
        <TabsList className="h-8 w-full">
          <TabsTrigger value="file" className="flex-1 px-2 py-1 text-xs">
            <Upload className="size-3.5" />
            {S.jdUploadTab}
          </TabsTrigger>
          <TabsTrigger value="text" className="flex-1 px-2 py-1 text-xs">
            <FileText className="size-3.5" />
            {S.jdPasteTab}
          </TabsTrigger>
        </TabsList>
        <TabsContent value="file" className="mt-2">
          {file ? (
            <div className="flex items-center justify-between gap-2 rounded-md border border-border bg-muted/60 px-2.5 py-2 text-xs">
              <span className="flex min-w-0 items-center gap-1.5">
                <FileText className="size-3.5 shrink-0 text-muted-foreground" />
                <span className="truncate">{file.name}</span>
              </span>
              <button
                type="button"
                className="cursor-pointer rounded p-0.5 text-muted-foreground transition-colors hover:text-reject"
                aria-label="移除文件"
                onClick={onClearFile}
              >
                <X className="size-3.5" />
              </button>
            </div>
          ) : (
            <label className={DROPZONE_CLASS}>
              <Upload className="size-4" />
              选择文件
              <input
                type="file"
                accept={ACCEPT}
                className="hidden"
                onChange={(e) => onPick(e.target.files)}
              />
            </label>
          )}
        </TabsContent>
        <TabsContent value="text" className="mt-2">
          <textarea
            className={JD_TEXTAREA_CLASS}
            placeholder={S.jdPastePlaceholder}
            value={text}
            onChange={(e) => onTextChange(e.target.value)}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
