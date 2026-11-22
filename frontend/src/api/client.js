import {workbench} from '../stores/workbench.js';

async function request(path, {method = 'GET', body, download = false} = {}) {
  const headers = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (workbench.user) headers.Authorization = `Bearer ${workbench.user.token}`;
  let response;
  try {
    response = await fetch(`/api${path}`, {method, headers, body: body === undefined ? undefined : JSON.stringify(body)});
  } catch {
    throw new Error('连接不到工具站服务，请检查网络后重试。');
  }
  if (!response.ok) {
    if (response.status === 401 && path !== '/login') {
      document.dispatchEvent(new Event('session-expired'));
    }
    const payload = await response.json().catch(() => ({}));
    const detail = payload.detail;
    const message = typeof detail === 'string' ? detail
      : detail?.message ? `${detail.message}：${(detail.rows || []).join('；')}`
      : payload.fields ? `请核对输入字段：${payload.fields.join('、')}`
      : `服务暂时不可用（${response.status}），请稍后重试。`;
    throw new Error(message);
  }
  return download ? response.blob() : response.json();
}

export const api = {
  login: body => request('/login', {method: 'POST', body}),
  stations: () => request('/stations'),
  addStation: body => request('/stations', {method: 'POST', body}),
  records: (query, page) => request(`/records/search?page=${page}`, {method: 'POST', body: query}),
  addRecord: body => request('/records', {method: 'POST', body}),
  correctRecord: (id, body) => request(`/records/${id}`, {method: 'PATCH', body}),
  imports: () => request('/imports'),
  importLedger: body => request('/imports', {method: 'POST', body}),
  reconcile: (query, station) => request(`/reconcile${station ? `?station_code=${encodeURIComponent(station)}` : ''}`, {method: 'POST', body: query}),
  runs: () => request('/runs'),
  run: id => request(`/runs/${id}`),
  runTrace: id => request(`/runs/${id}/trace`),
  createRun: body => request('/runs', {method: 'POST', body}),
  publish: (id, body) => request(`/runs/${id}/publish`, {method: 'POST', body}),
  download: id => request(`/runs/${id}/duty.csv`, {download: true}),
};
