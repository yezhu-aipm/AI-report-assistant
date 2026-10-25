import React, { useCallback, useEffect, useState } from 'react';
import { api, go } from '../api.js';
import { Logo, ThemeButtons, useBusy } from '../parts/ui.jsx';

export default function Login({ reg, onDone }) {
  const [f, setF] = useState({ username: '', password: '', password2: '', name: '', agree: false, invite: '', captcha: '' });
  const [err, setErr] = useState(''); const [busy, run] = useBusy(); const [cfg, setCfg] = useState({ allow_register: true, invite: false });
  const [cap, setCap] = useState(null); const [needCap, setNeedCap] = useState(reg);
  const newCap = useCallback(() => api.get('/auth/captcha').then(setCap).catch(() => setCap(null)), []);
  useEffect(() => { api.get('/config').then(setCfg).catch(() => {}); }, []);
  useEffect(() => { setErr(''); setNeedCap(reg); }, [reg]);
  useEffect(() => { if (needCap) newCap(); }, [needCap, newCap]);
  const checkState = u => { if (reg || !u) return; api.get('/auth/login-state?username=' + encodeURIComponent(u)).then(d => d && d.captcha && setNeedCap(true)).catch(() => {}); };
  const set = k => e => setF({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value });
  const submit = e => {
    e.preventDefault(); setErr('');
    if (!/^[A-Za-z0-9]{4,20}$/.test(f.username)) return setErr('账号需要 4–20 位字母或数字');
    if (f.password.length < 8) return setErr('密码至少 8 位');
    if (reg && f.password !== f.password2) return setErr('两次输入的密码不一致');
    if (reg && !f.agree) return setErr('请先勾选同意用户协议和隐私政策');
    if (reg && cfg.invite && !f.invite.trim()) return setErr('请填写邀请码');
    if (needCap && !f.captcha.trim()) return setErr('请填写验证码');
    const body = { ...f, cid: needCap && cap ? cap.id : undefined };
    run(() => api.post(reg ? '/auth/register' : '/auth/login', body).then(onDone).catch(e => {
      setErr(e.message); setF(x => ({ ...x, captcha: '' }));
      if (e.data && e.data.captcha) { if (needCap) newCap(); else setNeedCap(true); }
    }));
  };
  return <>
    <canvas id="silkBg" aria-hidden="true" />
    <div className="login fxzone" data-silk="bg">
      <div className="lside">
        <div className="topbar"><button className="brand" onClick={() => go('/')} aria-label="返回首页"><Logo /><b>学情报告助手</b></button><ThemeButtons /></div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <h2>上传三份材料，全班每位学生的学情报告一次生成</h2>
          <p>成绩怎么算、错在哪、下一步怎么做，系统写成一份家长看得懂的三页 PDF。老师只需要核对和确认。</p>
        </div>
        <div className="lsteps">
          <div><b>1</b><span>上传试卷、逐题成绩表、出门测记录表</span></div>
          <div><b>2</b><span>核对系统标出的几处问题</span></div>
          <div><b>3</b><span>预览、改寄语，下载全班 PDF</span></div>
        </div>
      </div>
      <div className="lmain">
        <form className="lbox" onSubmit={submit} noValidate>
          <h1>{reg ? '注册账号' : '登录'}</h1>
          <div className="sw" role="group" aria-label="登录或注册">
            <button type="button" aria-pressed={!reg} onClick={() => go('/login')}>登录</button>
            <button type="button" aria-pressed={reg} onClick={() => go('/register')} disabled={!cfg.allow_register}>注册</button>
          </div>
          <div className="f"><label htmlFor="lUser">账号</label><input id="lUser" autoComplete="username" placeholder="4–20 位字母或数字" value={f.username} onChange={set('username')} onBlur={e => checkState(e.target.value)} /></div>
          {reg && <div className="f"><label htmlFor="lName">怎么称呼您<span>选填，用于报告署名，如 王老师</span></label><input id="lName" placeholder="王老师" maxLength={20} value={f.name} onChange={set('name')} /></div>}
          <div className="f"><label htmlFor="lPass">密码</label><input id="lPass" type="password" autoComplete={reg ? 'new-password' : 'current-password'} placeholder="至少 8 位" value={f.password} onChange={set('password')} /></div>
          {reg && <div className="f"><label htmlFor="lPass2">确认密码</label><input id="lPass2" type="password" autoComplete="new-password" placeholder="再输入一次密码" value={f.password2} onChange={set('password2')} /></div>}
          {reg && cfg.invite && <div className="f"><label htmlFor="lInv">邀请码<span>向管理员索取</span></label><input id="lInv" autoComplete="off" value={f.invite} onChange={set('invite')} /></div>}
          {needCap && <div className="f"><label htmlFor="lCap">验证码<span>看不清？点图片换一张</span></label><div className="caprow">
            <input id="lCap" autoComplete="off" maxLength={4} placeholder="4 位字符" value={f.captcha} onChange={set('captcha')} />
            <button type="button" className="capimg" onClick={newCap} aria-label="换一张验证码" title="换一张">{cap ? <img src={cap.img} alt="验证码图片" /> : '加载中'}</button></div></div>}
          {reg && <label className="agree"><input type="checkbox" checked={f.agree} onChange={set('agree')} /> 我已阅读并同意《用户协议》和《隐私政策》，并确认有权处理所上传的学生信息</label>}
          {err && <p className="err" role="alert">{err}</p>}
          <button className={'btn pri block' + (busy ? ' busy' : '')} disabled={busy}>{reg ? '注册并登录' : '登录'}</button>
          {!reg && <p className="demo">忘记密码请联系管理员重置。</p>}
          {reg && !cfg.allow_register && <p className="demo">暂未开放注册，请联系管理员开通账号。</p>}
        </form>
      </div>
    </div>
  </>;
}
