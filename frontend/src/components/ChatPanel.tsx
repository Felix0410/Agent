import { useEffect, useState } from 'react';
import { getRun, isTerminal, listRuns, startRun } from '../api/runtime';
import type { RunDto, ThreadDto } from '../api/runtime';
import RunStatus from './RunStatus';

/** 单会话的历史和后台 Run；切换会话时由 App 的 key 重新建立独立生命周期。 */
export default function ChatPanel({ thread }: { thread: ThreadDto | null }) {
  const [runs, setRuns] = useState<RunDto[]>([]);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [activeRun, setActiveRun] = useState<string | null>(null);
  const [recovering, setRecovering] = useState(thread?.needs_recovery ?? false);

  useEffect(() => {
    if (!thread) return;
    let live = true;
    setLoading(true);
    // 1. 页面刷新只读真实 Run 历史；活动 Run 从服务端状态恢复轮询。
    listRuns(thread.id).then((data) => {
      if (!live) return;
      setRuns(data);
      setActiveRun(data.find((run) => !isTerminal(run))?.id ?? null);
      if (data.some((run) => run.status === 'FAILED' && run.started_at)) setRecovering(true);
    }).catch((reason) => { if (live) setError(String(reason)); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [thread?.id]);

  useEffect(() => {
    if (!activeRun || !thread) return;
    let live = true;
    let timer: ReturnType<typeof setTimeout>;
    let attempts = 0;
    // 2. 串行有限轮询，不叠加请求；断网不代表后台模型失败。
    async function poll() {
      try {
        const run = await getRun(activeRun!);
        if (!live) return;
        setRuns((old) => [...old.filter((item) => item.id !== run.id), run]);
        if (isTerminal(run)) {
          setActiveRun(null);
          if (run.status === 'FAILED' && run.started_at) setRecovering(true);
          return;
        }
      } catch (reason) {
        if (live) setError(String(reason));
      }
      if (!live) return;
      if (++attempts >= 180) {
        setError('状态查询已达上限，请刷新页面重新查询；后台任务不会被取消。');
        return;
      }
      timer = setTimeout(poll, 1000);
    }
    void poll();
    return () => { live = false; clearTimeout(timer); };
  }, [activeRun, thread?.id]);

  async function send() {
    if (!thread || !message.trim() || sending || activeRun) return;
    setSending(true);
    setError('');
    try {
      // 3. 202 只是接收确认；后续 GET Run 才决定最终显示的状态与结果。
      const accepted = await startRun(thread.id, message);
      setMessage('');
      setActiveRun(accepted.run_id);
    } catch (reason) {
      setError(String(reason));
      if (String(reason).includes('THREAD_REQUIRES_RECOVERY')) setRecovering(true);
    } finally {
      setSending(false);
    }
  }

  return (
    <section aria-label="会话聊天">
      <h2>{thread ? `当前会话：${thread.title}` : '请选择会话'}</h2>
      {loading && <p>正在加载历史…</p>}
      {!loading && thread && runs.length === 0 && <p>此会话暂无 Run 历史。</p>}
      {runs.map((run) => <RunStatus key={run.id} run={run} />)}
      {recovering && <p role="alert">此会话需恢复，请新建会话继续。</p>}
      {error && <output role="alert">{error}</output>}
      <label>会话消息
        <textarea maxLength={2000} value={message} onChange={(event) => setMessage(event.target.value)} />
      </label>
      <button disabled={!thread || loading || recovering || sending || !!activeRun || !message.trim()} onClick={send}>
        {sending ? '正在提交…' : activeRun ? '后台执行中…' : '发送到会话'}
      </button>
    </section>
  );
}
