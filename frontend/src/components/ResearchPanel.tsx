import { useEffect, useState } from "react";
import { getEvidence, getResearchStatus } from "../api/research";
import type { Evidence, ResearchStatus } from "../api/research";

/** 来源文字仅作为React文本；不插入HTML、不加载来源图片或favicon。 */
export default function ResearchPanel({ runId, status, revision }: {
  runId: string; status: string; revision: number;
}) {
  const [capability, setCapability] = useState<ResearchStatus | null>(null);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    // 事件只触发重新读取；历史/刷新/终态始终以HTTP持久记录为准。
    Promise.all([getResearchStatus(), getEvidence(runId)])
      .then(([available, items]) => {
        if (active) { setCapability(available); setEvidence(items); setError(""); }
      })
      .catch((e) => { if (active) setError(String(e)); });
    return () => { active = false; };
  }, [runId, status, revision]);
  const labels = { SNIPPET_ONLY: "仅搜索摘要，正文未核验", EXTRACTED: "Tavily已提取正文，事实仍待核验", EXTRACTION_FAILED: "正文提取失败，仅摘要线索" };
  return <section aria-label="联网研究">
    <h4>联网研究 · {evidence.length} 条证据</h4>
    <p>Lead 与 Research 子任务共享本 Run 证据；General 保持离线，子任务只读。</p>
    {capability && !capability.enabled && <p>尚未配置 Tavily，联网研究不可用；已有证据仍可查询。</p>}
    {error && <p role="alert">{error}</p>}
    {evidence.map((item) => <details key={item.id}>
      <summary>{item.title || item.url} · {labels[item.source_status]}</summary>
      <p>证据 ID：{item.id}</p>
      <a href={item.url} target="_blank" rel="noopener noreferrer">{item.url}</a>
      <p>检索时间：{item.searched_at}</p>
      <output>{item.excerpt}</output>
    </details>)}
  </section>;
}
