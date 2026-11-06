import { useEffect, useState } from "react";
import { getSubtasks } from "../api/runtime";
import type { TaskRecord } from "../api/runtime";

/** 历史由 SQL 恢复；任务完成只认服务端状态。 */
export default function TaskPanel({runId,status,revision}:{runId:string;status:string;revision:number}) {
  const [items,setItems]=useState<TaskRecord[]>([]);
  const [error,setError]=useState("");
  useEffect(()=>{
    let live=true;
    getSubtasks(runId).then(data=>{if(live){setItems(data);setError("");}}).catch(e=>{if(live)setError(String(e));});
    return ()=>{live=false;};
  },[runId,status,revision]);
  return <section aria-label="子任务"><h4>子任务</h4>{error && <p role="alert">{error}</p>}{items.length===0 && <p>本次未使用委派</p>}{items.map(item=><article key={item.id}><strong>{item.agent_type}{item.agent_type==="research" && "（仅已有材料，无联网）"} · {item.status}</strong><p>{item.description}</p><p>{item.result_summary}{item.truncated && "（摘要已截断）"}</p>{item.error_code && <p role="alert">{item.error_code}</p>}<p className="thread-id">来源文件：{item.source_file_ids.join(", ") || "无已验证文件引用"}</p><small>{item.created_at}</small></article>)}</section>;
}
