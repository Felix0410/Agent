/** Workspace API 不接收磁盘路径，所有调用均绑定当前 Thread。 */
import { request } from "../api";

export type FileRecord = {
  id: string;
  thread_id: string;
  display_name: string;
  kind: "UPLOAD" | "ARTIFACT";
  mime: string;
  size_bytes: number;
  sha256: string;
  created_at: string;
};

export function listFiles(threadId: string): Promise<FileRecord[]> {
  return request(`/api/threads/${encodeURIComponent(threadId)}/files`);
}

export async function uploadFile(
  threadId: string,
  file: File,
): Promise<FileRecord> {
  const body = new FormData();
  body.append("file", file);
  // 让浏览器生成 multipart boundary，禁止手工设置 Content-Type。
  const response = await fetch(
    `/api/threads/${encodeURIComponent(threadId)}/files`,
    { method: "POST", body },
  );
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      `${data.detail?.code ?? response.status}: ${data.detail?.message ?? "上传失败"}`,
    );
  return data;
}

export type ArtifactRecord = {
  artifact_id: string;
  file_id: string;
  display_name: string;
  size_bytes: number;
  mime: string;
  run_id: string;
  created_at: string;
};

export function listArtifacts(threadId: string): Promise<ArtifactRecord[]> {
  return request(`/api/threads/${encodeURIComponent(threadId)}/artifacts`);
}

export async function downloadArtifact(
  threadId: string,
  artifactId: string,
): Promise<Blob> {
  const response = await fetch(
    `/api/artifacts/${encodeURIComponent(artifactId)}?thread_id=${encodeURIComponent(threadId)}`,
  );
  if (!response.ok) {
    const data = await response.json();
    throw new Error(
      `${data.detail?.code ?? response.status}: ${data.detail?.message ?? "下载失败"}`,
    );
  }
  return response.blob();
}
