import { useEffect, useState } from "react";
import { getTools, getSkills } from "../api/capabilities";
import type { ToolCapability, SkillCapability } from "../api/capabilities";

/** 真实目录只读展示；刷新GET不重新发现或批准MCP。 */
export default function CapabilityPanel() {
  const [tools, setTools] = useState<ToolCapability[]>([]);
  const [skills, setSkills] = useState<SkillCapability[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let live = true;
    setLoading(true);
    Promise.all([getTools(), getSkills()])
      .then(([t, s]) => {
        if (live) {
          setTools(t);
          setSkills(s);
          setError("");
        }
      })
      .catch((e) => {
        if (live) setError(String(e));
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [revision]);
  return (
    <section aria-label="能力目录">
      <h2>可用工具与 Skills</h2>
      <button disabled={loading} onClick={() => setRevision((v) => v + 1)}>
        刷新能力目录
      </button>
      <p>
        只读目录；MCP状态来自启动发现和实际调用；故障后停用，配置或服务恢复后需重启后端。research仅分析已有材料，不联网。
      </p>
      {error && <p role="alert">{error}</p>}
      {loading && <p>正在读取目录…</p>}
      <ul>
        {tools.map((t) => (
          <li key={t.name}>
            <strong>{t.name}</strong> · {t.source} · {t.permission} · {t.origin}{" "}
            · {t.availability}
          </li>
        ))}
      </ul>
      {!tools.some((t) => t.source === "mcp") && (
        <p>MCP 未启用，无外部工具。</p>
      )}
      <h3>本地 Skills（说明文本，不授予权限）</h3>
      {skills.length === 0 && <p>没有可用 Skill。</p>}
      <ul>
        {skills.map((s) => (
          <li key={s.name}>
            <strong>{s.name}</strong> · {s.availability}
            <p>{s.description}</p>
            <p>前置工具：{s.required_tools.join(", ") || "无"}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
