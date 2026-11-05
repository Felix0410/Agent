/** P01 本地调试页的统一请求入口，封装成功响应与结构化错误。 */
export async function request<T>(path: string, body?: object): Promise<T> {
  // 1. 无请求体时使用 GET；有请求体时发送 JSON POST，交给 Vite 代理转发。
  const response = await fetch(
    path,
    body === undefined
      ? undefined
      : {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        },
  );

  // 2. 按后端约定提取业务错误码；成功时返回原始数据供各测试区独立展示。
  const data = await response.json();
  if (!response.ok) {
    throw new Error(
      typeof data.detail === 'object' && !Array.isArray(data.detail)
        ? `${data.detail.code}: ${data.detail.message}`
        : JSON.stringify(data.detail),
    );
  }
  return data;
}
