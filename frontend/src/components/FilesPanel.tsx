import { useEffect, useRef, useState } from 'react';
import { listFiles, uploadFile } from '../api/files';
import type { FileRecord } from '../api/files';

/** 只展示已登记的文件；切换 Thread 后卸载旧面板并重新加载。 */
export default function FilesPanel({ threadId, refreshKey = 0 }: {threadId:string;refreshKey?:number}) {
  const [files,setFiles]=useState<FileRecord[]>([]);
  const [selected,setSelected]=useState<File|null>(null);
  const [busy,setBusy]=useState(false);
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState('');
  const alive=useRef(true);
  const version=useRef(0);

  async function refresh() {
    const ticket=++version.current;
    setLoading(true);
    try {
      const records=await listFiles(threadId);
      if(alive.current && ticket===version.current) setFiles(records);
    } catch(reason) {
      if(alive.current && ticket===version.current) setError(String(reason));
    } finally {
      if(alive.current && ticket===version.current) setLoading(false);
    }
  }
  useEffect(()=>{
    alive.current=true;
    void refresh();
    return ()=>{alive.current=false;++version.current;};
  },[threadId,refreshKey]);

  async function upload() {
    if(!selected || busy) return;
    setBusy(true);setError('');
    try {
      // 成功响应只包含已安全落盘并登记的资源，不按原文件名猜测磁盘位置。
      await uploadFile(threadId,selected);
      if(alive.current) await refresh();
    } catch(reason) {
      if(alive.current) setError(String(reason));
    } finally {if(alive.current) setBusy(false);}
  }
  return <section aria-label="会话文件">
    <h2>会话文件</h2>
    <p>文本 txt/md/csv/json：UTF-8，最多2MiB。PDF最多10MiB，仅存储，暂不解析。每会话50项、30MiB。</p>
    <label>选择上传文件<input type="file" accept=".txt,.md,.csv,.json,.pdf" onChange={event=>setSelected(event.target.files?.[0]??null)}/></label>
    <button disabled={!selected||busy} onClick={upload}>{busy?'上传中…':'上传到当前会话'}</button>
    <button disabled={busy||loading} onClick={refresh}>刷新文件</button>
    {error && <output role="alert">{error}</output>}
    {loading && <p>正在读取文件列表…</p>}
    {!loading && files.length===0 && <p>当前会话没有已登记文件。</p>}
    <ul>{files.map(file=><li key={file.id}>
      <strong>{file.display_name}</strong> · {file.size_bytes} bytes · {file.mime}
      {file.mime==='application/pdf' && <span>（仅存储，暂不解析）</span>}
      <p className="thread-id">文件ID：{file.id}</p>
    </li>)}</ul>
  </section>;
}
