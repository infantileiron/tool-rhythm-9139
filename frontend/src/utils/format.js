const escapes = {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'};
export const esc = (value = '') => String(value ?? '').replace(/[&<>"']/g, match => escapes[match]);
export const number = value => new Intl.NumberFormat('zh-CN').format(Number(value));
export const pad = value => String(value).padStart(2, '0');
export const band = ([a, b]) => `${pad(a)}:00–${pad(b)}:00`;
export const pct = value => `${(value * 100).toFixed(1)}%`;
export const localDateTime = value => new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
}).format(new Date(value.replace(' ', 'T') + 'Z'));
