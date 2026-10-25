import React, { useEffect, useState, useCallback } from 'react';
import { api, go } from './api.js';
import { ToastProvider } from './parts/ui.jsx';
import Landing from './views/Landing.jsx';
import Login from './views/Login.jsx';
import Workspace from './views/Workspace.jsx';

/* 简单的 hash 路由：#/ 首页，#/login 登录，#/register 注册，#/app 工作区，#/app/b/12 某个报告 */
const parse = () => (location.hash.replace(/^#/, '') || '/');


export default function App() {
  const [route, setRoute] = useState(parse());
  const [me, setMe] = useState(undefined);   // undefined=检查中，null=未登录
  const refreshMe = useCallback(() => api.get('/auth/me').then(setMe).catch(() => setMe(null)), []);
  useEffect(() => { refreshMe(); const f = () => { setRoute(parse()); }; addEventListener('hashchange', f); return () => removeEventListener('hashchange', f); }, [refreshMe]);
  useEffect(() => { window.scrollTo(0, 0); }, [route.split('/')[1]]);
  const top = route.split('/')[1] || '';
  useEffect(() => {
    const t = parse().split('/')[1] || '';      // 读最新地址：退出登录时已经跳回首页，不再被带去登录页
    if (t === 'app' && me === null) go('/login');
    if ((top === 'login' || top === 'register') && me) go('/app');
  }, [top, me]);
  let view = null;
  if (top === 'app') { if (me) view = <Workspace me={me} setMe={setMe} refreshMe={refreshMe} route={route} />; }
  else if (top === 'login' || top === 'register') { if (me === null) view = <Login reg={top === 'register'} onDone={u => { setMe(u); go('/app'); }} />; }
  else view = <Landing me={me} />;
  return <ToastProvider><canvas id="fxTop" aria-hidden="true" />{view}</ToastProvider>;
}
