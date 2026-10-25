// 后端接口封装：同域 Cookie 登录，错误统一抛出中文提示
async function req(method, path, body, isForm) {
  const opt = { method, credentials: 'same-origin', headers: {} };
  if (body !== undefined) {
    if (isForm) opt.body = body;
    else { opt.body = JSON.stringify(body); opt.headers['Content-Type'] = 'application/json'; }
  }
  let r;
  try { r = await fetch('/api' + path, opt); } catch (e) { throw new Error('网络连接失败，请检查网络后重试'); }
  const t = await r.text(); let d = null;
  try { d = t ? JSON.parse(t) : null; } catch (e) { d = null; }
  if (!r.ok) { const err = new Error((d && (d.error || d.detail)) || `请求失败（${r.status}）`); err.status = r.status; err.data = d; throw err; }
  return d;
}
export const api = {
  get: p => req('GET', p), post: (p, b) => req('POST', p, b ?? {}), put: (p, b) => req('PUT', p, b), patch: (p, b) => req('PATCH', p, b), del: p => req('DELETE', p),
  upload: (p, form) => req('POST', p, form, true),
};
export const enc = encodeURIComponent;
export function go(path) { if (location.hash !== '#' + path) location.hash = path; }
