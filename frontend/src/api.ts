export async function request<T>(path: string, body?: object): Promise<T> {
  const response = await fetch(path, body === undefined ? undefined : {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'object' && !Array.isArray(data.detail)
    ? `${data.detail.code}: ${data.detail.message}` : JSON.stringify(data.detail));
  return data;
}
