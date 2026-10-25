import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api, go, enc } from '../api.js';
import { I, Logo, Popover, ThemeButtons, useToast, day } from '../parts/ui.jsx';
import Wizard from './Wizard.jsx';
import Settings from './Settings.jsx';

export const bname = b => b.title || `${b.cls || '未命名班级'} · ${b.exam || '未命名考试'}`;

export const ST = { draft: ['草稿', 'c-draft'], recognizing: ['识别中', 'c-check'], check: ['待核对', 'c-check'], generating: ['生成中', 'c-review'], review: ['待审核', 'c-review'], done: ['已完成', 'c-done'] };

/* 拖拽：报告拖到文件夹，文件夹拖动排序 */
const drag = { kind: null, id: null };
function dragStart(e, kind, id, label) {
  drag.kind = kind; drag.id = id; e.dataTransfer.effectAllowed = 'move';
  try { e.dataTransfer.setData('text/plain', label); } catch (_) {}
  const g = document.createElement('div'); g.className = 'dragghost'; g.textContent = (kind === 'folder' ? '📁 ' : '') + label;
  document.body.appendChild(g); e.dataTransfer.setDragImage(g, 14, 14); setTimeout(() => g.remove(), 0);
  document.body.classList.add('dragging', kind === 'folder' ? 'drag-folder' : 'drag-batch');
}
function dragEnd() { drag.kind = drag.id = null; document.body.classList.remove('dragging', 'drag-folder', 'drag-batch'); document.querySelectorAll('.over,.before,.after,.dragsrc').forEach(x => x.classList.remove('over', 'before', 'after', 'dragsrc')); }
if (typeof document !== 'undefined') document.addEventListener('dragend', dragEnd);

export default function Workspace({ me, setMe, refreshMe, route }) {
  const toast = useToast();
  const [folders, setFolders] = useState([]); const [batches, setBatches] = useState([]);
  const parts = route.split('/'); // ['', 'app', 'f'|'b'|'new', id]
  const view = parts[2] || 'all', arg = parts[3];
  const curFolder = view === 'f' ? arg : view === 'u' ? '' : 'all';
  const load = useCallback(() => Promise.all([api.get('/folders').then(setFolders), api.get('/batches').then(setBatches)]).catch(e => toast(e.message)), [toast]);
  useEffect(() => { load(); }, [load, route]);
  const moveBatch = async (id, fid) => {
    const b = batches.find(x => x.id === id); if (!b || (b.folder_id || '') === (fid || '')) return;
    await api.patch(`/batches/${id}`, { move: true, folder_id: fid || null }); await load();
    toast(`已移动到「${fid ? folders.find(f => f.id === fid)?.name : '未分类'}」`);
  };
  const logout = async () => { await api.post('/auth/logout').catch(() => {}); go('/'); setMe(null); };
  const inWizard = view === 'b' || view === 'new', inSet = view === 'settings';
  return <div className="app">
    <Rail me={me} folders={folders} batches={batches} curFolder={inWizard || inSet ? null : curFolder} curBatch={view === 'b' ? +arg : null} inSet={inSet}
      load={load} moveBatch={moveBatch} logout={logout} setFolders={setFolders} setBatches={setBatches} />
    <main>
      {inSet ? <Settings me={me} setMe={setMe} />
        : inWizard ? <Wizard key={view + (arg || '') + (parts[4] || '')} me={me} id={view === 'b' ? +arg : null} newFolder={view === 'new' ? (arg || '') : ''} folders={folders} reload={load} refreshMe={refreshMe} />
        : <List batches={batches} folders={folders} curFolder={curFolder} load={load} moveBatch={moveBatch} />}
    </main>
  </div>;
}

/* ---------------- 左侧栏：我的报告 + 文件夹树 ---------------- */
function Rail({ me, folders, batches, curFolder, curBatch, inSet, load, moveBatch, logout, setFolders, setBatches }) {
  const toast = useToast();
  const [open, setOpen] = useState(() => new Set());
  const [ren, setRen] = useState(null); const [menu, setMenu] = useState(null);
  const [kren, setKren] = useState(null); const [kmenu, setKmenu] = useState(null); const [umenu, setUmenu] = useState(null);
  // 打开某个报告时，自动展开它所在的文件夹并高亮
  const curFid = curBatch ? batches.find(b => b.id === curBatch)?.folder_id : null;
  useEffect(() => { if (curFid) setOpen(s => s.has(curFid) ? s : new Set(s).add(curFid)); }, [curFid]);
  useEffect(() => { if (curBatch) setTimeout(() => document.querySelector('.kid[aria-current="true"]')?.scrollIntoView({ block: 'nearest' }), 50); }, [curBatch, curFid]);
  const renameBatch = async (id, v) => { setKren(null); v = v.trim(); const b = batches.find(x => x.id === id); if (!b || !v || v === bname(b)) return; await api.patch(`/batches/${id}`, { title: v }); load(); };
  const reorderBatch = async (dragId, targetId, after) => {
    const t = batches.find(b => b.id === targetId), d = batches.find(b => b.id === dragId); if (!t || !d) return;
    const fid = t.folder_id || null;
    const ids = batches.filter(b => (b.folder_id || null) === fid && b.id !== dragId).map(b => b.id);
    let to = ids.indexOf(targetId); if (after) to++; ids.splice(to, 0, dragId);
    if ((d.folder_id || null) !== fid) await api.patch(`/batches/${dragId}`, { move: true, folder_id: fid });
    await api.post('/batches/order', { ids }); load();
  };
  const kidDrop = b => ({
    onDragOver: e => {
      if (drag.kind !== 'batch' || drag.id === b.id) return;
      e.preventDefault(); e.stopPropagation(); e.dataTransfer.dropEffect = 'move'; const t = e.currentTarget;
      document.querySelectorAll('.over,.before,.after').forEach(x => { if (x !== t) x.classList.remove('over', 'before', 'after'); });
      const r = t.getBoundingClientRect(), below = e.clientY > r.top + r.height / 2; t.classList.toggle('after', below); t.classList.toggle('before', !below);
    },
    onDragLeave: e => e.currentTarget.classList.remove('before', 'after'),
    onDrop: e => { e.preventDefault(); e.stopPropagation(); const after = e.currentTarget.classList.contains('after'), id = drag.id; dragEnd(); if (id && id !== b.id) reorderBatch(id, b.id, after); },
  });
  const kact = async (k, b, extra) => {
    if (k === 'ren') { setKmenu(null); setKren(b.id); }
    if (k === 'copy') { setKmenu(null); await api.post(`/batches/${b.id}/copy`); await load(); toast('已创建副本：沿用机构信息、试卷和课程大纲，换上新的成绩表和出门测即可'); }
    if (k === 'move') setKmenu({ ...kmenu, view: 'move' });
    if (k === 'back') setKmenu({ ...kmenu, view: 'main' });
    if (k === 'del') setKmenu({ ...kmenu, view: 'del' });
    if (k === 'del2') { setKmenu(null); await api.del(`/batches/${b.id}`); if (curBatch === b.id) go('/app'); await load(); toast('已删除'); }
    if (k === 'to') { setKmenu(null); moveBatch(b.id, extra); if (extra) setOpen(s => new Set(s).add(extra)); }
  };
  const cnt = f => batches.filter(b => f === 'all' || (f === '' ? !b.folder_id : b.folder_id === f)).length;
  const newFolder = async () => {
    let n = 1, name = '未命名文件夹'; while (folders.some(f => f.name === name)) name = `未命名文件夹 ${++n}`;
    const f = await api.post('/folders', { name }); await load(); setRen(f.id);
  };
  const rename = async (id, v) => { setRen(null); v = v.trim(); const f = folders.find(x => x.id === id); if (!v || !f || v === f.name) return; await api.patch(`/folders/${id}`, { name: v }); load(); };
  const del = async id => { const f = folders.find(x => x.id === id), n = cnt(id); setMenu(null); await api.del(`/folders/${id}`); if (curFolder == id) go('/app'); await load(); toast(`已删除文件夹「${f.name}」${n ? '，其中的报告已移到「未分类」' : ''}`); };
  const reorder = async (dragId, targetId, after) => {
    const ids = folders.map(f => f.id).filter(i => i !== dragId); let to = ids.indexOf(targetId); if (after) to++; ids.splice(to, 0, dragId);
    setFolders(ids.map(i => folders.find(f => f.id === i))); await api.post('/folders/order', { ids }); load();
  };
  const dropProps = fid => ({
    'data-drop': 1,
    onDragOver: e => {
      if (!drag.kind) return; if (drag.kind === 'folder' && (fid === '' || fid === drag.id)) return;
      e.preventDefault(); e.dataTransfer.dropEffect = 'move'; const t = e.currentTarget;
      document.querySelectorAll('.over,.before,.after').forEach(x => { if (x !== t) x.classList.remove('over', 'before', 'after'); });
      if (drag.kind === 'folder') { const r = t.getBoundingClientRect(), below = e.clientY > r.top + r.height / 2; t.classList.toggle('after', below); t.classList.toggle('before', !below); } else t.classList.add('over');
    },
    onDragLeave: e => { if (!e.currentTarget.contains(e.relatedTarget)) e.currentTarget.classList.remove('over', 'before', 'after'); },
    onDrop: e => { e.preventDefault(); const after = e.currentTarget.classList.contains('after'); const k = drag.kind, id = drag.id; dragEnd();
      if (k === 'batch') { moveBatch(id, fid || null); if (fid) setOpen(s => new Set(s).add(fid)); }
      if (k === 'folder' && fid && fid !== id) reorder(id, fid, after); },
  });
  const usedPct = Math.min(100, me.used / me.quota * 100);
  return <aside className="rail">
    <div className="brand"><Logo /><b>学情报告助手</b></div>
    <button className="btn pri block" onClick={() => go('/app/new')}>{I.plus}新建报告</button>
    <nav className="nav" aria-label="我的报告">
      <div className="lab">我的报告</div>
      {[['all', '全部报告', '/app'], ['', '未分类', '/app/u']].map(([k, n, href]) =>
        <div key={n} className="ni frow" role="button" tabIndex={0} aria-current={curFolder === k} {...(k === '' ? dropProps('') : {})}
          onClick={() => go(href)} onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), go(href))}>
          <span className="car-s" />{I.all}<span className="nm">{n}</span><span className="ct">{cnt(k)}</span></div>)}
      <div className="lab">文件夹 <button onClick={newFolder} aria-label="新建文件夹" title="新建文件夹">{I.plus}</button></div>
      {folders.map(f => {
        const kids = batches.filter(b => b.folder_id === f.id), isOpen = open.has(f.id);
        return <div key={f.id} className={'fi' + (isOpen ? ' open' : '')}>
          <div className="ni frow" role="button" tabIndex={0} aria-current={curFolder == f.id} aria-expanded={isOpen} draggable={ren !== f.id}
            onDragStart={e => dragStart(e, 'folder', f.id, f.name)} {...dropProps(f.id)}
            onClick={e => { if (e.target.closest('button,input')) return; go('/app/f/' + f.id); }}
            onKeyDown={e => { if (e.target !== e.currentTarget) return; if (e.key === 'Enter') go('/app/f/' + f.id); if (e.key === 'F2') setRen(f.id); }}>
            <button className="car" aria-label={(isOpen ? '收起' : '展开') + f.name} onClick={e => { e.stopPropagation(); setOpen(s => { const n = new Set(s); n.has(f.id) ? n.delete(f.id) : n.add(f.id); return n; }); }}>{I.car}</button>
            {I.folder}
            {ren === f.id ? <RenameInput value={f.name} onDone={v => rename(f.id, v)} onCancel={() => setRen(null)} /> : <span className="nm" title={f.name}>{f.name}</span>}
            <span className="ct">{kids.length}</span>
            <span className="fa">
              <button aria-label={`在「${f.name}」里新建报告`} title="新建报告" onClick={e => { e.stopPropagation(); go('/app/new/' + f.id); }}>{I.plus}</button>
              <button aria-label="文件夹操作" aria-haspopup="menu" aria-expanded={menu?.id === f.id} title="更多" onClick={e => { e.stopPropagation(); setMenu(menu?.id === f.id ? null : { id: f.id, el: e.currentTarget, view: 'main' }); }}>{I.dots}</button>
            </span>
          </div>
          <div className="kids">{kids.length ? kids.map(b => <div key={b.id} className="ni kid frow" role="button" tabIndex={0} draggable={kren !== b.id} title={bname(b)}
            aria-current={curBatch === b.id} {...kidDrop(b)}
            onDragStart={e => { e.stopPropagation(); e.currentTarget.classList.add('dragsrc'); dragStart(e, 'batch', b.id, bname(b)); }}
            onClick={e => { if (e.target.closest('button,input')) return; go('/app/b/' + b.id); }}
            onKeyDown={e => { if (e.target !== e.currentTarget) return; if (e.key === 'Enter') go('/app/b/' + b.id); if (e.key === 'F2') setKren(b.id); }}>
            {I.doc}{kren === b.id ? <RenameInput value={bname(b)} label="报告名称" max={40} onDone={v => renameBatch(b.id, v)} onCancel={() => setKren(null)} /> : <span className="nm">{bname(b)}</span>}
            <span className="fa"><button aria-label="报告操作" aria-haspopup="menu" aria-expanded={kmenu?.id === b.id} title="更多"
              onClick={e => { e.stopPropagation(); setKmenu(kmenu?.id === b.id ? null : { id: b.id, el: e.currentTarget, view: 'main' }); }}>{I.dots}</button></span>
          </div>) : <div className="kid-empty">空文件夹，把报告拖到这里</div>}</div>
        </div>;
      })}
    </nav>
    {menu && (() => { const f = folders.find(x => x.id === menu.id); if (!f) return null; const n = cnt(f.id); return <Popover anchor={menu.el} align="left" onClose={() => setMenu(null)}>
      {menu.view === 'main' ? <>
        <button role="menuitem" onClick={() => { setMenu(null); go('/app/new/' + f.id); }}>{I.plus}在此新建报告</button>
        <button role="menuitem" onClick={() => { setMenu(null); setRen(f.id); }}>{I.pen}重命名</button><hr />
        <button role="menuitem" className="danger" onClick={() => setMenu({ ...menu, view: 'del' })}>{I.del}删除文件夹</button></> : <>
        <div className="mh">{I.del}删除文件夹「{f.name}」？</div>
        <div className="warn">{n ? `里面的 ${n} 个报告批次会移到「未分类」，报告本身不会被删除。` : '这是一个空文件夹。'}</div>
        <div className="row2"><button className="btn sm" onClick={() => setMenu(null)}>取消</button><button className="btn sm danger solid" onClick={() => del(f.id)}>删除</button></div></>}
    </Popover>; })()}
    {kmenu && (() => { const b = batches.find(x => x.id === kmenu.id); if (!b) return null; return <Popover anchor={kmenu.el} align="left" onClose={() => setKmenu(null)}>
      {kmenu.view === 'main' && <>
        <button role="menuitem" onClick={() => { setKmenu(null); go('/app/b/' + b.id); }}>{I.open}打开</button>
        <button role="menuitem" onClick={() => kact('ren', b)}>{I.pen}重命名</button>
        <button role="menuitem" onClick={() => kact('copy', b)}>{I.copy}创建副本</button>
        <button role="menuitem" onClick={() => kact('move', b)}>{I.folder}移动到{I.chev}</button><hr />
        <button role="menuitem" className="danger" onClick={() => kact('del', b)}>{I.del}删除</button></>}
      {kmenu.view === 'move' && <>
        <button role="menuitem" onClick={() => kact('back', b)}>{I.back}移动到</button><hr />
        {[[null, '未分类'], ...folders.map(f => [f.id, f.name])].map(([fid, n]) => <button key={n + fid} role="menuitemradio" aria-checked={(b.folder_id || null) === fid} onClick={() => kact('to', b, fid)}>{I.folder}{n}</button>)}</>}
      {kmenu.view === 'del' && <>
        <div className="mh">{I.del}删除这个报告批次？</div>
        <div className="warn">「{bname(b)}」{b.n ? `和其中 ${b.n} 份报告` : ''}会一起删除，不可恢复。</div>
        <div className="row2"><button className="btn sm" onClick={() => setKmenu(null)}>取消</button><button className="btn sm danger solid" onClick={() => kact('del2', b)}>删除</button></div></>}
    </Popover>; })()}
    <div className="mecard">
      <button className="me mebtn" aria-haspopup="menu" aria-expanded={!!umenu} onClick={e => setUmenu(umenu ? null : e.currentTarget)} title="账号与设置">
        <span className="av">{(me.name || me.username)[0]}</span><div className="who"><b>{me.name}</b><small>本月 {me.used} / {me.quota} 批次</small><i className="usage" aria-hidden="true"><u style={{ width: usedPct + '%' }} /></i></div></button>
      <div className="mebar"><ThemeButtons />
        <button className="ibtn out" aria-current={inSet} onClick={() => go('/app/settings')} aria-label="设置" title="设置">{I.gear}</button>
        <button className="ibtn" onClick={logout} aria-label="退出登录" title="退出登录">{I.out}</button></div>
    </div>
    {umenu && <Popover anchor={umenu} align="left" onClose={() => setUmenu(null)}>
      <div className="mh">{me.name}<small>账号：{me.username}{me.admin ? ' · 管理员' : ''}</small></div><hr />
      <button role="menuitem" onClick={() => { setUmenu(null); go('/app/settings'); }}>{I.gear}设置</button>
      <button role="menuitem" onClick={() => { setUmenu(null); logout(); }}>{I.out}退出登录</button>
    </Popover>}
  </aside>;
}

function RenameInput({ value, onDone, onCancel, label = '文件夹名称', max = 20 }) {
  const ref = useRef(); const done = useRef(false);
  useEffect(() => { ref.current.focus(); ref.current.select(); }, []);
  const fin = v => { if (done.current) return; done.current = true; v === null ? onCancel() : onDone(v); };
  return <input ref={ref} className="ren" defaultValue={value} maxLength={max} aria-label={label}
    onClick={e => e.stopPropagation()} onKeyDown={e => { e.stopPropagation(); if (e.key === 'Enter') fin(e.target.value); if (e.key === 'Escape') fin(null); }} onBlur={e => fin(e.target.value)} />;
}

/* ---------------- 报告列表 ---------------- */
function List({ batches, folders, curFolder, load, moveBatch }) {
  const toast = useToast(); const [q, setQ] = useState(''); const [menu, setMenu] = useState(null);
  const title = curFolder === 'all' ? '全部报告' : curFolder === '' ? '未分类' : (folders.find(f => f.id == curFolder) || {}).name || '文件夹';
  const rows = batches.filter(b => (curFolder === 'all' || (curFolder === '' ? !b.folder_id : b.folder_id == curFolder)) && (!q || bname(b).includes(q) || b.cls.includes(q) || b.exam.includes(q) || b.names.some(n => n.includes(q))));
  const act = async (k, b, extra) => {
    if (k === 'open') { setMenu(null); go('/app/b/' + b.id); }
    if (k === 'copy') { setMenu(null); await api.post(`/batches/${b.id}/copy`); await load(); toast('已创建副本：沿用机构信息、试卷和课程大纲，换上新的成绩表和出门测即可'); }
    if (k === 'move') setMenu({ ...menu, view: 'move' });
    if (k === 'back') setMenu({ ...menu, view: 'main' });
    if (k === 'del') setMenu({ ...menu, view: 'del' });
    if (k === 'del2') { setMenu(null); await api.del(`/batches/${b.id}`); await load(); toast('已删除'); }
    if (k === 'to') { setMenu(null); moveBatch(b.id, extra); }
  };
  const mb = menu && batches.find(x => x.id === menu.id);
  return <section className="wrap">
    <div className="ph"><div><h1>{title}</h1><p>{q ? `搜索“${q}”找到 ${rows.length} 个批次` : '一个班的一次考试是一个报告批次。可以把报告拖到左边的文件夹里'}</p></div>
      <label className="search">{I.search}<input value={q} onChange={e => setQ(e.target.value.trim())} placeholder="搜索班级、考试或学生姓名" aria-label="搜索" /></label></div>
    <div className="card tw"><table className="list"><colgroup><col className="c-n" /><col className="c-s" /><col className="c-st" /><col className="c-a" /></colgroup>
      <thead><tr><th>报告批次</th><th>学生</th><th>状态</th><th style={{ textAlign: 'right' }}>操作</th></tr></thead>
      <tbody>{rows.map(b => { const full = bname(b), hit = q && b.names.find(n => n.includes(q)); return <tr key={b.id} draggable
        onDragStart={e => { e.currentTarget.classList.add('dragsrc'); dragStart(e, 'batch', b.id, full); }} onClick={e => { if (e.target.closest('button,a')) return; go('/app/b/' + b.id); }}>
        <td><div className="bn"><b title={full}>{full}</b><small>{hit ? `包含学生 ${hit} · ` : ''}{day(b.created)} 创建</small></div></td>
        <td className="nw">{b.n ? `${b.n} 人` : '—'}</td>
        <td><span className={'chip ' + ST[b.status][1]}>{ST[b.status][0]}</span></td>
        <td><div className="acts">
          {['review', 'done'].includes(b.status) ? <a className="btn ghost sm" href={`/api/batches/${b.id}/zip`}>下载</a> : <button className="btn ghost sm" disabled style={{ opacity: .4 }}>下载</button>}
          <button className="more" aria-label="更多操作" aria-haspopup="menu" aria-expanded={menu?.id === b.id} title="更多" onClick={e => { e.stopPropagation(); setMenu(menu?.id === b.id ? null : { id: b.id, el: e.currentTarget, view: 'main' }); }}>{I.dots}</button>
        </div></td></tr>; })}</tbody></table>
      {!rows.length && <div className="empty">{batches.length ? '没有找到报告。换个关键词试试，或者点左上角「新建报告」。' : '还没有报告。点左上角「新建报告」，上传三份材料就能生成。'}</div>}
    </div>
    {mb && <Popover anchor={menu.el} onClose={() => setMenu(null)}>
      {menu.view === 'main' && <>
        <button role="menuitem" onClick={() => act('open', mb)}>{I.open}打开</button>
        {['review', 'done'].includes(mb.status) ? <a role="menuitem" className="mi" href={`/api/batches/${mb.id}/zip`} onClick={() => setMenu(null)}>{I.dl}下载全班 zip</a> : <button role="menuitem" disabled>{I.dl}下载全班 zip</button>}<hr />
        <button role="menuitem" onClick={() => act('copy', mb)}>{I.copy}创建副本</button>
        <button role="menuitem" onClick={() => act('move', mb)}>{I.folder}移动到{I.chev}</button><hr />
        <button role="menuitem" className="danger" onClick={() => act('del', mb)}>{I.del}删除</button></>}
      {menu.view === 'move' && <>
        <button role="menuitem" onClick={() => act('back', mb)}>{I.back}移动到</button><hr />
        {[[null, '未分类'], ...folders.map(f => [f.id, f.name])].map(([fid, n]) => <button key={n + fid} role="menuitemradio" aria-checked={(mb.folder_id || null) === fid} onClick={() => act('to', mb, fid)}>{I.folder}{n}</button>)}</>}
      {menu.view === 'del' && <>
        <div className="mh">{I.del}删除这个报告批次？</div>
        <div className="warn">「{bname(mb)}」{mb.n ? `和其中 ${mb.n} 份报告` : ''}会一起删除，不可恢复。</div>
        <div className="row2"><button className="btn sm" onClick={() => setMenu(null)}>取消</button><button className="btn sm danger solid" onClick={() => act('del2', mb)}>删除</button></div></>}
    </Popover>}
  </section>;
}
