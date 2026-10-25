import React, { useEffect, useRef } from 'react';
import { Logo, ThemeButtons } from '../parts/ui.jsx';
import { go } from '../api.js';
import html from './landing.html.js';

const MODS = [
  { t: '成绩总览与班级位置', d: '分数、等级、在全班分数分布里的位置，再加一句话总结。', p: 0, y: [.15, .27] },
  { t: '和班级平均比一比', d: '各讲得分率雷达图、各类题型得分率、逐题对比。', p: 0, y: [.39, .57] },
  { t: '从课堂到考试', d: '出门测和期中放在一起，每一讲是稳定掌握、已经补上，还是考试失分。', p: 1, y: [.07, .43] },
  { t: '失分分析与下阶段建议', d: '失分分成个人漏洞、常规失分、全班难题，算出提分潜力，给三层建议。', p: 1, y: [.52, .42] },
  { t: '课程规划', d: '上传续报课程大纲才出现，把最需要补的那一讲和后续课程连起来。', p: 2, y: [.49, .32], opt: true },
  { t: '老师寄语', d: '系统先起草，老师可以改，最后署老师的名字。', p: 2, y: [.81, .15] },
];
const STU = [['林一航', 'a'], ['陈子墨', 'b'], ['沈知夏', 'c']];
const img = (k, p) => `/samples/${k}${p}.jpg`;

export default function Landing({ me }) {
  const ref = useRef();
  useEffect(() => {
    const root = ref.current; const $ = id => root.querySelector('#' + id);
    root.classList.remove('on'); void root.offsetWidth; root.classList.add('on');
    root.querySelectorAll('[data-split]').forEach(el => { el.innerHTML = [...el.textContent].map((c, i) => `<span style="--i:${i}">${c}</span>`).join(''); });
    [['hc1', 'b'], ['hc2', 'a'], ['hc3', 'c']].forEach(([id, k]) => $(id).innerHTML = `<img src="${img(k, 1)}" alt="">`);
    $('minis').innerHTML = [1, 2, 3].map(p => `<img src="${img('a', p)}" alt="示例报告第 ${p} 页">`).join('');
    // 报告拆解：点模块切到对应页面并框出位置
    let stu = 0, mod = 0, auto = true;
    $('dStu').innerHTML = STU.map(([n], i) => `<button aria-pressed="${i === 0}" data-i="${i}">${n}</button>`).join('');
    $('dList').innerHTML = MODS.map((m, i) => `<li><button data-i="${i}" aria-current="${i === 0}"><span class="n">${i + 1}</span><b>${m.t}${m.opt ? '<em>选配</em>' : ''}</b><small>${m.d}</small></button></li>`).join('');
    const paint = () => {
      const m = MODS[mod], k = STU[stu][1], wrap = $('dPaper');
      wrap.querySelectorAll('img').forEach(x => x.remove());
      [3, 2, 1].forEach(p => wrap.insertAdjacentHTML('afterbegin', `<img src="${img(k, p)}" alt="${p - 1 === m.p ? STU[stu][0] + ' 的示例报告第 ' + p + ' 页' : ''}" class="${p - 1 === m.p ? 'on' : ''}" data-p="${p - 1}">`));
      light();
    };
    const light = () => {
      const m = MODS[mod];
      $('dPaper').querySelectorAll('img').forEach(x => x.classList.toggle('on', +x.dataset.p === m.p));
      $('dMark').style.top = m.y[0] * 100 + '%'; $('dMark').style.height = m.y[1] * 100 + '%';
      $('dPage').textContent = `第 ${m.p + 1} 页 / 共 3 页`;
      root.querySelectorAll('#dList button').forEach(b => b.setAttribute('aria-current', +b.dataset.i === mod));
      root.querySelectorAll('#dStu button').forEach(b => b.setAttribute('aria-pressed', +b.dataset.i === stu));
    };
    root.querySelectorAll('#dList button').forEach(b => { b.onclick = b.onmouseenter = () => { auto = false; mod = +b.dataset.i; light(); }; });
    root.querySelectorAll('#dStu button').forEach(b => b.onclick = () => { auto = false; stu = +b.dataset.i; paint(); });
    paint();
    const iv = setInterval(() => { if (!auto) return; const r = $('dPaper').getBoundingClientRect(); if (r.bottom < 0 || r.top > innerHeight) return; mod = (mod + 1) % MODS.length; light(); }, 3200);
    const io = new IntersectionObserver(es => es.forEach(en => { if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); } }), { threshold: .18 });
    root.querySelectorAll('.rv,#vsBox').forEach(el => io.observe(el));
    root.querySelectorAll('[data-go]').forEach(b => b.onclick = () => go(b.dataset.go === 'reg' ? '/register' : '/login'));
    root.querySelectorAll('a[href^="#"]:not([href^="#/"])').forEach(a => a.onclick = e => { e.preventDefault(); const t = root.querySelector(a.getAttribute('href')); t && t.scrollIntoView({ behavior: 'smooth' }); });
    return () => { clearInterval(iv); io.disconnect(); };
  }, []);
  const jump = id => e => { e.preventDefault(); const t = document.getElementById(id); t && t.scrollIntoView({ behavior: 'smooth' }); };
  return <>
    <canvas id="silkBg" aria-hidden="true" />
    <div className="land fxzone" data-silk="bg" ref={ref}>
      <header className="lnav"><div className="in">
        <button className="brand" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })} aria-label="学情报告助手首页"><Logo /><b>学情报告助手</b></button>
        <div className="links">
          <a href="#vs" onClick={jump('vs')}>以前和现在</a><a href="#flow" onClick={jump('flow')}>使用流程</a><a href="#dissect" onClick={jump('dissect')}>报告拆解</a><a href="#why" onClick={jump('why')}>为什么可信</a>
          <ThemeButtons />
          {me ? <button className="lb hot" onClick={() => go('/app')}>进入工作台</button> : <><button className="lb" onClick={() => go('/login')}>登录</button><button className="lb hot" onClick={() => go('/register')}>免费开始</button></>}
        </div>
      </div></header>
      <div dangerouslySetInnerHTML={{ __html: html }} />
    </div>
  </>;
}
