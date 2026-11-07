/** P02 会话、Run 与有限 SSE 订阅；不向浏览器提供任何模型凭据。 */
import { request } from "../api";

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
  status: "CREATED" | "RUNNING" | "SUCCEEDED" | "FAILED" | "CANCELLED";
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
  return request("/api/threads", title === undefined ? {} : { title });
}

export function listThreads(): Promise<ThreadDto[]> {
  return request("/api/threads");
}

export function listRuns(threadId: string): Promise<RunDto[]> {
  return request(`/api/threads/${encodeURIComponent(threadId)}/runs?limit=50`);
}

export type RunAccepted = {
  run_id: string;
  thread_id: string;
  status: "CREATED";
};

export function startRun(
  threadId: string,
  message: string,
): Promise<RunAccepted> {
  return request(`/api/threads/${encodeURIComponent(threadId)}/runs`, {
    message,
  });
}

export function getRun(runId: string): Promise<RunDto> {
  return request(`/api/runs/${encodeURIComponent(runId)}`);
}

export function isTerminal(run: RunDto): boolean {
  return ["SUCCEEDED", "FAILED", "CANCELLED"].includes(run.status);
}

export type RunEvent = {
  event_id: string;
  run_id: string;
  thread_id: string;
  type: string;
  timestamp: string;
  payload: Record<string, unknown>;
};

/** 有限原生重连；自定义事件必须显式注册，过期/缺口交给 GET Run 兜底。 */
export function subscribeRunEvents(
  runId: string,
  threadId: string,
  onEvent: (event: RunEvent) => void,
  onUnavailable: () => void,
): () => void {
  const source = new EventSource(
    `/api/runs/${encodeURIComponent(runId)}/events`,
  );
  let sequence = 0;
  let reconnects = 0;
  let closed = false;
  const stop = () => {
    closed = true;
    source.close();
  };
  const unavailable = () => {
    stop();
    onUnavailable();
  };
  const kinds = [
    "todo_updated",
    "subtask_created",
    "subtask_started",
    "subtask_completed",
    "subtask_failed",
    "budget_updated",
    "context_compacted",
    "tool_output_externalized",
    "run_start",
    "assistant_delta",
    "tool_start",
    "tool_end",
    "assistant_final",
    "error",
    "run_end",
    "stream_gap",
  ];
  // 1. 校验当前 Run/Thread 与递增 ID，避免重放或切换时把旧数据串入新会话。
  for (const kind of kinds) {
    source.addEventListener(kind, (raw) => {
      if (closed || !(raw instanceof MessageEvent)) return;
      try {
        const event = JSON.parse(raw.data) as RunEvent;
        if (
          event.run_id !== runId ||
          event.thread_id !== threadId ||
          event.type !== kind ||
          !event.payload ||
          typeof event.payload !== "object"
        ) {
          unavailable();
          return;
        }
        if (kind === "stream_gap") {
          stop();
          onEvent(event);
          return;
        }
        const prefix = `${runId}:`;
        const suffix = event.event_id?.startsWith(prefix)
          ? event.event_id.slice(prefix.length)
          : "";
        if (
          !/^[1-9][0-9]*$/.test(suffix) ||
          !Number.isSafeInteger(Number(suffix))
        ) {
          unavailable();
          return;
        }
        const next = Number(suffix);
        if (next <= sequence) return;
        if (next !== sequence + 1) {
          unavailable();
          return;
        }
        sequence = next;
        if (kind === "run_end") stop();
        onEvent(event);
      } catch {
        unavailable();
      }
    });
  }
  // 2. 断线只表示流暂不可用，不是模型失败；超过三次则关闭并有限轮询。
  source.onerror = (event) => {
    // 服务端 error 是带数据的业务事件，不能误算成网络重连失败。
    if (event instanceof MessageEvent) return;
    if (!closed && ++reconnects >= 3) unavailable();
  };
  return stop;
}

export type TodoItem = {
  todo_id: string;
  title: string;
  status: "pending" | "in_progress" | "completed";
  position: number;
};
export function getTodos(runId: string): Promise<TodoItem[]> {
  return request(`/api/runs/${encodeURIComponent(runId)}/todos`);
}

export type TaskRecord = {
  id: string;
  run_id: string;
  thread_id: string;
  agent_type: string;
  description: string;
  todo_id: string | null;
  status:
    "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "TIMED_OUT" | "CANCELLED";
  result_summary: string | null;
  error_code: string | null;
  source_file_ids: string[];
  truncated: boolean;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};
export function getSubtasks(runId: string): Promise<TaskRecord[]> {
  return request(`/api/runs/${encodeURIComponent(runId)}/subtasks`);
}

export type RunUsage = {
  run_id: string;
  model_calls: number;
  tool_calls: number;
  provider_input_tokens: number | null;
  provider_output_tokens: number | null;
  usage_unknown_calls: number;
  estimated_input_tokens: number;
  elapsed_ms: number;
  compaction_count: number;
  output_externalized_count: number;
  budget: Record<string, number>;
};
export const getUsage = (runId: string): Promise<RunUsage> =>
  request(`/api/runs/${encodeURIComponent(runId)}/usage`);
