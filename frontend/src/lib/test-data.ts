import { api } from "@/lib/api";

async function fetchAsFile(url: string, filename: string): Promise<File> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`无法加载测试文件：${filename}`);
  }
  const blob = await response.blob();
  return new File([blob], filename, {
    type: blob.type || "application/octet-stream",
  });
}

export async function loadTestDataFiles(): Promise<{ jd: File; resumes: File[] }> {
  const manifest = await api.getTestDataManifest();
  const [jd, ...resumes] = await Promise.all([
    fetchAsFile(manifest.jd.url, manifest.jd.filename),
    ...manifest.resumes.map((item) => fetchAsFile(item.url, item.filename)),
  ]);
  return { jd, resumes };
}
