/* theme: five hues, each with a day and a night palette */
const DAY = [
  {n:'晨光蜜桃', d:[.99,.90,.86], m:[1,.68,.58], w:[1,.98,.94], bg:'#fff3ee', ink:'#2b1a16', ink2:'#6a4f47', acc:'#c9431b', shine:'#e0522a', g1:'rgba(255,140,100,.9)', g2:'rgba(255,190,160,.5)'},
  {n:'晴空蓝', d:[.87,.92,1], m:[.52,.70,1], w:[1,1,1], bg:'#eef4ff', ink:'#10203f', ink2:'#4a5a7a', acc:'#2a62e8', shine:'#2f6bff', g1:'rgba(80,140,255,.9)', g2:'rgba(150,190,255,.5)'},
  {n:'薄荷汽水', d:[.87,.97,.93], m:[.46,.85,.75], w:[1,1,1], bg:'#edfaf5', ink:'#0f2f28', ink2:'#46645c', acc:'#0b8a65', shine:'#0f9f74', g1:'rgba(30,190,140,.9)', g2:'rgba(140,230,200,.5)'},
  {n:'香芋紫', d:[.94,.91,1], m:[.70,.62,1], w:[1,1,1], bg:'#f5f1ff', ink:'#221a3f', ink2:'#5b5480', acc:'#6a46f5', shine:'#7451ff', g1:'rgba(130,100,255,.9)', g2:'rgba(200,180,255,.5)'},
  {n:'柠檬黄', d:[1,.97,.85], m:[1,.83,.40], w:[1,1,.97], bg:'#fffbea', ink:'#2a2410', ink2:'#6b6242', acc:'#a86a00', shine:'#d48a00', g1:'rgba(255,190,40,.9)', g2:'rgba(255,225,140,.5)'}
];
const nt = (n, bg, d, m, w, acc, shine, g1, g2, ink2) => ({n, d, m, w, lift:0, night:true, bg, ink:'#eef0ff', ink2, acc, shine, g1, g2});
const NIGHT = [
  nt('玫瑰夜', '#160a12', [.08,.03,.06], [.46,.14,.32], [1,.76,.88], '#ff7ab8', '#ff9cc9', 'rgba(255,110,170,.8)', 'rgba(210,70,140,.36)', '#d2a9bf'),
  nt('深海蓝', '#06101f', [.02,.05,.11], [.07,.24,.50], [.62,.84,1], '#5aa9ff', '#7cc0ff', 'rgba(70,150,255,.85)', 'rgba(40,110,230,.38)', '#9fb4d2'),
  nt('极光绿', '#05130f', [.02,.07,.06], [.05,.33,.27], [.62,1,.86], '#3fe0b0', '#6af0c6', 'rgba(50,220,170,.8)', 'rgba(20,160,120,.36)', '#9cc7bb'),
  nt('星夜紫', '#0a0b1a', [.03,.035,.09], [.19,.16,.46], [.80,.74,1], '#a68cff', '#b9a5ff', 'rgba(150,120,255,.85)', 'rgba(110,86,240,.38)', '#a9aed2'),
  nt('琥珀夜', '#140e06', [.07,.045,.02], [.44,.26,.07], [1,.86,.6], '#ffb547', '#ffc86e', 'rgba(255,180,70,.8)', 'rgba(220,130,40,.36)', '#d2bfa0')
];
let hue = 3, dark = false;
try { const t = JSON.parse(localStorage.getItem('xq-theme') || 'null'); if (t) { hue = (+t.h || 0) % 5; dark = !!t.d; } } catch (e) {}
const listeners = new Set();
export const onTheme = f => { listeners.add(f); return () => listeners.delete(f); };
export const PAL = () => (dark ? NIGHT : DAY)[hue];
export function applyTheme(){
  const P = PAL(), r = document.documentElement;
  [['--bBg',P.bg],['--bInk',P.ink],['--bInk2',P.ink2],['--bAcc',P.acc],['--bShine',P.shine],['--bGlow1',P.g1],['--bGlow2',P.g2]].forEach(([k, v]) => r.style.setProperty(k, v));
  r.classList.toggle('night', dark); r.dataset.theme = dark ? 'dark' : 'light';
  r.style.setProperty('--brand', P.acc); r.style.setProperty('--brand-ink', dark ? '#14122b' : '#ffffff');
  r.style.setProperty('--brand-soft', `color-mix(in srgb, ${P.acc} ${dark ? 22 : 12}%, ${dark ? '#171d28' : '#ffffff'})`);
  try { localStorage.setItem('xq-theme', JSON.stringify({h:hue, d:dark})); } catch (e) {}
  listeners.forEach(f => f({hue, dark, name:P.n}));
}
export const nextHue = () => { hue = (hue + 1) % 5; applyTheme(); };
export const toggleDark = () => { dark = !dark; applyTheme(); };
export const themeState = () => ({hue, dark, name:PAL().n});

/* silk */
function makeSilk(cv){
  const gl = cv.getContext('webgl'); if (!gl) return () => {};
  const vs = 'attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}';
  const fs = `precision highp float;uniform float t;uniform vec2 r;uniform vec3 cD,cM,cW;uniform vec4 rp[4];uniform float lift;
  float silk(vec2 uv){vec2 tex=uv*2.2;tex.y+=0.03*sin(8.*tex.x-t);return .6+.4*sin(5.*(tex.x+tex.y+cos(3.*tex.x+5.*tex.y)+.02*t)+sin(20.*(tex.x+tex.y-.1*t)));}
  void main(){vec2 fc=gl_FragCoord.xy;float glow=0.;
  for(int i=0;i<4;i++){vec4 R=rp[i];if(R.w>0.){vec2 d=fc-R.xy;float dist=length(d);float front=R.z*520.*R.w;
    float env=exp(-pow((dist-front)/(150.*R.w),2.))*exp(-R.z*1.3);float w=sin(dist*.05/R.w-R.z*10.)*env;
    fc+=normalize(d+.001)*w*26.*R.w;glow+=env*.55;}}
  vec2 uv=fc/r;uv.x*=r.x/r.y;float c=cos(-.5),s=sin(-.5);uv=mat2(c,-s,s,c)*uv;float v=silk(uv);
  vec3 col=mix(cD,cM,smoothstep(.25,.95,v));col=mix(col,cW,pow(clamp(v,0.,1.),9.)*.9);
  vec2 q=gl_FragCoord.xy/r;col=mix(col,vec3(1.),lift*q.y);col=mix(col,cW,clamp(glow,0.,.45));gl_FragColor=vec4(col,1.);}`;
  const sh = (type, src) => { const o = gl.createShader(type); gl.shaderSource(o, src); gl.compileShader(o); return o; };
  const pr = gl.createProgram(); gl.attachShader(pr, sh(gl.VERTEX_SHADER, vs)); gl.attachShader(pr, sh(gl.FRAGMENT_SHADER, fs)); gl.linkProgram(pr); gl.useProgram(pr);
  const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1,1,-1,-1,1,1,1]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(pr, 'p'); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  const U = n => gl.getUniformLocation(pr, n), uT = U('t'), uR = U('r'), uD = U('cD'), uM = U('cM'), uW = U('cW'), uP = U('rp'), uL = U('lift');
  return (t, P, rips = []) => { gl.viewport(0, 0, cv.width, cv.height); gl.uniform3fv(uD, P.d); gl.uniform3fv(uM, P.m); gl.uniform3fv(uW, P.w); gl.uniform1f(uT, t / 1000 * 1.2); gl.uniform2f(uR, cv.width, cv.height); gl.uniform1f(uL, P.lift ?? .12);
    const arr = new Float32Array(16); rips.slice(-4).forEach((q, i) => arr.set(q, i * 4)); gl.uniform4fv(uP, arr); gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4); };
}
const SILK_SCALE = () => Math.min(devicePixelRatio || 1, 1.5) * .6;
/* silk canvases are looked up by id every frame, so React can mount and unmount them freely */
const SILKS = {bg:{id:'silkBg', rips:[]}, rec:{id:'silkRec', rips:[]}, win:{id:'silkWin', rips:[]}};
const shown = el => el && el.isConnected && el.getClientRects().length > 0;
function silkOf(s){ const cv = document.getElementById(s.id); if (!shown(cv)) return null; if (s.cv !== cv) { s.cv = cv; s.draw = makeSilk(cv); s.rips = []; } return s; }

/* overlay for click shimmer + stardust; sprites are rendered once so a frame never recomputes shadow blur */
let fx = null, fc = null;
let glints = [], dust = [], lastClick = 0, lastFrame = 0, fxDirty = false, lastDust = {x:-99, y:-99};
const sprite = {}, SPR = 48;
function starSprite(c){ if (sprite[c]) return sprite[c]; const o = document.createElement('canvas'); o.width = o.height = SPR; const g = o.getContext('2d');
  g.translate(SPR / 2, SPR / 2); g.fillStyle = c; g.shadowColor = c; g.shadowBlur = 8; g.beginPath(); const s = SPR * .3;
  for (let i = 0; i < 4; i++) { g.lineTo(0, -s); g.quadraticCurveTo(0, 0, s, 0); g.rotate(Math.PI / 2); } g.closePath(); g.fill(); return sprite[c] = o; }
const ringSpr = (() => { const o = document.createElement('canvas'); o.width = o.height = 256; const g = o.getContext('2d'), gr = g.createRadialGradient(128, 128, 70, 128, 128, 128);
  gr.addColorStop(0, 'rgba(255,255,255,0)'); gr.addColorStop(.75, 'rgba(255,255,255,.75)'); gr.addColorStop(1, 'rgba(255,255,255,0)'); g.fillStyle = gr; g.fillRect(0, 0, 256, 256); return o; })();
const CLICK_GAP = 220, MAX_GLINTS = 90, MAX_DUST = 90;
export function burst(x, y, n = 22, power = 1){
  const P = PAL(), cols = ['#ffffff', P.acc, P.shine, '#ffffff'];
  for (let i = 0; i < n; i++) { const a = Math.random() * Math.PI * 2, v = (1.6 + Math.random() * 5.2) * power; glints.push({x, y, vx:Math.cos(a) * v, vy:Math.sin(a) * v - 1.2, l:1, s:6 + Math.random() * 12, img:starSprite(cols[i % cols.length]), ph:Math.random() * 6, spin:(Math.random() - .5) * .2, rot:Math.random() * 3}); }
  glints.push({ring:1, x, y, l:1});
  if (glints.length > MAX_GLINTS) glints.splice(0, glints.length - MAX_GLINTS);
}
function silkRipple(key, cx, cy){ const s = SILKS[key] && silkOf(SILKS[key]); if (!s) return; const r = s.cv.getBoundingClientRect(); s.rips.push({x:cx - r.left, y:cy - r.top, t:performance.now()}); if (s.rips.length > 3) s.rips.shift(); }
const INTERACTIVE = 'button,a,input,select,textarea,label,.hc,.dlist,.seg';
document.addEventListener('click', e => { const z = e.target.closest('.fxzone'); if (!z || e.target.closest(INTERACTIVE)) return;
  const now = performance.now(); if (now - lastClick < CLICK_GAP) return; lastClick = now;
  silkRipple(z.dataset.silk, e.clientX, e.clientY); burst(e.clientX, e.clientY); });
let tilt = {x:0, y:0, tx:0, ty:0};
addEventListener('mousemove', e => {
  if (document.getElementById('tilt3')) { tilt.tx = (e.clientX / innerWidth - .5) * 2; tilt.ty = (e.clientY / innerHeight - .5) * 2; }
  /* stardust follows the pointer on every page; click shimmer stays limited to showcase zones */
  const x = e.clientX, y = e.clientY; if (Math.hypot(x - lastDust.x, y - lastDust.y) < 6) return; lastDust = {x, y};
  const P = PAL(), cols = dark ? ['#ffffff', P.acc, P.shine] : [P.acc, P.shine, P.acc];
  for (let i = 0; i < 2; i++) dust.push({x:x + (Math.random() - .5) * 8, y:y + (Math.random() - .5) * 8, vx:(Math.random() - .5) * .8, vy:Math.random() * .6 + .2, l:1, s:5 + Math.random() * 7, img:starSprite(cols[(Math.random() * 3) | 0]), rot:Math.random() * 3, ph:Math.random() * 6});
  if (dust.length > MAX_DUST) dust.splice(0, dust.length - MAX_DUST); });
document.addEventListener('mouseleave', () => { tilt.tx = tilt.ty = 0; });
document.addEventListener('mousemove', e => { const g = e.target.closest && e.target.closest('.glow'); if (!g) return; const r = g.getBoundingClientRect(); g.style.setProperty('--mx', (e.clientX - r.left) + 'px'); g.style.setProperty('--my', (e.clientY - r.top) + 'px'); });

function fit(cv, k){ const r = cv.getBoundingClientRect(), w = Math.max(1, Math.round(r.width * k)), h = Math.max(1, Math.round(r.height * k)); if (cv.width !== w || cv.height !== h) { cv.width = w; cv.height = h; } return r; }
function frame(t){
  const P = PAL(), k = SILK_SCALE();
  for (const s0 of Object.values(SILKS)) { const s = silkOf(s0); if (!s) continue; const r = fit(s.cv, k), kk = s.cv.width / Math.max(1, r.width);
    s.rips = s.rips.filter(q => t - q.t < 3200); s.draw(t, P, s.rips.map(q => [q.x * kk, s.cv.height - q.y * kk, (t - q.t) / 1000, kk])); }
  const te = document.getElementById('tilt3');
  if (te) { tilt.x += (tilt.tx - tilt.x) * .07; tilt.y += (tilt.ty - tilt.y) * .07;
    te.style.transform = `rotateY(${(tilt.x * 14).toFixed(2)}deg) rotateX(${(2 - tilt.y * 10).toFixed(2)}deg)`; te.style.setProperty('--gx', (60 - tilt.x * 40).toFixed(1) + '%'); }
  const f = Math.min(3, (t - (lastFrame || t)) / 16.67 || 1); lastFrame = t;
  if (!fx || !fx.isConnected) { fx = document.getElementById('fxTop'); fc = fx && fx.getContext('2d'); }
  if (fx && (glints.length || dust.length || fxDirty)) {
    fxDirty = glints.length > 0 || dust.length > 0;
    const d = Math.min(devicePixelRatio || 1, 1.5), W = innerWidth, H = innerHeight;
    if (fx.width !== Math.round(W * d) || fx.height !== Math.round(H * d)) { fx.width = Math.round(W * d); fx.height = Math.round(H * d); }
    fc.setTransform(d, 0, 0, d, 0, 0); fc.clearRect(0, 0, W, H);
    glints = glints.filter(g => g.l > 0);
    for (const g of glints) {
      if (g.ring) { g.l -= .022 * f; const rr = (1 - g.l) * 150; fc.globalAlpha = Math.max(0, g.l); fc.drawImage(ringSpr, g.x - rr, g.y - rr, rr * 2, rr * 2); continue; }
      const dmp = Math.pow(.95, f); g.x += g.vx * f; g.y += g.vy * f; g.vx *= dmp; g.vy = g.vy * dmp + .035 * f; g.l -= .014 * f; g.rot += g.spin * f;
      const tw = .55 + .45 * Math.sin(t / 90 + g.ph), sz = g.s * (0.6 + 0.4 * g.l), c = Math.cos(g.rot), sn = Math.sin(g.rot);
      fc.globalAlpha = Math.max(0, g.l) * tw; fc.setTransform(d * c, d * sn, -d * sn, d * c, g.x * d, g.y * d); fc.drawImage(g.img, -sz, -sz, sz * 2, sz * 2); fc.setTransform(d, 0, 0, d, 0, 0); }
    dust = dust.filter(p => p.l > 0);
    for (const p of dust) { p.x += p.vx * f; p.y += p.vy * f; p.l -= .02 * f; p.rot += .05 * f;
      const sz = p.s * (.4 + .6 * p.l), c = Math.cos(p.rot), sn = Math.sin(p.rot); fc.globalAlpha = Math.max(0, p.l) * (.6 + .4 * Math.sin(t / 80 + p.ph));
      fc.setTransform(d * c, d * sn, -d * sn, d * c, p.x * d, p.y * d); fc.drawImage(p.img, -sz, -sz, sz * 2, sz * 2); }
    fc.setTransform(d, 0, 0, d, 0, 0); fc.globalAlpha = 1;
  }
  requestAnimationFrame(frame);
}
let started = false;
export function startEffects(){ if (started) return; started = true; applyTheme(); requestAnimationFrame(frame); }

