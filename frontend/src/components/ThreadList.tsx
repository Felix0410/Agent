import { useEffect, useRef, useState } from 'react';
import { createThread, listRuns, listThreads } from '../api/runtime';
import type { RunDto, ThreadDto } from '../api/runtime';

/** 展示真实会话及历史查询结果；不把 P01 单轮请求混入持久会话。 */
export default function ThreadList() {
  const [threads, setThreads] = useState<ThreadDto[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [title, setTitle] = useState('');
  const [listBusy, setListBusy] = useState(true);
  const [creating, setCreating] = useState(false);
  const [listError, setListError] = useState('');
  const [runs, setRuns] = useState<RunDto[]>([]);
  const [historyBusy, setHistoryBusy] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const refreshVersion = useRef(0);

  async function refresh() {
    // 刷新与新建可能交错；只接收最后一次列表请求，避免旧结果覆盖新会话。
    const version = ++refreshVersion.current;
    setListBusy(true);
    setListError('');
    try {
      const data = await listThreads();
      if (version === refreshVersion.current) setThreads(data);
    } catch (error) {
      if (version === refreshVersion.current) setListError(String(error));
    } finally {
      if (version === refreshVersion.current) setListBusy(false);
    }
  }

  useEffect(() => {
    void refresh();
    return () => {
      ++refreshVersion.current;
    };
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    // 1. 切换时清空旧历史，后返回的旧会话响应不能写入新会话面板。
    let active = true;
    setRuns([]);
    setHistoryBusy(true);
    setHistoryError('');
    listRuns(selectedId)
      .then((data) => {
        if (active) setRuns(data);
      })
      .catch((error) => {
        if (active) setHistoryError(String(error));
      })
      .finally(() => {
        if (active) setHistoryBusy(false);
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  async function create() {
    setCreating(true);
    setListError('');
    try {
      // 2. 只展示后端实际保存的会话，成功后再刷新列表并选中新会话。
      const thread = await createThread(title.trim() || undefined);
      setTitle('');
      setSelectedId(thread.id);
      setThreads((items) => [thread, ...items.filter((item) => item.id !== thread.id)]);
      await refresh();
    } catch (error) {
      setListError(String(error));
    } finally {
      setCreating(false);
    }
  }

  const selected = threads.find((thread) => thread.id === selectedId);

  return (
    <section aria-label="会话工作台">
      <h2>会话工作台 · P02-A</h2>
      <div className="thread-workbench">
        <div>
          <label>
            会话标题（可选）
            <input maxLength={100} value={title} onChange={(event) => setTitle(event.target.value)} />
          </label>
          <div className="thread-actions">
            <button disabled={creating} onClick={create}>
              {creating ? '新建中…' : '新建会话'}
            </button>
            <button disabled={listBusy || creating} onClick={refresh}>刷新会话</button>
          </div>
          {listError && <output role="alert">{listError}</output>}
          {listBusy && <p role="status">正在加载会话…</p>}
          {!listBusy && !listError && threads.length === 0 && (
            <p>暂无会话，请新建。</p>
          )}
          <ul className="thread-list">
            {threads.map((thread) => (
              <li key={thread.id}>
                <button aria-pressed={selectedId === thread.id} onClick={() => setSelectedId(thread.id)}>
                  {thread.title}
                  {thread.needs_recovery ? ' · 需恢复' : ''}
                </button>
              </li>
            ))}
          </ul>
        </div>
        <div className="thread-detail" aria-live="polite">
          {selected ? (
            <>
              <h3>当前会话：{selected.title}</h3>
              <p className="thread-id">{selected.id}</p>
              {selected.needs_recovery && <p role="alert">此会话需恢复，请新建会话继续。</p>}
              {historyBusy && <p>正在查询历史…</p>}
              {historyError && <output role="alert">{historyError}</output>}
              {!historyBusy && !historyError && runs.length === 0 && (
                <p>此会话暂无 Run 历史。</p>
              )}
              {runs.map((run) => (
                <article key={run.id}>
                  <p>{run.input_message}</p>
                  <p>状态：{run.status}</p>
                  {run.status === 'SUCCEEDED' && run.answer && <output>{run.answer}</output>}
                  {run.error_code && <p role="alert">{run.error_code}</p>}
                </article>
              ))}
            </>
          ) : (
            <p>请选择或新建一个会话。</p>
          )}
          {/* 3. A 只有会话身份与历史查询，不能把一次性 Agent 伪装成后台 Run。 */}
          <button disabled>会话聊天（P02-B 尚未实现）</button>
        </div>
      </div>
    </section>
  );
}
