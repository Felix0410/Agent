/** P02-A 会话 API；此阶段不提供 Run 提交或流式订阅。 */
import { request } from '../api';

export type ThreadDto = {
  id: string;
  title: string;
  needs_recovery: boolean;
  created_at: string;
  updated_at: string;
};

export type RunDto = {
  id: string;
  thread_id: string;
  input_message: string;
  status: 'CREATED' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED';
  answer: string | null;
  tool_calls: {
    name: string;
    args: Record<string, unknown>;
    result: string;
    ok: boolean;
  }[];
  error_code: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export function createThread(title?: string): Promise<ThreadDto> {
  return request('/api/threads', title === undefined ? {} : { title });
}

export function listThreads(): Promise<ThreadDto[]> {
  return request('/api/threads');
}

export function listRuns(threadId: string): Promise<RunDto[]> {
  return request(`/api/threads/${encodeURIComponent(threadId)}/runs?limit=50`);
}

export type RunAccepted = { run_id: string; thread_id: string; status: 'CREATED' };

export function startRun(threadId: string, message: string): Promise<RunAccepted> {
  return request(`/api/threads/${encodeURIComponent(threadId)}/runs`, { message });
}

export function getRun(runId: string): Promise<RunDto> {
  return request(`/api/runs/${encodeURIComponent(runId)}`);
}

export function isTerminal(run: RunDto): boolean {
  return ['SUCCEEDED', 'FAILED', 'CANCELLED'].includes(run.status);
}
