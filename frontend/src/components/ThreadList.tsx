import { useEffect, useRef, useState } from 'react';
import { createThread, listThreads } from '../api/runtime';
import type { ThreadDto } from '../api/runtime';

/** 展示真实会话及历史查询结果；不把 P01 单轮请求混入持久会话。 */
export default function ThreadList({ selectedId, onSelect }: {
  selectedId: string | null;
  onSelect: (thread: ThreadDto) => void;
}) {
  const [threads, setThreads] = useState<ThreadDto[]>([]);
  const [title, setTitle] = useState('');
  const [listBusy, setListBusy] = useState(true);
  const [creating, setCreating] = useState(false);
  const [listError, setListError] = useState('');
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


  async function create() {
    setCreating(true);
    setListError('');
    try {
      // 2. 只展示后端实际保存的会话，成功后再刷新列表并选中新会话。
      const thread = await createThread(title.trim() || undefined);
      setTitle('');
      onSelect(thread);
      setThreads((items) => [thread, ...items.filter((item) => item.id !== thread.id)]);
      await refresh();
    } catch (error) {
      setListError(String(error));
    } finally {
      setCreating(false);
    }
  }


  return (
    <section aria-label="会话工作台">
      <h2>会话列表</h2>
      <div className="thread-selector">
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
                <button aria-pressed={selectedId === thread.id} onClick={() => onSelect(thread)}>
                  {thread.title}
                  {thread.needs_recovery ? ' · 需恢复' : ''}
                </button>
              </li>
            ))}
          </ul>
        </div>

      </div>
    </section>
  );
}
