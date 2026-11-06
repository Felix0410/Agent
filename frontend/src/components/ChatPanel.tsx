import { useEffect, useState } from "react";
import {
  getRun,
  isTerminal,
  listRuns,
  listThreads,
  startRun,
  subscribeRunEvents,
} from "../api/runtime";
import type { RunDto, ThreadDto } from "../api/runtime";
import RunStatus from "./RunStatus";
import type { LiveRun } from "./RunStatus";

/** 单会话的历史和后台 Run；切换会话时由 App 的 key 重新建立独立生命周期。 */
export default function ChatPanel({
  thread,
  onThreadUpdate,
}: {
  thread: ThreadDto | null;
  onThreadUpdate: (thread: ThreadDto) => void;
}) {
  const [runs, setRuns] = useState<RunDto[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [liveRun, setLiveRun] = useState<LiveRun>({
    fragments: {},
    answer: null,
    tools: {},
  });
  const [streamNotice, setStreamNotice] = useState("");
  const [activeRun, setActiveRun] = useState<string | null>(null);
  const [recovering, setRecovering] = useState(thread?.needs_recovery ?? false);

  useEffect(() => {
    if (!thread) return;
    let live = true;
    setLoading(true);
    // 1. 页面刷新只读真实 Run 历史；活动 Run 从服务端状态恢复轮询。
    listRuns(thread.id)
      .then((data) => {
        if (!live) return;
        setRuns(data);
        setActiveRun(data.find((run) => !isTerminal(run))?.id ?? null);
      })
      .catch((reason) => {
        if (live) setError(String(reason));
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [thread?.id]);

  useEffect(() => {
    if (!activeRun || !thread) return;
    let live = true;
    let timer: ReturnType<typeof setTimeout>;
    let attempts = 0;
    let version = 0;
    setLiveRun({ fragments: {}, answer: null, tools: {} });
    setStreamNotice("");
    // 1. 任何流终态都要重新 GET；版本号防止较早的 RUNNING 响应覆盖新终态。
    async function poll() {
      clearTimeout(timer);
      const ticket = ++version;
      try {
        const run = await getRun(activeRun!);
        if (!live || ticket !== version) return;
        setRuns((old) => [...old.filter((item) => item.id !== run.id), run]);
        if (isTerminal(run)) {
          stopStream();
          // started_at 不等于 Graph 已写入；恢复标志必须读取权威 Thread 数据。
          try {
            const fresh = (await listThreads()).find(
              (item) => item.id === thread!.id,
            );
            if (live && fresh) {
              setRecovering(fresh.needs_recovery);
              onThreadUpdate(fresh);
            }
          } catch (reason) {
            if (live) setError(String(reason));
          }
          if (live) setActiveRun(null);
          return;
        }
      } catch (reason) {
        if (live && ticket === version) setError(String(reason));
      }
      if (!live || ticket !== version) return;
      if (++attempts >= 180) {
        stopStream();
        setError("状态查询已达上限，请刷新重新查询；后台任务不会被取消。");
        return;
      }
      timer = setTimeout(poll, 1000);
    }
    // 2. Token 按 message_id 分组；最终文本覆盖临时片段，工具按真实调用 ID 配对。
    const stopStream = subscribeRunEvents(
      activeRun,
      thread.id,
      (event) => {
        if (!live) return;
        const p = event.payload;
        if (
          event.type === "assistant_delta" &&
          typeof p.message_id === "string" &&
          typeof p.text === "string"
        ) {
          const id = p.message_id;
          const text = p.text;
          setLiveRun((old) => ({
            ...old,
            fragments: {
              ...old.fragments,
              [id]: (old.fragments[id] ?? "") + text,
            },
          }));
        } else if (
          event.type === "assistant_final" &&
          typeof p.answer === "string"
        ) {
          const answer = p.answer;
          setLiveRun((old) => ({ ...old, answer }));
        } else if (
          event.type === "tool_start" &&
          typeof p.tool_call_id === "string" &&
          typeof p.name === "string"
        ) {
          const id = p.tool_call_id;
          const name = p.name;
          setLiveRun((old) => ({
            ...old,
            tools: { ...old.tools, [id]: { name, args: p.args } },
          }));
        } else if (
          event.type === "tool_end" &&
          typeof p.tool_call_id === "string" &&
          typeof p.result === "string" &&
          typeof p.ok === "boolean"
        ) {
          const id = p.tool_call_id;
          const result = p.result;
          const ok = p.ok;
          setLiveRun((old) =>
            old.tools[id]
              ? {
                  ...old,
                  tools: {
                    ...old.tools,
                    [id]: { ...old.tools[id], result, ok },
                  },
                }
              : old,
          );
        } else if (event.type === "run_end" || event.type === "stream_gap") {
          stopStream();
          if (event.type === "stream_gap") {
            setLiveRun({ fragments: {}, answer: null, tools: {} });
            setStreamNotice("流有缺口，已停止拼接，正在查询服务端状态。");
          }
          void poll();
        }
      },
      () => {
        if (!live) return;
        setStreamNotice("流暂不可用，正在查询服务端状态；后台仍继续执行。");
        void poll();
      },
    );
    // 3. 轮询是断线/过期兜底；切换只关闭本地订阅，不向后端发送取消。
    void poll();
    return () => {
      live = false;
      clearTimeout(timer);
      stopStream();
    };
  }, [activeRun, thread?.id]);

  async function send() {
    if (!thread || !message.trim() || sending || activeRun) return;
    setSending(true);
    setError("");
    try {
      // 3. 202 只是接收确认；后续 GET Run 才决定最终显示的状态与结果。
      const accepted = await startRun(thread.id, message);
      setMessage("");
      setActiveRun(accepted.run_id);
    } catch (reason) {
      setError(String(reason));
      if (String(reason).includes("THREAD_REQUIRES_RECOVERY"))
        setRecovering(true);
    } finally {
      setSending(false);
    }
  }

  return (
    <section aria-label="会话聊天">
      <h2>{thread ? `当前会话：${thread.title}` : "请选择会话"}</h2>
      {loading && <p>正在加载历史…</p>}
      {!loading && thread && runs.length === 0 && <p>此会话暂无 Run 历史。</p>}
      {runs.map((run) => (
        <RunStatus
          key={run.id}
          run={run}
          live={run.id === activeRun ? liveRun : undefined}
        />
      ))}
      {recovering && <p role="alert">此会话需恢复，请新建会话继续。</p>}
      {streamNotice && <p role="status">{streamNotice}</p>}
      {error && <output role="alert">{error}</output>}
      <label>
        会话消息
        <textarea
          maxLength={2000}
          value={message}
          onChange={(event) => setMessage(event.target.value)}
        />
      </label>
      <button
        disabled={
          !thread ||
          loading ||
          recovering ||
          sending ||
          !!activeRun ||
          !message.trim()
        }
        onClick={send}
      >
        {sending ? "正在提交…" : activeRun ? "后台执行中…" : "发送到会话"}
      </button>
    </section>
  );
}
