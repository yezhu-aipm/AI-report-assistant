import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react';
import { LOGO, IBTNS } from './svg.js';
import { nextHue, toggleDark } from '../fx/effects.js';

const ToastCtx = createContext(() => {});
export function ToastProvider({ children }) {
  const [msg, setMsg] = useState(null); const t = useRef();
  const show = useCallback(m => { setMsg(m); clearTimeout(t.current); t.current = setTimeout(() => setMsg(null), 2800); }, []);
  return <ToastCtx.Provider value={show}>{children}{msg && <div className="toast" role="status">{msg}</div>}</ToastCtx.Provider>;
}
export const useToast = () => useContext(ToastCtx);

export const Logo = () => <span className="logo" dangerouslySetInnerHTML={{ __html: LOGO }} />;

/* 换颜色、白天/夜间两个图标按钮 */
export function ThemeButtons() {
  const ref = useRef();
  useEffect(() => {
    const el = ref.current; if (!el) return;
    el.innerHTML = IBTNS.replace(/^<span class="ibtns">|<\/span>$/g, '');
    const spin = b => { b.classList.add('spin'); setTimeout(() => b.classList.remove('spin'), 420); };
    const h = el.querySelector('[data-hue]'), m = el.querySelector('[data-mode]');
    h.title = '换颜色'; m.title = '白天 / 夜间';
    h.onclick = e => { e.stopPropagation(); nextHue(); spin(h); };
    m.onclick = e => { e.stopPropagation(); toggleDark(); spin(m); };
  }, []);
  return <span className="ibtns" ref={ref} />;
}

/* 点击外部、滚动、Esc 自动关闭的弹出菜单，定位在触发按钮旁边 */
export function Popover({ anchor, onClose, children, align = 'right' }) {
  const ref = useRef(); const [pos, setPos] = useState(null);
  useEffect(() => {
    const m = ref.current; if (!m || !anchor) return;
    const r = anchor.getBoundingClientRect(), mw = m.offsetWidth, mh = m.offsetHeight;
    const left = align === 'right' ? r.right - mw : r.left;
    setPos({ left: Math.max(8, Math.min(innerWidth - mw - 8, left)), top: r.bottom + 6 + mh > innerHeight - 8 ? Math.max(8, r.top - mh - 6) : r.bottom + 6 });
  }, [anchor, children, align]);
  useEffect(() => { const f = ref.current && ref.current.querySelector('button:not(:disabled)'); f && f.focus({ preventScroll: true }); }, []);
  useEffect(() => {
    const down = e => { if (ref.current && !ref.current.contains(e.target) && !anchor.contains(e.target)) onClose(); };
    const key = e => { if (e.key === 'Escape') { onClose(); anchor && anchor.focus(); } };
    const sc = () => onClose();
    document.addEventListener('mousedown', down); document.addEventListener('keydown', key);
    addEventListener('scroll', sc, true); addEventListener('resize', sc);
    return () => { document.removeEventListener('mousedown', down); document.removeEventListener('keydown', key); removeEventListener('scroll', sc, true); removeEventListener('resize', sc); };
  }, [anchor, onClose]);
  const nav = e => {
    const items = [...ref.current.querySelectorAll('button:not(:disabled)')], i = items.indexOf(document.activeElement);
    if (e.key === 'ArrowDown') { e.preventDefault(); items[(i + 1) % items.length].focus(); }
    if (e.key === 'ArrowUp') { e.preventDefault(); items[(i - 1 + items.length) % items.length].focus(); }
  };
  return <div className="menu" role="menu" ref={ref} onKeyDown={nav} style={pos || { left: -9999, top: -9999 }} onClick={e => e.stopPropagation()}>{children}</div>;
}

export const I = {
  open: <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M9 2.5h4.5V7M13.5 2.5 7.5 8.5M12 9.5v3a1 1 0 0 1-1 1H3.5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h3" /></svg>,
  dl: <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M8 2.5v8M4.5 7.5 8 11l3.5-3.5M3 13.5h10" /></svg>,
  copy: <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"><rect x="5" y="5" width="8.5" height="8.5" rx="1.6" /><path d="M10.5 5V3.6A1.6 1.6 0 0 0 8.9 2H3.6A1.6 1.6 0 0 0 2 3.6v5.3a1.6 1.6 0 0 0 1.6 1.6H5" /></svg>,
  folder: <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"><path d="M2 4.5a1.5 1.5 0 0 1 1.5-1.5h3l1.5 1.5h4.5A1.5 1.5 0 0 1 14 6v5.5a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 2 11.5z" /></svg>,
  del: <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M2.5 4.5h11M6 4.5V3h4v1.5M4 4.5l.7 8.6a1 1 0 0 0 1 .9h4.6a1 1 0 0 0 1-.9l.7-8.6" /></svg>,
  pen: <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M10.5 2.5l3 3L6 13H3v-3z" /></svg>,
  plus: <svg width="14" height="14" viewBox="0 0 16 16"><path d="M8 3v10M3 8h10" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" /></svg>,
  dots: <svg width="16" height="16" viewBox="0 0 16 16"><circle cx="3.5" cy="8" r="1.4" fill="currentColor" /><circle cx="8" cy="8" r="1.4" fill="currentColor" /><circle cx="12.5" cy="8" r="1.4" fill="currentColor" /></svg>,
  chev: <svg className="chev" width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M6 3.5 10.5 8 6 12.5" /></svg>,
  back: <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M10 3.5 5.5 8 10 12.5" /></svg>,
  car: <svg width="12" height="12" viewBox="0 0 16 16"><path d="M6 4l4 4-4 4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>,
  all: <svg width="15" height="15" viewBox="0 0 16 16"><rect x="2" y="3" width="12" height="10" rx="2" fill="none" stroke="currentColor" strokeWidth="1.5" /><path d="M2 6h12" stroke="currentColor" strokeWidth="1.5" /></svg>,
  doc: <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"><path d="M4 2h5.5L12.5 5v8.5a.5.5 0 0 1-.5.5H4a.5.5 0 0 1-.5-.5v-11A.5.5 0 0 1 4 2z" /><path d="M6 8h4.5M6 10.5h3" /></svg>,
  search: <svg width="15" height="15" viewBox="0 0 16 16"><circle cx="7" cy="7" r="5" fill="none" stroke="currentColor" strokeWidth="1.6" /><path d="M11 11l3.5 3.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>,
  gear: <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></svg>,
  out: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M14 4h4a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-4" /><path d="M10 16l-4-4 4-4M6 12h10" /></svg>,
};

export function useBusy() {
  const [busy, setBusy] = useState(false);
  const run = async f => { if (busy) return; setBusy(true); try { return await f(); } finally { setBusy(false); } };
  return [busy, run];
}
export const fmt = n => (Number.isInteger(n) ? String(n) : (Math.round(n * 10) / 10).toString());
export const day = t => { const d = new Date(t * 1000); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
