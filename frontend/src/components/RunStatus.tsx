import type { RunDto } from '../api/runtime';

/** 只展示持久化终态，不把模型的“完成”措辞作为成功证据。 */
export type LiveRun = {
  fragments: Record<string, string>;
  answer: string | null;
  tools: Record<string, {name: string; args: unknown; result?: string; ok?: boolean}>;
};

export default function RunStatus({ run, live }: { run: RunDto; live?: LiveRun }) {
  return (
    <article>
      <p><strong>你：</strong>{run.input_message}</p>
      <p>状态：{run.status}</p>
      {run.status === 'SUCCEEDED' && <output>{run.answer}</output>}
      {live && !['SUCCEEDED', 'FAILED', 'CANCELLED'].includes(run.status) && (
        <div aria-live="polite">
          <p>流式内容（待服务端确认终态）</p>
          <output>{live.answer ?? Object.values(live.fragments).join('\n')}</output>
          {Object.entries(live.tools).map(([id, tool]) => (
            <div className="tool-trace" key={id}>
              <strong>{tool.name} · {tool.ok === undefined ? '调用中' : tool.ok ? '成功' : '失败'}</strong>
              <p className="thread-id">调用 ID：{id}</p>
              <pre>{JSON.stringify(tool.args, null, 2)}</pre>
              <output>{tool.result}</output>
            </div>
          ))}
        </div>
      )}
      {run.error_code && <p role="alert">执行失败：{run.error_code}</p>}
      {run.tool_calls.map((call, index) => (
        <div key={index} className="tool-trace">
          <strong>{call.name} · {call.ok ? '成功' : '失败'}</strong>
          <pre>{JSON.stringify(call.args, null, 2)}</pre>
          <output>{call.result}</output>
        </div>
      ))}
    </article>
  );
}
