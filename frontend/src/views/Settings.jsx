import React, { useCallback, useEffect, useState } from 'react';
import { api, go } from '../api.js';
import { useToast, useBusy, day } from '../parts/ui.jsx';

/* 设置页：个人信息、新建报告默认信息、用量、密码、登录设备、注销；管理员另有邀请码和用户管理 */
export default function Settings({ me, setMe }) {
  const toast = useToast();
  const [tab, setTab] = useState('me');
  return <section className="wrap set">
    <div className="ph"><div><h1>设置</h1><p>账号：{me.username}{me.admin ? ' · 管理员' : ''}</p></div><button className="btn ghost" onClick={() => go('/app')}>返回我的报告</button></div>
    {me.admin && <div className="seg settabs" role="tablist" aria-label="设置分类">
      <button role="tab" aria-selected={tab === 'me'} onClick={() => setTab('me')}>个人设置</button>
      <button role="tab" aria-selected={tab === 'admin'} onClick={() => setTab('admin')}>管理员</button>
    </div>}
    {tab === 'me' ? <Mine me={me} setMe={setMe} toast={toast} /> : <AdminPanel me={me} toast={toast} />}
  </section>;
}

function Card({ title, desc, children, foot, wide }) {
  return <div className={'card scard' + (wide ? ' wide' : '')}><div className="sh"><h2>{title}</h2>{desc && <p>{desc}</p>}</div><div className="sb">{children}</div>{foot && <div className="sf">{foot}</div>}</div>;
}

function Mine({ me, setMe, toast }) {
  const [name, setName] = useState(me.name || '');
  const [pf, setPf] = useState({ org: me.prefs?.org || '', campus: me.prefs?.campus || '', teacher: me.prefs?.teacher || '' });
  const [pw, setPw] = useState({ old: '', new: '', new2: '' }); const [pwErr, setPwErr] = useState('');
  const [del, setDel] = useState(null);
  const [b1, r1] = useBusy(), [b2, r2] = useBusy(), [b3, r3] = useBusy(), [b4, r4] = useBusy(), [b5, r5] = useBusy();
  const pct = Math.min(100, me.used / Math.max(1, me.quota) * 100);
  const saveName = () => r1(async () => { if (!name.trim()) return toast('称呼不能为空'); setMe(await api.patch('/auth/me', { name })); toast('称呼已保存'); });
  const savePf = () => r2(async () => { setMe(await api.patch('/auth/me', { prefs: { ...pf, subject: '数学' } })); toast('默认信息已保存，下次新建报告会自动填好'); });
  const savePw = e => { e.preventDefault(); setPwErr('');
    if (pw.new.length < 8) return setPwErr('新密码至少 8 位');
    if (pw.new !== pw.new2) return setPwErr('两次输入的新密码不一致');
    r3(async () => { try { await api.post('/auth/password', { old: pw.old, new: pw.new }); setPw({ old: '', new: '', new2: '' }); toast('密码已修改，其他设备需要用新密码重新登录'); } catch (er) { setPwErr(er.message); } }); };
  const others = () => r4(async () => { const d = await api.post('/auth/logout-others'); toast(d.n ? `已退出其他 ${d.n} 个登录` : '没有其他设备在登录'); });
  const delMe = e => { e.preventDefault(); r5(async () => { try { await api.post('/auth/delete', { password: del }); go('/'); setMe(null); } catch (er) { toast(er.message); } }); };
  return <div className="sgrid">
    <Card title="新建报告默认信息" desc="每次新建报告，第 1 步会先自动填好这些内容，老师只需要核对或修改。"
      foot={<button className={'btn pri' + (b2 ? ' busy' : '')} disabled={b2} onClick={savePf}>保存默认信息</button>}>
      <div className="form">
        <div className="f"><label htmlFor="pOrg">机构名称<span>显示在报告抬头</span></label><input id="pOrg" value={pf.org} maxLength={40} onChange={e => setPf({ ...pf, org: e.target.value })} placeholder="如 示例教育" /></div>
        <div className="f"><label htmlFor="pCampus">校区</label><input id="pCampus" value={pf.campus} maxLength={40} onChange={e => setPf({ ...pf, campus: e.target.value })} placeholder="如 示例校区" /></div>
        <div className="f"><label htmlFor="pTeacher">授课老师<span>用于报告抬头和寄语署名</span></label><input id="pTeacher" value={pf.teacher} maxLength={40} onChange={e => setPf({ ...pf, teacher: e.target.value })} placeholder={me.name} /></div>
        <div className="f"><label>学科</label><input value="数学" disabled /><small>第一版只支持数学</small></div>
      </div>
    </Card>

    <Card title="个人信息" desc="称呼会显示在左下角，也是新建报告时「授课老师」的备选。"
      foot={<button className={'btn pri' + (b1 ? ' busy' : '')} disabled={b1 || name === me.name} onClick={saveName}>保存</button>}>
      <div className="form one">
        <div className="f"><label>账号</label><input value={me.username} disabled /><small>账号不能修改</small></div>
        <div className="f"><label htmlFor="sName">称呼</label><input id="sName" value={name} maxLength={20} onChange={e => setName(e.target.value)} placeholder="如 王老师" /></div>
      </div>
    </Card>

    <Card title="修改密码" desc="修改后，其他已登录的设备需要用新密码重新登录。">
      <form className="form one" onSubmit={savePw} noValidate>
        <input type="text" autoComplete="username" value={me.username} readOnly hidden />
        <div className="f"><label htmlFor="pwOld">当前密码</label><input id="pwOld" type="password" autoComplete="current-password" value={pw.old} onChange={e => setPw({ ...pw, old: e.target.value })} /></div>
        <div className="f"><label htmlFor="pwNew">新密码</label><input id="pwNew" type="password" autoComplete="new-password" placeholder="至少 8 位" value={pw.new} onChange={e => setPw({ ...pw, new: e.target.value })} /></div>
        <div className="f"><label htmlFor="pwNew2">确认新密码</label><input id="pwNew2" type="password" autoComplete="new-password" value={pw.new2} onChange={e => setPw({ ...pw, new2: e.target.value })} /></div>
        {pwErr && <p className="err" role="alert">{pwErr}</p>}
        <div><button className={'btn pri' + (b3 ? ' busy' : '')} disabled={b3 || !pw.old || !pw.new}>修改密码</button></div>
      </form>
    </Card>

    <Card title="本月用量" desc={`每生成一个报告批次算 1 次，${me.reset} 重置。`}>
      <div className="quota"><b>{me.used}</b><span> / {me.quota} 批次</span></div>
      <i className="usage big" aria-hidden="true"><u style={{ width: pct + '%' }} /></i>
      <small className="muted">{me.used >= me.quota ? '本月额度已用完，如需更多请联系管理员。' : `本月还可以生成 ${me.quota - me.used} 个批次。`}</small>
    </Card>

    <Card title="登录设备" desc="在别人的电脑上登录过、忘了退出？点一下，除了现在这台，其他设备都要重新登录。">
      <div><button className={'btn' + (b4 ? ' busy' : '')} disabled={b4} onClick={others}>退出其他所有设备</button></div>
    </Card>

    {!me.admin && <Card wide title="注销账号" desc="账号、文件夹和所有报告会被永久删除，不可恢复。">
      {del === null ? <div><button className="btn danger" onClick={() => setDel('')}>注销账号</button></div> :
        <form className="form one" onSubmit={delMe}>
          <div className="f"><label htmlFor="delPw">输入密码确认注销</label><input id="delPw" type="password" autoComplete="current-password" value={del} onChange={e => setDel(e.target.value)} autoFocus /></div>
          <div className="row2l"><button type="button" className="btn" onClick={() => setDel(null)}>取消</button><button className={'btn danger solid' + (b5 ? ' busy' : '')} disabled={b5 || !del}>永久注销</button></div>
        </form>}
    </Card>}
  </div>;
}

function AdminPanel({ me, toast }) {
  const [users, setUsers] = useState(null); const [inv, setInv] = useState(null); const [code, setCode] = useState('');
  const [pwShow, setPwShow] = useState(null); const [qEdit, setQEdit] = useState(null);
  const [bi, ri] = useBusy();
  const load = useCallback(() => Promise.all([api.get('/admin/users').then(setUsers), api.get('/admin/invite').then(d => { setInv(d); setCode(d.code); })]).catch(e => toast(e.message)), [toast]);
  useEffect(() => { load(); }, [load]);
  const saveInv = () => ri(async () => { try { const d = await api.put('/admin/invite', { code }); setInv({ ...inv, code: d.code }); toast(d.code ? '邀请码已更新，旧的邀请码立即失效' : '已关闭邀请码，任何人都能注册'); } catch (e) { toast(e.message); } });
  const copy = t => { navigator.clipboard?.writeText(t).then(() => toast('已复制'), () => toast('复制失败，请手动选择复制')); };
  const edit = async (u, body, msg) => { try { await api.patch(`/admin/users/${u.id}`, body); toast(msg); load(); } catch (e) { toast(e.message); } };
  const [sure, setSure] = useState(null);
  const resetPw = async u => { if (sure !== u.id) { setSure(u.id); setTimeout(() => setSure(s => s === u.id ? null : s), 4000); return; } setSure(null); try { const d = await api.post(`/admin/users/${u.id}/password`); setPwShow({ u, pw: d.password }); } catch (e) { toast(e.message); } };
  const saveQ = (u) => { const n = parseInt(qEdit.v, 10); if (isNaN(n) || n < 0) return toast('请输入 0 或更大的整数'); setQEdit(null); edit(u, { quota: n }, `已把「${u.name || u.username}」的每月额度改为 ${n}`); };
  return <div className="sgrid">
    <Card title="注册邀请码" desc="注册时必须填写这个邀请码。发给需要使用的老师；泄露了就换一个，旧的立即失效。留空表示不需要邀请码。"
      foot={<><button className={'btn pri' + (bi ? ' busy' : '')} disabled={bi || !inv || code === inv.code} onClick={saveInv}>保存</button>{inv?.code && <button className="btn ghost" onClick={() => copy(inv.code)}>复制当前邀请码</button>}</>}>
      <div className="form one"><div className="f"><label htmlFor="invCode">邀请码</label><input id="invCode" value={code} maxLength={32} onChange={e => setCode(e.target.value.trim())} placeholder="4–32 位字母或数字" /></div></div>
    </Card>

    <Card title="用户管理" desc={`默认每人每月 ${inv?.default_quota ?? '—'} 个批次。忘记密码的老师在这里重置，把新密码私下发给对方，对方登录后可以在设置里改掉。`}>
      {!users ? <p className="muted">加载中…</p> : <div className="tw"><table className="list users">
        <thead><tr><th>老师</th><th>本月用量</th><th>报告</th><th>状态</th><th style={{ textAlign: 'right' }}>操作</th></tr></thead>
        <tbody>{users.map(u => <tr key={u.id} className={u.disabled ? 'off' : ''}>
          <td><div className="bn"><b>{u.name || u.username}{u.admin && <span className="chip c-done tag">管理员</span>}</b><small>{u.username} · {day(u.created)} 注册</small></div></td>
          <td className="nw">{qEdit?.id === u.id ? <span className="qedit">{u.used} / <input type="number" min="0" value={qEdit.v} autoFocus aria-label="每月额度"
              onChange={e => setQEdit({ ...qEdit, v: e.target.value })} onKeyDown={e => { if (e.key === 'Enter') saveQ(u); if (e.key === 'Escape') setQEdit(null); }} />
              <button className="btn sm pri" onClick={() => saveQ(u)}>保存</button><button className="btn sm ghost" onClick={() => setQEdit(null)}>取消</button></span>
            : <>{u.used} / {u.quota}{u.custom_quota && <small className="muted">（单独设置）</small>}</>}</td>
          <td className="nw">{u.batches}</td>
          <td><span className={'chip ' + (u.disabled ? 'c-draft' : 'c-done')}>{u.disabled ? '已停用' : '正常'}</span></td>
          <td><div className="acts wrapacts">
            <button className="btn ghost sm" onClick={() => setQEdit({ id: u.id, v: String(u.quota) })}>改额度</button>
            {u.custom_quota && <button className="btn ghost sm" onClick={() => edit(u, { reset_quota: true }, '已恢复默认额度')}>恢复默认</button>}
            <button className={'btn ghost sm' + (sure === u.id ? ' danger' : '')} onClick={() => resetPw(u)}>{sure === u.id ? '再点一次确认' : '重置密码'}</button>
            {u.id !== me.id && <button className={'btn ghost sm' + (u.disabled ? '' : ' danger')} onClick={() => edit(u, { disabled: !u.disabled }, u.disabled ? '已恢复账号' : '已停用，对方会立刻被退出登录')}>{u.disabled ? '恢复' : '停用'}</button>}
          </div></td>
        </tr>)}</tbody></table></div>}
    </Card>

    {pwShow && <div className="modal" role="dialog" aria-modal="true" aria-label="新密码" onClick={() => setPwShow(null)}>
      <div className="card mbox" onClick={e => e.stopPropagation()}>
        <h2>新密码已生成</h2>
        <p>「{pwShow.u.name || pwShow.u.username}」（账号 {pwShow.u.username}）的新密码是：</p>
        <div className="pwbox"><code>{pwShow.pw}</code><button className="btn sm" onClick={() => copy(pwShow.pw)}>复制</button></div>
        <p className="muted">这个密码只显示这一次。请私下发给对方，提醒对方登录后到「设置 → 修改密码」改掉。</p>
        <div className="row2l"><button className="btn pri" onClick={() => setPwShow(null)}>知道了</button></div>
      </div>
    </div>}
  </div>;
}
