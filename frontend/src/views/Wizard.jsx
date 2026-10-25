import React, { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { api, go, enc } from '../api.js';
import { I, useToast, useBusy, fmt } from '../parts/ui.jsx';
import { burst } from '../fx/effects.js';

const STEPS = ['填写信息', '上传材料', '核对识别结果', '预览与修改', '下载'];
const UPS = [
  { k: 'paper', t: '考试试卷', req: true, d: '整张原卷，系统识别题号、分值、知识点和答案' },
  { k: 'grade', t: '逐题成绩表', req: true, d: '全班每位学生每道小题的得分', tpl: true },
  { k: 'exit', t: '出门测记录表', req: true, d: '每讲课尾测验，每个知识点的对错', tpl: true },
  { k: 'plan', t: '续报课程大纲', req: false, d: '下一阶段的课程安排；不传则报告不含课程规划' },
];
const ACCEPT = '.jpg,.jpeg,.png,.webp,.heic,.pdf,.docx,.xlsx,.csv';
const ext = n => (n.split('.').pop() || '').toUpperCase().slice(0, 4);
const size = s => s > 1048576 ? (s / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(s / 1024)) + ' KB';
const stepOf = b => !b ? 1 : b.status === 'draft' || b.status === 'recognizing' ? 2 : b.status === 'check' || b.status === 'generating' ? 3 : b.status === 'review' ? 4 : 5;

export default function Wizard({ me, id, newFolder, folders, reload, refreshMe }) {
  const toast = useToast();
  const [b, setB] = useState(null); const [step, setStep] = useState(id ? 0 : 1);
  const pf = me.prefs || {};
  const [meta, setMeta] = useState({ org: pf.org || '', campus: pf.campus || '', teacher: pf.teacher || me.name || '', cls: '', exam: '' });
  const [busy, run] = useBusy();
  const load = useCallback(async (keepStep) => {
    const d = await api.get('/batches/' + id); setB(d); setMeta(m => ({ ...m, ...d.meta }));
    if (!keepStep) setStep(stepOf(d));
    return d;
  }, [id]);
  useEffect(() => { if (id) load().catch(e => { toast(e.message); go('/app'); }); }, [id, load, toast]);
  // 识别中 / 生成中：每秒刷新进度
  useEffect(() => {
    if (!b || !['recognizing', 'generating'].includes(b.status)) return;
    const t = setInterval(async () => {
      const d = await api.get('/batches/' + id).catch(() => null); if (!d) return;
      setB(d); setMeta(m => ({ ...m, ...d.meta }));
      if (d.status !== b.status) {
        if (b.status === 'recognizing') { if (d.status === 'check') { setStep(3); toast(d.issues?.some(x => !x.done) ? '识别完成，请核对标出来的地方' : '识别完成，没有发现问题'); } else toast(d.error || '识别失败'); }
        if (b.status === 'generating') { if (d.status === 'review') { setStep(4); refreshMe(); reload(); toast('报告已生成，可以逐份预览和修改'); } else toast(d.error || '生成失败'); }
      }
    }, 1000);
    return () => clearInterval(t);
  }, [b, id, toast, refreshMe, reload]);

  const title = b ? (b.title || `${b.meta.cls || '未命名班级'} · ${b.meta.exam || '未命名考试'}`) : '新建报告';
  const saveMeta = async () => {
    if (!meta.teacher.trim()) { toast('请填写授课老师'); document.getElementById('fTeacher')?.focus(); return false; }
    if (!b) { const d = await api.post('/batches', { ...meta, folder_id: newFolder ? +newFolder : null }); reload(); go('/app/b/' + d.id); return false; }
    const d = await api.patch('/batches/' + b.id, meta); setB(d); return true;
  };
  const reds = (b?.issues || []).filter(x => x.lv === 'r' && !x.done).length;
  const files = b?.files || [];
  const miss = UPS.filter(u => u.req && !files.some(f => f.kind === u.k)).map(u => u.t);
  const st = step || stepOf(b);
  const recognizing = b?.status === 'recognizing', generating = b?.status === 'generating';

  let hint = '', next = null;
  if (st === 1) { hint = '带 * 的为必填。班级和考试名称可以留空，上传成绩表后自动识别。'; next = ['下一步：上传材料', () => run(async () => { if (await saveMeta()) setStep(2); })]; }
  if (st === 2 && !recognizing) { hint = miss.length ? `还差：${miss.join('、')}` : '三份必填材料已齐，续报课程大纲可以不传'; next = ['开始识别', () => run(async () => { const d = await api.post(`/batches/${b.id}/recognize`).catch(e => toast(e.message)); d && setB(d); }), miss.length > 0]; }
  if (st === 3 && !generating) { hint = reds ? <>还有 <b>{reds}</b> 个红色问题需要处理，处理完才能生成报告</> : '红色问题已全部处理，黄色提示可以忽略。'; next = ['生成报告', () => run(async () => { const d = await api.post(`/batches/${b.id}/generate`).catch(e => toast(e.message)); d && setB(d); }), reds > 0]; }
  if (st === 4) { const n = b.report?.students.length || 0; hint = `已确认 ${b.confirmed.length} / ${n} 份。不必逐份确认，也可以直接下载。`; next = ['完成，去下载', () => run(async () => { setB(await api.post(`/batches/${b.id}/finish`)); setStep(5); reload(); })]; }
  if (st === 5) { hint = '报告已保存在「我的报告」，以后可以随时打开、修改、重新下载。'; next = ['回到我的报告', () => go('/app')]; }
  const canBack = st > 1 && !recognizing && !generating && b;

  return <section className="wrap">
    <div className="ph"><div><h1>{title}</h1><p>按顺序完成 5 步，随时可以退出，下次从「我的报告」接着做</p></div><button className="btn ghost" onClick={() => go('/app')}>返回我的报告</button></div>
    <div className="steps">{STEPS.map((s, i) => <div key={s} className={'st ' + (i + 1 < st ? 'ok' : i + 1 === st ? 'on' : '')}><div className="bar" /><div className="tx"><i>{i + 1 < st ? '✓' : i + 1}</i><span>{s}</span></div></div>)}</div>
    {b?.data?.notes?.length > 0 && st >= 3 && <div className="notice">{b.data.notes.map(n => <p key={n}>{n}</p>)}</div>}
    {st === 1 && <Step1 meta={meta} setMeta={setMeta} isNew={!b} />}
    {st === 2 && b && (recognizing || b.progress?.steps ? (recognizing ? <Rec b={b} /> : <Upload b={b} setB={setB} />) : <Upload b={b} setB={setB} />)}
    {st === 2 && b && !recognizing && b.error && b.progress?.error && <div className="notice bad"><b>上次识别没有成功：</b>{b.error}</div>}
    {st === 3 && b && (generating ? <Gen b={b} /> : <Check b={b} setB={setB} />)}
    {st === 3 && b && !generating && b.error && b.progress?.phase && <div className="notice bad"><b>上次生成没有成功：</b>{b.error}</div>}
    {st === 4 && b?.report && <Preview b={b} setB={setB} />}
    {st === 5 && b?.report && <Done b={b} setB={setB} folders={folders} reload={reload} />}
    <div className="abar"><div className="in"><span className="hint">{hint}</span>
      {canBack && <button className="btn" onClick={() => setStep(st - 1)}>上一步</button>}
      {next && <button className={'btn pri' + (busy ? ' busy' : '')} onClick={next[1]} disabled={busy || next[2]}>{next[0]}</button>}</div></div>
  </section>;
}

/* ---------------- 第 1 步：填写信息 ---------------- */
function Step1({ meta, setMeta, isNew }) {
  const set = k => e => setMeta({ ...meta, [k]: e.target.value });
  return <div className="card">
    {isNew && <p className="prefhint">机构、校区和授课老师已按你的默认信息填好，可以直接修改。<a href="#/app/settings">修改默认信息</a></p>}
    <div className="form">
    <div className="f"><label htmlFor="fOrg">机构名称<span>选填，显示在报告抬头</span></label><input id="fOrg" value={meta.org} onChange={set('org')} maxLength={40} /></div>
    <div className="f"><label htmlFor="fCampus">校区<span>选填</span></label><input id="fCampus" value={meta.campus} onChange={set('campus')} maxLength={40} /></div>
    <div className="f"><label htmlFor="fTeacher">授课老师<em>*</em></label><input id="fTeacher" value={meta.teacher} onChange={set('teacher')} maxLength={40} /><small>用于报告抬头和寄语署名</small></div>
    <div className="f"><label htmlFor="fClass">班级名称</label><input id="fClass" value={meta.cls} onChange={set('cls')} placeholder="上传成绩表后自动识别" maxLength={40} /><small className="auto">上传成绩表后会从表头自动识别，可修改</small></div>
    <div className="f"><label htmlFor="fExam">考试名称</label><input id="fExam" value={meta.exam} onChange={set('exam')} placeholder="上传成绩表后自动识别" maxLength={40} /><small className="auto">同样自动识别，如「26秋 期中测试」</small></div>
    <div className="f"><label>学科</label><input value="数学" disabled /><small>第一版只支持数学</small></div>
  </div></div>;
}

/* ---------------- 第 2 步：上传材料 ---------------- */
function Upload({ b, setB }) {
  const toast = useToast(); const [over, setOver] = useState(null); const [up, setUp] = useState(null);
  const add = async (k, list) => {
    const fl = [...list]; if (!fl.length) return;
    const big = fl.find(f => f.size > 20 * 1048576); if (big) { toast(`${big.name} 超过 20 MB，请压缩后再传`); return; }
    const fd = new FormData(); fd.append('kind', k); fl.forEach(f => fd.append('files', f));
    setUp(k);
    try { await api.upload(`/batches/${b.id}/files`, fd); setB(await api.get('/batches/' + b.id)); } catch (e) { toast(e.message); } finally { setUp(null); }
  };
  const rm = async f => { await api.del(`/batches/${b.id}/files/${f.id}`); setB(await api.get('/batches/' + b.id)); };
  return <div>
    <div className="ups">{UPS.map(u => { const fs = b.files.filter(f => f.kind === u.k); return <div key={u.k} className="card up">
      <div className="uh"><div><h2>{u.t}</h2><p>{u.d}</p></div><div className="uht">{u.tpl && <a className="btn ghost sm tpl" href={`/api/templates/${u.k}`}>{I.dl}下载模板</a>}<span className={'tag ' + (u.req ? 'req' : 'opt')}>{u.req ? '必填' : '选填'}</span></div></div>
      <div className="files">{fs.map(f => <div key={f.id} className="file"><span className="ext">{ext(f.name)}</span><span className="nm">{f.name}</span><small>{size(f.size)}</small><button onClick={() => rm(f)} aria-label={'移除 ' + f.name}>✕</button></div>)}</div>
      <label className={'drop' + (over === u.k ? ' over' : '')} onDragOver={e => { e.preventDefault(); setOver(u.k); }} onDragLeave={() => setOver(null)} onDrop={e => { e.preventDefault(); setOver(null); add(u.k, Array.from(e.dataTransfer.files || [])); }}>
        {up === u.k ? '正在上传…' : '点击选择或拖入文件'}<br /><small>图片 · PDF · Word · Excel，可多选</small>
        <input type="file" multiple hidden accept={ACCEPT} onChange={e => { const fs = Array.from(e.target.files || []); e.target.value = ''; add(u.k, fs); }} /></label>
    </div>; })}</div>
    <p className="fmt">每类材料都支持图片、PDF、Word、Excel，单个文件不超过 20 MB。成绩表和出门测表用 Excel 最准确，卡片右上角可以下载模板。试卷也可以上传「题号 | 题型 | 分值 | 知识点 | 讲次」格式的题目表。</p>
  </div>;
}

/* 识别中 / 生成中的展示面板（丝绸背景） */
function Rec({ b }) {
  const p = b.progress || {};
  return <div className="rec fxzone" data-silk="rec"><canvas className="silk" id="silkRec" aria-hidden="true" />
    <div className="rin"><h2>正在识别材料</h2><p>系统正在读你上传的文件，随后会逐项校验，有问题的地方会标给你。</p>
      <ol className="msl">{(p.steps || []).map(s => <li key={s.key} className={s.state === 'on' ? 'on' : s.state === 'ok' ? 'ok' : ''}><span className="dot" /><div><b>{s.label}</b><small>{s.summary}</small></div></li>)}</ol>
      <div className="log" aria-live="polite">{(p.log || []).map((l, i) => <div key={i}>{l}</div>)}</div></div></div>;
}
function Gen({ b }) {
  const p = b.progress || {}; const writing = p.phase === 'writing';
  return <div className="rec fxzone" data-silk="rec"><canvas className="silk" id="silkRec" aria-hidden="true" />
    <div className="rin"><h2>正在生成报告</h2><p>数字按规则计算，文字由系统起草，再逐份排版成三页 PDF。一个班大约需要一两分钟。</p>
      <ol className="msl">
        <li className={writing ? 'on' : 'ok'}><span className="dot" /><div><b>计算并撰写报告文字</b><small>{writing ? '进行中…' : '已完成'}</small></div></li>
        <li className={p.phase === 'rendering' ? 'on' : p.phase === 'done' ? 'ok' : ''}><span className="dot" /><div><b>排版生成 PDF</b><small>{p.total ? `${p.done} / ${p.total} 份` : '等待中'}</small></div></li>
      </ol>
      <div className="log" aria-live="polite">{(p.log || []).map((l, i) => <div key={i}>{l}</div>)}</div></div></div>;
}

/* ---------------- 第 3 步：核对识别结果 ---------------- */
function Check({ b, setB }) {
  const toast = useToast(); const d = b.data; const [tab, setTab] = useState('grade');
  const save = async body => { try { setB(await api.put(`/batches/${b.id}/data`, body)); } catch (e) { toast(e.message); } };
  const iss = b.issues || []; const reds = iss.filter(x => x.lv === 'r' && !x.done).length, yel = iss.filter(x => x.lv === 'y' && !x.done).length;
  const tot = n => d.scores[n].reduce((a, v) => a + (+v || 0), 0);
  const avg = d.students.length ? d.students.reduce((a, n) => a + tot(n), 0) / d.students.length : 0;
  const full = d.items.reduce((a, i) => a + (i.full || 0), 0);
  const redCell = new Set(iss.filter(x => !x.done && x.stu && x.col != null).map(x => `${x.stu}:${x.col}:${x.lv}`));
  const locate = x => {
    setTab(x.tab || 'grade');
    setTimeout(() => {
      const cell = document.getElementById(x.tab === 'q' ? `q${x.col}` : `g${d.students.indexOf(x.stu)}_${x.col}`);
      if (cell) { cell.scrollIntoView({ block: 'center', inline: 'center', behavior: 'smooth' }); cell.classList.remove('flash'); void cell.offsetWidth; cell.classList.add('flash'); const inp = cell.querySelector('input,select'); inp && setTimeout(() => inp.focus({ preventScroll: true }), 400); }
    }, 60);
  };
  return <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
    <div className="sumbar">{reds ? <span className="pill r">{reds} 个必须处理</span> : <span className="pill g">必须处理的问题已清空</span>}{yel > 0 && <span className="pill y">{yel} 个提示</span>}
      <span className="fmt">{d.students.length} 名学生 · {d.items.length} 个得分点 · 满分 {fmt(full)} · 班均 {fmt(Math.round(avg * 10) / 10)}</span></div>
    <div className="chk">
      <div className="card" style={{ minWidth: 0 }}>
        <div className="tabs" role="tablist">{[['grade', '成绩表'], ['q', '题目表'], ['exit', '出门测']].map(([k, n]) => { const c = iss.filter(x => x.lv === 'r' && !x.done && (x.tab || 'grade') === k).length; return <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>{n}{c > 0 && <span className="n">{c}</span>}</button>; })}</div>
        {tab === 'grade' && <div className="gw"><table className="grid"><thead><tr><th className="sn">学生</th>{d.items.map(i => <th key={i.id}>{i.id}<small>{i.full == null ? '?' : fmt(i.full)}分</small></th>)}<th>系统合计</th><th>表中总分</th></tr></thead>
          <tbody>{d.students.map((n, r) => { const t = tot(n), off = d.official[n]; return <tr key={n}><td className="sn">{n}</td>
            {d.scores[n].map((v, c) => <td key={c} id={`g${r}_${c}`} className={redCell.has(`${n}:${c}:r`) ? 'red' : redCell.has(`${n}:${c}:y`) ? 'yel' : ''}>
              <input defaultValue={v} key={`${v}`} aria-label={`${n} 第${d.items[c].id}题`} inputMode="decimal" onBlur={e => {
                const nv = parseFloat(e.target.value); if (isNaN(nv) || nv < 0) { e.target.value = v; if (e.target.value !== String(v)) toast('请输入 0 或正数'); return; }
                if (nv === v) return; const s = [...d.scores[n]]; s[c] = nv; save({ scores: { [n]: s } }); }} onKeyDown={e => e.key === 'Enter' && e.target.blur()} /></td>)}
            <td className={'tot' + (off != null && Math.abs(t - off) > 1e-6 ? ' bad' : '')}>{fmt(t)}</td><td className="tot" style={{ fontWeight: 400 }}>{off == null ? '—' : fmt(off)}</td></tr>; })}</tbody></table></div>}
        {tab === 'q' && <div className="gw"><table className="qt" style={{ width: '100%' }}><thead><tr><th>题号</th><th>题型</th><th>分值</th><th>考察知识点</th><th>所属讲次</th></tr></thead>
          <tbody>{d.items.map((i, x) => <tr key={i.id} id={`q${x}`}><td><b>{i.id}</b></td>
            <td><select value={i.type} onChange={e => save({ items: d.items.map((it, k) => k === x ? { ...it, type: e.target.value } : it) })} aria-label={`第${i.id}题题型`}>{['选择', '判断', '填空', '计算', '解答'].concat(['选择', '判断', '填空', '计算', '解答'].includes(i.type) ? [] : [i.type]).map(t => <option key={t}>{t}</option>)}</select></td>
            <td className="c"><input className={'qin' + (i.full == null ? ' bad' : '')} defaultValue={i.full ?? ''} key={`${i.full}`} inputMode="decimal" aria-label={`第${i.id}题分值`} onBlur={e => { const v = parseFloat(e.target.value); if (isNaN(v) || v <= 0 || v === i.full) return; save({ items: d.items.map((it, k) => k === x ? { ...it, full: v } : it) }); }} /></td>
            <td><input className="qin wide" defaultValue={i.kp} key={i.kp} maxLength={40} aria-label={`第${i.id}题知识点`} onBlur={e => { const v = e.target.value.trim(); if (v === i.kp) return; save({ items: d.items.map((it, k) => k === x ? { ...it, kp: v } : it) }); }} /></td>
            <td><select value={i.lect ?? ''} className={i.lect == null ? 'bad' : ''} onChange={e => save({ items: d.items.map((it, k) => k === x ? { ...it, lect: e.target.value === '' ? null : +e.target.value } : it) })} aria-label={`第${i.id}题所属讲次`}>
              {i.lect == null && <option value="">请选择</option>}{d.lectures.map((l, j) => <option key={j} value={j}>{l.no} {l.name}</option>)}</select></td></tr>)}</tbody></table></div>}
        {tab === 'exit' && <div className="gw"><table className="ex" style={{ width: '100%' }}><thead><tr><th>学生</th>{d.lectures.map(l => <th key={l.no}>{l.no}<br /><span style={{ fontWeight: 400 }}>{l.name}</span></th>)}</tr></thead>
          <tbody>{d.students.map(n => { const m = d.exit[n]; return <tr key={n}><td><b>{n}</b></td>{d.lectures.map((l, li) => { const row = m ? m[li] : l.kps.map(() => 0); return <td key={li}><span className="dots">{row.map((v, j) =>
            <button key={j} className={v ? 'y' : 'n'} title={`${l.kps[j]}：${v ? '答对' : '答错'}（点击切换）`} aria-label={`${n} ${l.no} ${l.kps[j]} ${v ? '答对' : '答错'}`} onClick={() => { const mm = (m || d.lectures.map(L => L.kps.map(() => 0))).map(r => [...r]); mm[li][j] = v ? 0 : 1; save({ exit: { [n]: mm } }); }} />)}</span> <small style={{ color: 'var(--muted)' }}>{row.filter(Boolean).length}/{row.length}</small></td>; })}</tr>; })}</tbody></table>
          <p className="fmt" style={{ padding: '10px 14px', margin: 0 }}>绿点为答对，红圈为答错，点圆点可以切换。</p></div>}
      </div>
      <div className="card iss"><h2>需要你确认的地方</h2><div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: 4 }}>
        {!iss.length && <div className="is ok"><span className="lv">没有问题</span><b>识别结果全部通过校验</b></div>}
        {iss.map(x => <div key={x.id} className={'is ' + (x.done ? 'ok' : x.lv)}><span className="lv">{x.done ? '已处理' : x.lv === 'r' ? '必须处理' : '提示'}</span><b>{x.title}</b>{x.desc && !x.done && <p>{x.desc}</p>}
          {x.done ? (x.how && <span className="st2">{x.how}</span>) : <div className="row">{(x.col != null || x.stu) && <button className="btn sm" onClick={() => locate(x)}>定位</button>}
            {x.actions.map(a => <button key={a.key} className={'btn sm' + (a.primary ? ' pri' : '')} onClick={() => save({ action: { issue: x.id, key: a.key } })}>{a.label}</button>)}</div>}</div>)}
      </div></div>
    </div>
  </div>;
}

/* ---------------- 第 4 步：预览与修改 ---------------- */
function Preview({ b, setB }) {
  const toast = useToast(); const R = b.report; const [cur, setCur] = useState(0); const [busy, run] = useBusy();
  const s = R.students[cur]; const [h, setH] = useState(s.headline); const [m, setM] = useState(s.message);
  useEffect(() => { setH(s.headline); setM(s.message); }, [cur, s.headline, s.message]);
  const dirty = h !== s.headline || m !== s.message;
  const saveText = async () => { const d = await api.put(`/batches/${b.id}/students/${enc(s.name)}`, { headline: h, message: m }); setB(d); return d; };
  return <div className="pv">
    <div className="card stu" aria-label="学生名单">{R.students.map((x, i) => <button key={x.name} className="su" aria-current={i === cur} onClick={() => { if (dirty && !confirm('这一份的修改还没保存，确定切换吗？')) return; setCur(i); }}>
      <b>{x.name}</b><span className="sc">{fmt(x.total)}</span><small className={b.confirmed.includes(x.name) ? 'ok' : ''}>{b.confirmed.includes(x.name) ? '✓ 已确认' : '未确认'}</small></button>)}</div>
    <div className="card paper">{Array.from({ length: s.pages }, (_, p) => <img key={p + ':' + R.version} src={`/api/batches/${b.id}/preview/${s.key}/${p + 1}?v=${R.version}`} alt={`${s.name} 学情报告第 ${p + 1} 页`} loading="lazy" />)}</div>
    <div className="card ed">
      <h2>{s.name} · 报告文字</h2>
      <div className="f"><label htmlFor="edHead">一句话总结</label><textarea id="edHead" rows={2} value={h} onChange={e => setH(e.target.value)} maxLength={60} /></div>
      <div className="f"><label htmlFor="edMsg">老师寄语</label><textarea id="edMsg" rows={9} value={m} onChange={e => setM(e.target.value)} maxLength={600} /><small>{m.length} 字，建议 150–220 字</small></div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button className="btn sm" disabled={busy} onClick={() => run(async () => { const r = await api.post(`/batches/${b.id}/students/${enc(s.name)}/rewrite`).catch(e => toast(e.message)); if (r) { setH(r.headline); setM(r.message); toast('已重写，确认没问题后点「保存修改」'); } })}>重写这两段</button>
        {dirty && <button className={'btn sm' + (busy ? ' busy' : '')} disabled={busy} onClick={() => run(async () => { await saveText().catch(e => toast(e.message)); toast('已保存，报告已更新'); })}>保存修改</button>}
        <button className={'btn sm pri' + (busy ? ' busy' : '')} disabled={busy} onClick={() => run(async () => {
          if (dirty) await saveText(); const d = await api.post(`/batches/${b.id}/students/${enc(s.name)}/confirm`); setB(d);
          if (cur < R.students.length - 1) { setCur(cur + 1); toast('已确认，切换到下一位'); } else toast('最后一位也确认了'); })}>确认这一份</button>
      </div>
      <a className="btn sm ghost" href={`/api/batches/${b.id}/pdf/${s.key}`} target="_blank" rel="noreferrer">{I.dl}下载这一份 PDF</a>
      <div className="lock">数字、图表和结论由系统计算，不能在这里修改。数据有误请回到「核对」一步修改，再重新生成报告。</div>
    </div>
  </div>;
}

/* ---------------- 第 5 步：下载 ---------------- */
function Done({ b, setB, folders, reload }) {
  const toast = useToast(); const R = b.report; const cnt = useRef(); const fan = useRef();
  useEffect(() => {
    const n = R.students.length, t0 = performance.now(); let raf;
    const f = t => { const p = Math.min(1, (t - t0) / 1100); if (cnt.current) cnt.current.textContent = Math.round(n * (1 - Math.pow(1 - p, 3))); if (p < 1) raf = requestAnimationFrame(f); };
    raf = requestAnimationFrame(f);
    const t1 = setTimeout(() => fan.current && fan.current.classList.add('open'), 60);
    const t2 = setTimeout(() => { const r = fan.current?.getBoundingClientRect(); if (r) [[.5, .35, 40, 1.4], [.25, .5, 24, 1], [.75, .5, 24, 1]].forEach(([a, c, k, p], i) => setTimeout(() => burst(r.left + r.width * a, r.top + r.height * c, k, p), i * 180)); }, 350);
    return () => { cancelAnimationFrame(raf); clearTimeout(t1); clearTimeout(t2); };
  }, [R.students.length]);
  const pics = R.students.slice(0, 7);
  const move = async e => { const v = e.target.value; await api.patch('/batches/' + b.id, { move: true, folder_id: v ? +v : null }); setB(await api.get('/batches/' + b.id)); reload(); toast('已放入文件夹'); };
  return <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
    <div className="win fxzone" data-silk="win"><canvas className="silk" id="silkWin" aria-hidden="true" />
      <div className="win-in"><div><h2 className="count"><span ref={cnt}>{R.students.length}</span><small>份学情报告已生成</small></h2>
        <p>{b.meta.cls} · {b.meta.exam}　·　每份 3 页{R.has_plan ? '，含课程规划' : ''}</p>
        <div className="cta" style={{ marginTop: 22 }}><a className="lb hot lg" href={`/api/batches/${b.id}/zip`}>下载全班 zip</a>
          <label className="wl" htmlFor="doneFolder">放入文件夹</label>
          <select className="mv" id="doneFolder" value={b.folder_id || ''} onChange={move}><option value="">未分类</option>{folders.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}</select></div></div>
        <div className="fan" ref={fan} aria-hidden="true">{pics.map((s, i) => { const m = i - (pics.length - 1) / 2; return <div key={s.name} className="fs" style={{ '--r': m * 11 + 'deg', '--y': Math.abs(m) * 6 + 'px', transitionDelay: i * 60 + 'ms', zIndex: 10 - Math.abs(Math.round(m)) }}>
          <img src={`/api/batches/${b.id}/preview/${s.key}/1?v=${R.version}`} alt="" /></div>; })}</div></div></div>
    <div className="card dl"><div style={{ padding: '14px 18px', fontWeight: 700 }}>单份下载</div>
      {R.students.map(s => <div key={s.name} className="r"><span className="ext pdf">PDF</span><span className="nm">{s.name}_{b.meta.exam}_学情报告.pdf</span><small>{fmt(s.total)} 分</small><a className="btn ghost sm" href={`/api/batches/${b.id}/pdf/${s.key}`}>下载</a></div>)}</div>
  </div>;
}
