import { useEffect, useState } from "react";
import { getTodos } from "../api/runtime";
import type { TodoItem } from "../api/runtime";

/** 每个 Run 独立快照；切换/终态/缺口时重新读取 SQL 权威结果。 */
export default function TodoPanel({runId, status, snapshot, revision}: {runId:string; status:string; snapshot?:TodoItem[]; revision:number}) {
  const [items,setItems] = useState<TodoItem[]>([]);
  const [error,setError] = useState("");
  useEffect(() => {
    let live=true;
    getTodos(runId).then(data=>{if(live){setItems(data);setError("");}}).catch(e=>{if(live)setError(String(e));});
    return ()=>{live=false;};
  },[runId,status,revision]);
  useEffect(()=>{if(snapshot)setItems(snapshot);},[snapshot]);
  return <section aria-label="任务计划"><h4>任务计划</h4>{error && <p role="alert">{error}</p>}{items.length===0 ? <p>本次未使用计划</p> : <ol>{items.map(item=><li key={item.todo_id}>{item.title} · {item.status}</li>)}</ol>}</section>;
}
