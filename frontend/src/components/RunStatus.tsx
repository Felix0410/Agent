import type { RunDto } from '../api/runtime';

/** 只展示持久化终态，不把模型的“完成”措辞作为成功证据。 */
export default function RunStatus({ run }: { run: RunDto }) {
  return (
    <article>
      <p><strong>你：</strong>{run.input_message}</p>
      <p>状态：{run.status}</p>
      {run.status === 'SUCCEEDED' && <output>{run.answer}</output>}
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
