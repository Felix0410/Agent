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
            模型调用：{usage.model_calls}；工具调用：{usage.tool_calls}
            {usage.budget.mode === "observe_only"
              ? "（仅统计，不设调用次数或字节执行额度）"
              : "（历史Run统计；原预算仅供查阅）"}
          </p>
          <p>
            Provider已报告输入/输出（真实Token）：
            {usage.provider_input_tokens === null
              ? "未提供统计"
              : `${usage.provider_input_tokens} / ${usage.provider_output_tokens}`}
          </p>
          <p>未返回Provider统计的调用：{usage.usage_unknown_calls}</p>
          {usage.budget.mode === "observe_only" && (
            <>
              <p>摘要模型尝试：{usage.summary_calls}；原生自动摘要次数：{usage.compaction_count}</p>
              <p>
                自动摘要：{usage.summary_settings.enabled ? "已启用" : "已关闭"}；
                触发条件为约 {usage.summary_settings.trigger_tokens ?? "—"} Token 或{" "}
                {usage.summary_settings.trigger_messages ?? "—"} 条消息，保留最近{" "}
                {usage.summary_settings.keep_messages ?? "—"} 条（工具配对由框架保护）。
                这是 LangChain 近似触发值，非Provider真实窗口或执行额度。
              </p>
              {usage.summary_diagnostic && (
                <p>
                  最近摘要消息数：{usage.summary_diagnostic.old_message_count} →{" "}
                  {usage.summary_diagnostic.new_message_count}；近似Token：{" "}
                  {usage.summary_diagnostic.estimated_before} → {usage.summary_diagnostic.estimated_after}；
                  耗时 {usage.summary_diagnostic.elapsed_ms} ms。
                </p>
              )}
            </>
          )}
          {usage.budget.mode !== "observe_only" && (
            <p>
              历史UTF-8字节近似诊断（非真实Token、非当前执行额度）：
              {usage.estimated_input_tokens}（{usage.estimate_unit}）
            </p>
          )}
          {usage.budget.mode !== "observe_only" && usage.estimated_input_tokens_v2 !== null && (
            <p>输入Token保守预估：{usage.estimated_input_tokens_v2}（{usage.estimated_token_unit} / {usage.estimator_version}；覆盖 {usage.estimated_v2_calls} 次调用，非Provider实际统计）</p>
          )}
          {usage.budget.mode !== "observe_only" && usage.context_breakdown && (
            <p>
              最近请求：System {usage.context_breakdown.system_bytes}；工具定义{" "}
              {usage.context_breakdown.tool_schema_bytes}；消息{" "}
              {usage.context_breakdown.message_bytes}；合计{" "}
              {usage.context_breakdown.total_bytes} / {usage.context_breakdown.hard_bytes} 字节近似。
              原因：{usage.context_breakdown.reason}
            </p>
          )}
          {usage.tool_history_compaction_count > 0 && (
            <p>已压缩本轮工具历史：{usage.tool_history_compaction_count} 次，完整来源仍保留。</p>
          )}
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
