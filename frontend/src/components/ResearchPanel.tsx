import { useEffect, useState } from "react";
import { downloadArtifact } from "../api/files";
import { getEvidence, getReport, getResearchStatus } from "../api/research";
import type { Evidence, ResearchReport, ResearchStatus } from "../api/research";

/** 来源文字与Markdown只作为React文本，不插入HTML或自动加载外部资源。 */
export default function ResearchPanel({ runId, threadId, status, revision }: {
  runId: string;
  threadId: string;
  status: string;
  revision: number;
}) {
  const [capability, setCapability] = useState<ResearchStatus | null>(null);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [report, setReport] = useState<ResearchReport | null>(null);
  const [markdown, setMarkdown] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setMarkdown("");
    // 事件只触发重新读取；历史/刷新/终态始终以HTTP持久记录为准。
    Promise.all([getResearchStatus(), getEvidence(runId), getReport(runId)])
      .then(([available, items, saved]) => {
        if (active) {
          setCapability(available);
          setEvidence(items);
          setReport(saved);
          setError("");
        }
      })
      .catch((e) => {
        if (active) setError(String(e));
      });
    return () => { active = false; };
  }, [runId, status, revision]);

  async function openReport(download: boolean) {
    if (!report) return;
    try {
      // 1. 复用P03归属校验与SHA验证后的真实Artifact字节。
      const blob = await downloadArtifact(threadId, report.artifact_id);
      if (!download) {
        setMarkdown(await blob.text());
        return;
      }
      // 2. 只创建本地Blob下载，不把来源站点当文件获取地址。
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "research-report.md";
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setError(String(e));
    }
  }

  const labels = {
    SNIPPET_ONLY: "仅搜索摘要，正文未核验",
    EXTRACTED: "Tavily已提取正文，事实仍待核验",
    EXTRACTION_FAILED: "正文提取失败，仅摘要线索",
  };
  return (
    <section aria-label="联网研究">
      <h4>联网研究 · {evidence.length} 条证据</h4>
      <p>Lead 与 Research 子任务共享本 Run 证据；General 保持离线，子任务只读。</p>
      {capability && !capability.enabled && (
        <p>尚未配置 Tavily，联网研究不可用；已有证据仍可查询。</p>
      )}
      {error && <p role="alert">{error}</p>}
      {evidence.map((item) => (
        <details key={item.id}>
          <summary>{item.title || item.url} · {labels[item.source_status]}</summary>
          <p>证据 ID：{item.id}</p>
          <a href={item.url} target="_blank" rel="noopener noreferrer">{item.url}</a>
          <p>检索时间：{item.searched_at}</p>
          <output>{item.excerpt}</output>
        </details>
      ))}
      {report && (
        <section aria-label="研究报告">
          <h5>{report.title}</h5>
          <p>引用 {report.citations.length} 条真实来源；来源存在不等于主张已独立核真。</p>
          {report.limitations.map((item, index) => <p key={index}>局限：{item}</p>)}
          <button onClick={() => void openReport(false)}>查看报告</button>
          <button onClick={() => void openReport(true)}>下载研究报告</button>
          {markdown && <pre className="research-markdown">{markdown}</pre>}
        </section>
      )}
    </section>
  );
}
