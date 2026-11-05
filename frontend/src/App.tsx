import { useState } from 'react';
import { request } from './api';

export default function App() {
  const [health, setHealth] = useState('尚未检查');
  const [expression, setExpression] = useState('(12+8)*3');
  const [result, setResult] = useState('');
  const [healthBusy, setHealthBusy] = useState(false);
  const [calcBusy, setCalcBusy] = useState(false);
  async function checkHealth() {
    setHealthBusy(true);
    try { const data = await request<{status:string}>('/health'); setHealth(data.status); }
    catch (e) { setHealth(String(e)); } finally { setHealthBusy(false); }
  }
  async function compute() {
    setCalcBusy(true); setResult('');
    try { const data = await request<{result:string}>('/api/demo/calculate', {expression}); setResult(data.result); }
    catch (e) { setResult(String(e)); } finally { setCalcBusy(false); }
  }
  return <main><header><p>本地开发验证台</p><h1>Mini DeerFlow</h1></header>
    <section><h2>服务健康</h2><button disabled={healthBusy} onClick={checkHealth}>{healthBusy ? '检查中…' : '检查健康'}</button><output aria-live="polite">{health}</output></section>
    <section><h2>安全计算器</h2><label>算式<input value={expression} onChange={e=>setExpression(e.target.value)} /></label><button disabled={calcBusy} onClick={compute}>{calcBusy ? '计算中…' : '计算'}</button><output aria-live="polite">{result}</output></section>
    <section><h2>Agent 问答</h2><p>尚未实现</p><button disabled>发送</button></section>
    <footer>当前已实现：P00 健康 / P01 计算。后续：Agent、会话、SSE、Todo、文件。</footer>
  </main>;
}
