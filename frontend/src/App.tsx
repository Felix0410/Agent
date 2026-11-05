import { useState } from 'react';
import { request } from './api';

type AgentResponse = {
  answer: string;
  tool_calls: {
    name: string;
    args: Record<string, unknown>;
    result: string;
    ok: boolean;
  }[];
};

export default function App() {
  const [health, setHealth] = useState('尚未检查');
  const [expression, setExpression] = useState('(12+8)*3');
  const [result, setResult] = useState('');
  const [healthBusy, setHealthBusy] = useState(false);
  const [calcBusy, setCalcBusy] = useState(false);
  const [message, setMessage] = useState('请计算 (12+8)*3');
  const [agentBusy, setAgentBusy] = useState(false);
  const [agentError, setAgentError] = useState('');
  const [agentResponse, setAgentResponse] = useState<AgentResponse | null>(null);

  async function askAgent() {
    // 1. 清空上一次结果并显示等待态，防止把历史回答误认为当前请求的结果。
    setAgentBusy(true);
    setAgentError('');
    setAgentResponse(null);

    try {
      // 2. 调用真实后端；回答与工具调用轨迹都来自服务端实际执行消息。
      setAgentResponse(await request<AgentResponse>('/api/demo/agent', { message }));
    } catch (error) {
      setAgentError(String(error));
    } finally {
      // 3. 无论成功还是失败都恢复交互状态，不伪造 Agent 的完成结果。
      setAgentBusy(false);
    }
  }

  async function checkHealth() {
    setHealthBusy(true);
    try {
      const data = await request<{ status: string }>('/health');
      setHealth(data.status);
    } catch (error) {
      setHealth(String(error));
    } finally {
      setHealthBusy(false);
    }
  }

  async function compute() {
    setCalcBusy(true);
    setResult('');
    try {
      const data = await request<{ result: string }>('/api/demo/calculate', { expression });
      setResult(data.result);
    } catch (error) {
      setResult(String(error));
    } finally {
      setCalcBusy(false);
    }
  }

  return (
    <main>
      <header>
        <p>本地开发验证台</p>
        <h1>Mini DeerFlow</h1>
      </header>

      {/* 健康检查和计算器独立运行，不依赖模型配置。 */}
      <section>
        <h2>服务健康</h2>
        <button disabled={healthBusy} onClick={checkHealth}>
          {healthBusy ? '检查中…' : '检查健康'}
        </button>
        <output aria-live="polite">{health}</output>
      </section>

      <section>
        <h2>安全计算器</h2>
        <label>
          算式
          <input value={expression} onChange={(event) => setExpression(event.target.value)} />
        </label>
        <button disabled={calcBusy} onClick={compute}>
          {calcBusy ? '计算中…' : '计算'}
        </button>
        <output aria-live="polite">{result}</output>
      </section>

      <section>
        <h2>Agent 问答</h2>
        <p>需配置支持 Tool Calling 的模型。每次请求独立，不保留历史。</p>
        <label>
          问题
          <textarea
            value={message}
            maxLength={2000}
            onChange={(event) => setMessage(event.target.value)}
          />
        </label>
        <button disabled={agentBusy || !message.trim()} onClick={askAgent}>
          {agentBusy ? '等待模型…' : '发送'}
        </button>
        {agentError && <output role="alert">{agentError}</output>}

        {agentResponse && (
          <>
            <h3>最终答复</h3>
            <output>{agentResponse.answer}</output>
            <h3>实际工具调用轨迹</h3>
            {agentResponse.tool_calls.length === 0 ? (
              <p>本次没有工具调用</p>
            ) : (
              agentResponse.tool_calls.map((call, index) => (
                <article key={index}>
                  <strong>
                    {index + 1}. {call.name} · {call.ok ? '成功' : '失败'}
                  </strong>
                  <pre>{JSON.stringify(call.args, null, 2)}</pre>
                  <output>{call.result}</output>
                </article>
              ))
            )}
          </>
        )}
      </section>

      <footer>
        当前已实现：P00 健康 / P01 计算 / P01 Agent 入口（真实模型待配置验证）。后续：会话、SSE、Todo、文件。
      </footer>
    </main>
  );
}
