import { useEffect, useState } from "react";
import { getUsage } from "../api/runtime";
import type { RunUsage } from "../api/runtime";
/** 显示SQL权威用量，缺失Provider数字不会显示为零费用。 */
export default function UsagePanel({
  runId,
  status,
  revision,
}: {
  runId: string;
  status: string;
  revision: number;
}) {
  const [usage, setUsage] = useState<RunUsage | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    getUsage(runId)
      .then((data) => {
        if (live) {
          setUsage(data);
          setError("");
        }
      })
      .catch((e) => {
        if (live) setError(String(e));
      });
    return () => {
      live = false;
    };
  }, [runId, status, revision]);
  return (
    <section aria-label="运行用量">
      <h4>运行用量</h4>
      {error && <p role="alert">{error}</p>}
      {usage?.recorded === false && (
        <p>此Run未开始或没有P06用量记录；Provider统计未知。</p>
      )}
      {usage && usage.recorded !== false && (
        <>
          <p>
            模型调用：{usage.model_calls} /{" "}
            {usage.budget.max_model_calls ?? "—"}；工具调用：{usage.tool_calls}{" "}
            / {usage.budget.max_tool_calls ?? "—"}
          </p>
          <p>
            Provider已报告输入/输出：
            {usage.provider_input_tokens === null
              ? "未提供统计"
              : `${usage.provider_input_tokens} / ${usage.provider_output_tokens}`}
          </p>
          <p>
            未返回Provider统计的调用：{usage.usage_unknown_calls}
            ；累计输入估算：{usage.estimated_input_tokens} /{" "}
            {usage.budget.max_input_tokens_estimate ?? "—"}（估算，非实际计费）
          </p>
          <p>
            已记录耗时：{(usage.elapsed_ms / 1000).toFixed(2)} /{" "}
            {usage.budget.max_seconds ?? "—"}秒；上下文压缩：
            {usage.compaction_count}；长结果引用：
            {usage.output_externalized_count}
          </p>
        </>
      )}
    </section>
  );
}
