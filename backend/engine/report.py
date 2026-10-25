"""报告排版引擎：把分析结果 + 文案渲染成三页 A4 PDF。
每个批次在独立子进程里运行（run.py），模块级变量由 bind() 一次性注入。"""
import json, os, sys, html, math
e = html.escape
A = {}; META = {}; CLS = {}; LMAP = {}; KIND = '期中'
ADVICE = {}; HARD_NOTE = ''; HEADLINE = {}; MESSAGE = {}; ITEM_TIP = {}; PLAN = None; PLAN_LINK = {}
CN = '零一二三四五六七八九十'
def campus():
    c = (META.get('campus') or '').strip()
    return c if not c or c.endswith('校区') else c + '校区'
def cn(n): return CN[n] if n <= 10 else str(n)

def bind(analysis, content):
    g = globals()
    g['A'] = analysis; g['META'] = analysis['meta']; g['CLS'] = analysis['class']
    g['LMAP'] = {L['no']: L.get('short') or L['name'] for L in analysis['class']['lect']}
    g['KIND'] = analysis['meta'].get('kind') or '期中'
    g['ADVICE'] = content.get('advice', {}); g['HARD_NOTE'] = content.get('hard_note', '')
    g['HEADLINE'] = content.get('headline', {}); g['MESSAGE'] = content.get('message', {})
    g['ITEM_TIP'] = content.get('item_tip', {}); g['PLAN'] = content.get('plan') or None
    g['PLAN_LINK'] = content.get('plan_link', {})

STC = {'稳定掌握': 'good', '已经补上': 'fix', '考试失分': 'warn', '需要关注': 'bad'}
STDESC = {'稳定掌握': '课堂会、考试也拿下', '已经补上': '课堂有错，考试已做对', '考试失分': '课堂会，考试丢分', '需要关注': '课堂和考试都有失分'}
e = html.escape
def pct(x): return f'{round(x*100)}%'
def fmt(x): return f'{x:g}'

# ---------------- tiers ----------------
def tiers(d):
    weak_l = {L['no'] for L in d['lect'] if L['status'] == '需要关注'}
    t1, t2 = [], []
    for x in d['lost']:
        if x['kind'] != '全班难题' and (x['kind'] == '个人漏洞' or x['lect'] in weak_l): t1.append(x)
        else: t2.append(x)
    p1 = sum(x['lost'] for x in t1)
    p2 = sum(x['lost'] * (0.5 if x['kind'] == '全班难题' else 1) for x in t2)
    def lects(xs):
        seen = []
        for x in sorted(xs, key=lambda x: -x['lost']):
            if x['lect'] not in seen and x['kind'] != '全班难题': seen.append(x['lect'])
        return seen[:2]
    good = sorted([L for L in d['lect'] if L['status'] in ('稳定掌握', '已经补上')], key=lambda L: (-L['exam'], -(L['exam'] - L['cls'])))[:2]
    return [
        dict(key='t1', name='优先补', sub='个人漏洞：全班多数做对的题', pts=p1, items=t1, lects=lects(t1)),
        dict(key='t2', name='建议巩固', sub='常规失分与全班难题', pts=round(p2 * 2) / 2, items=t2, lects=lects(t2), hard=any(x['kind'] == '全班难题' for x in t2)),
        dict(key='t3', name='保持拔高', sub='已经掌握的强项', pts=None, items=[], lects=[L['no'] for L in good], good=good),
    ]

def lname(no): return LMAP.get(no, no)

# ---------------- SVG charts ----------------
def radar(d, size=330, label=13):
    cx = cy = size / 2; R = size / 2 - 58
    n = len(d['lect'])
    def pt(i, r): a = -math.pi / 2 + i * 2 * math.pi / n; return cx + R * r * math.cos(a), cy + R * r * math.sin(a)
    g = []
    for ring in (0.25, 0.5, 0.75, 1):
        g.append('<polygon points="%s" fill="none" stroke="var(--line)" stroke-width="1"/>' % ' '.join('%.1f,%.1f' % pt(i, ring) for i in range(n)))
    for i in range(n):
        x, y = pt(i, 1); g.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="var(--line)"/>')
    cp = ' '.join('%.1f,%.1f' % pt(i, L['cls']) for i, L in enumerate(d['lect']))
    mp = ' '.join('%.1f,%.1f' % pt(i, max(L['exam'], .02)) for i, L in enumerate(d['lect']))
    g.append(f'<polygon points="{cp}" fill="var(--cls-soft)" stroke="var(--cls)" stroke-width="1.6" stroke-dasharray="4 3"/>')
    g.append(f'<polygon points="{mp}" fill="var(--me-soft)" stroke="var(--me)" stroke-width="2.4" stroke-linejoin="round"/>')
    for i, L in enumerate(d['lect']):
        x, y = pt(i, max(L['exam'], .02)); g.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.6" fill="var(--me)" stroke="#fff" stroke-width="1.4"/>')
        lx, ly = pt(i, 1.0)
        dx = (lx - cx); anchor = 'middle' if abs(dx) < 5 else ('start' if dx > 0 else 'end')
        ox = 0 if anchor == 'middle' else (8 if anchor == 'start' else -8)
        oy = -12 if ly < cy - 5 else (20 if ly > cy + 5 else 4)
        if abs(dx) >= 5: oy = -2 if ly < cy else 12
        g.append(f'<text x="{lx+ox:.1f}" y="{ly+oy:.1f}" text-anchor="{anchor}" font-size="{label}" fill="var(--ink)" font-weight="700">{e(lname(d["lect"][i]["no"]))}</text>')
        g.append(f'<text x="{lx+ox:.1f}" y="{ly+oy+label+1:.1f}" text-anchor="{anchor}" font-size="{label-2}" fill="var(--me-ink)" font-weight="700">{pct(L["exam"])}<tspan fill="var(--muted)" font-weight="400"> / 班 {pct(L["cls"])}</tspan></text>')
    pad=48
    return f'<svg viewBox="{-pad} 0 {size+2*pad} {size}" width="100%" style="max-width:{size+2*pad}px;display:block;margin:0 auto">{"".join(g)}</svg>'

def dist(d, w=360, h=150):
    bins = list(reversed(CLS['bins']))  # 低 -> 高
    mx = max(c for _, c in bins) or 1
    bw = w / len(bins); g = []
    for i, (lab, c) in enumerate(bins):
        me = lab == d['bin']
        bh = (h - 76) * c / mx; x = i * bw + 8; y = h - 24 - bh
        col = 'var(--me)' if me else 'var(--cls-bar)'
        g.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw-16:.1f}" height="{max(bh,2):.1f}" rx="5" fill="{col}"/>')
        g.append(f'<text x="{x+(bw-16)/2:.1f}" y="{y-6:.1f}" text-anchor="middle" font-size="12" fill="{"var(--me-ink)" if me else "var(--muted)"}" font-weight="700">{c}人</text>')
        g.append(f'<text x="{x+(bw-16)/2:.1f}" y="{h-6}" text-anchor="middle" font-size="12" fill="{"var(--ink)" if me else "var(--muted)"}" font-weight="{700 if me else 400}">{lab}</text>')
        if me:
            fx = x + (bw - 16) / 2
            g.append(f'<g transform="translate({fx:.1f},{y-34:.1f})"><line x1="0" y1="0" x2="0" y2="14" stroke="var(--me)" stroke-width="2"/><path d="M0 0 L22 5 L0 10 Z" fill="var(--me)"/></g>')
    return f'<svg viewBox="0 0 {w} {h}" width="100%">{"".join(g)}</svg>'

def bars(d, w=360):
    rows = []
    for t in CLS['types']:
        me, c = d['types'][t], CLS['types'][t]
        rows.append(f'''<div class="tb"><span class="tl">{t}题</span><div class="tt">
          <div class="trk"><i style="width:{me*100:.1f}%;background:var(--me)"></i></div>
          <div class="trk sm"><i style="width:{c*100:.1f}%;background:var(--cls)"></i></div></div>
          <span class="tv"><b>{pct(me)}</b><small>班 {pct(c)}</small></span></div>''')
    return ''.join(rows)

def qgrid(d):
    lost_kind = {}
    for x in d['lost']:
        q = x['q']; lost_kind.setdefault(q, set()).add(x['kind'])
    cells = []
    for q in d['q18']:
        r = q['got'] / q['full']
        cls = 'full' if r >= 1 else ('zero' if r == 0 else 'part')
        ks = lost_kind.get(q['q'], set())
        tag = '<em class="k-hard">难</em>' if '全班难题' in ks else ('<em class="k-me">漏</em>' if '个人漏洞' in ks else '')
        cells.append(f'<div class="qc {cls}"><b>{q["q"]}</b><span>{fmt(q["got"])}/{fmt(q["full"])}</span><small>班 {pct(q["cls"])}</small>{tag}</div>')
    return ''.join(cells)

def traj(d):
    rows = []
    for L in d['lect']:
        dots = ''.join(f'<i class="{"y" if v else "n"}" title="{e(k)}"></i>' for v, k in zip(L['exit'], L['exit_kp']))
        st = L['status']
        rows.append(f'''<div class="tr-row">
          <div class="tr-name"><b>{L["no"]}</b><span>{lname(L["no"])}</span></div>
          <div class="tr-exit"><div class="dots">{dots}</div><small>{sum(L["exit"])}/{len(L["exit"])}</small></div>
          <div class="tr-arrow">→</div>
          <div class="tr-exam"><div class="trk"><i style="width:{max(L["exam"],.01)*100:.1f}%"></i><u style="left:{L["cls"]*100:.1f}%"></u></div><small><b>{pct(L["exam"])}</b> · 班 {pct(L["cls"])}</small></div>
          <div class="chip {STC[st]}">{st}</div></div>''')
    return ''.join(rows)

def tier_cards(d, compact=False):
    out = []
    T = tiers(d)
    for t in T:
        if t['key'] == 't3':
            if not t['good']: continue
            body = '、'.join(f'{L["no"]}{lname(L["no"])}（{pct(L["exam"])}）' for L in t['good'])
            kid = f'这两讲已经是孩子的优势：{body}。继续保持，课上可以主动挑战拓展题和压轴题。' if len(t['good']) > 1 else f'{body}已经是孩子的优势，继续保持，课上可以主动挑战拓展题。'
            par = '多肯定孩子在这些内容上的进步，具体地夸，比如"这一讲你考了满分"，这比笼统的"真棒"更能建立信心。'
            out.append(f'<div class="tier t3"><div class="th"><span class="tn">第三层 · {t["name"]}</span><span class="tp">保持优势</span></div><p class="ts">{t["sub"]}</p><div class="tdo"><b>孩子怎么做</b><p>{kid}</p></div><div class="tdo"><b>家长怎么配合</b><p>{par}</p></div></div>')
            continue
        idx = '第一层' if t['key'] == 't1' else '第二层'
        if not t['items']:
            out.append(f'<div class="tier {t["key"]}"><div class="th"><span class="tn">{idx} · {t["name"]}</span><span class="tp">无</span></div><p class="ts">这一层没有需要处理的失分，非常好。</p></div>')
            continue
        srt = sorted(t['items'], key=lambda x: -x['lost'])
        items = '；'.join(f'第{x["id"]}题 {e(x["kp"])}（丢 {fmt(x["lost"])} 分）' for x in srt[:5])
        if len(srt) > 5: items += f'；另有 {len(srt)-5} 处小失分，合计 {fmt(sum(x["lost"] for x in srt[5:]))} 分'
        advs = [ADVICE[l] for l in t['lects']]
        tips = []
        for x in sorted(t['items'], key=lambda x: -x['lost']):
            tp = ITEM_TIP.get(x['id'], '')
            if tp not in tips: tips.append(tp)
        kid = '<ul>' + ''.join(f'<li>{e(tp)}</li>' for tp in tips[:4]) + '</ul>' if tips else ''
        par = ' '.join(a['parent'] for a in advs[:1]) if advs else ''
        if t.get('hard'):
            par = (par + ' ' if par else '') + HARD_NOTE
            if not tips: kid = '难题部分先把能拿的步骤分拿到，课上认真听讲评，把解题思路整理到错题本上。'
        out.append(f'''<div class="tier {t["key"]}"><div class="th"><span class="tn">{idx} · {t["name"]}</span><span class="tp">补上可多拿 <b>{fmt(t["pts"])}</b> 分</span></div>
          <p class="ts">{t["sub"]}</p><p class="ti">{items}</p>
          {'<div class="tdo"><b>孩子怎么做</b><div class="tk">'+kid+'</div></div>' if kid else ''}
          {'<div class="tdo"><b>家长怎么配合</b><p>'+par+'</p></div>' if par else ''}</div>''')
    return ''.join(out)

def tags(d):
    best = max(d['lect'], key=lambda L: (L['exam'], L['exam'] - L['cls']))
    cand = [L for L in d['lect'] if L['status'] in ('需要关注', '考试失分')]
    weak = min(cand, key=lambda L: L['exam'] - L['cls']) if cand else None
    t = [('最强一讲', f'{lname(best["no"])} {pct(best["exam"])}', 'good')]
    t.append(('待提升', f'{lname(weak["no"])} {pct(weak["exam"])}' if weak else '暂无明显短板', 'warn'))
    t.append(('提分潜力', f'+{fmt(d["potential"])} 分', 'me'))
    return t


def plan_link(d):
    cand = [L for L in d['lect'] if L['status'] in ('需要关注', '考试失分') and L['lost'] > 0]
    if not cand: return PLAN_LINK.get('_default', '')
    w = max(cand, key=lambda L: (L['status'] == '需要关注', L['lost']))
    return PLAN_LINK.get(w['no']) or PLAN_LINK.get('_default', '')


CSS = '''
:root{
 --ink:#1f2b45; --ink2:#434e67; --muted:#5f6880; --line:#e3e7ef; --panel:#f5f7fb; --paper:#fff;
 --me:#e8622b; --me-ink:#b04c1c; --me-soft:rgba(240,112,60,.15); --cls:#9aa4b7; --cls-soft:rgba(154,164,183,.14); --cls-bar:#d9dee8;
 --good:#217a50; --good-soft:#e5f4ec; --warn:#8a5a00; --warn-soft:#fbf1da; --bad:#b33b37; --bad-soft:#fbe8e7;
 --fix:#2f62c0; --fix-soft:#e7eefb;
 --serif:"Noto Serif CJK SC",serif; --sans:"Noto Sans CJK SC",sans-serif;
 /* 5 级字号 */
 --f-hero:46px; --f-h:16px; --f-sub:12.5px; --f-body:11px; --f-note:10px;
 --s:1;
}
@page{size:A4;margin:0}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:var(--sans);color:var(--ink);font-size:var(--f-body);line-height:1.6;font-variant-numeric:tabular-nums;-webkit-print-color-adjust:exact}
.page{width:210mm;height:297mm;padding:11mm 12mm 9mm;display:flex;flex-direction:column;page-break-after:always;overflow:hidden;position:relative}
.page:last-child{page-break-after:auto}
.ph{display:flex;justify-content:space-between;align-items:baseline;border-bottom:1px solid var(--line);padding-bottom:6px;font-size:var(--f-note);color:var(--muted)}
.ph b{color:var(--ink);font-size:var(--f-sub)}
.pf{display:flex;justify-content:space-between;border-top:1px solid var(--line);padding-top:5px;font-size:var(--f-note);color:var(--muted);margin-top:6px}
.body{flex:1;display:flex;flex-direction:column;gap:calc(16px*var(--s));overflow:hidden;padding-top:calc(10px*var(--s))}
/* 封面抬头 */
.cover{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:2px solid var(--ink);padding-bottom:9px}
.cover .org{font-size:var(--f-note);color:var(--fix);font-weight:700;letter-spacing:.08em}
.cover h1{font-family:var(--serif);font-size:24px;font-weight:900;margin-top:2px;letter-spacing:.02em}
.cover .mt{display:grid;grid-template-columns:auto auto;gap:0 12px;font-size:var(--f-note);color:var(--muted);text-align:right}
.cover .mt b{color:var(--ink);font-weight:500;font-size:var(--f-body)}
/* 模块标题 */
.mod{display:flex;flex-direction:column;gap:calc(9px*var(--s))}
.mh{display:flex;align-items:baseline;gap:10px}
.mh h2{font-family:var(--serif);font-size:var(--f-h);font-weight:900;white-space:nowrap}
.mh h2 i{font-style:normal;color:var(--me-ink);margin-right:6px}
.mh span{font-size:var(--f-note);color:var(--muted)}
.sub{font-size:var(--f-sub);font-weight:700}
.note{font-size:var(--f-note);color:var(--muted);line-height:1.55}
/* 模块一 */
.m1{display:grid;grid-template-columns:200px 150px 1fr;gap:16px;align-items:stretch;min-height:calc(120px + 20px*var(--s))}
.score{background:var(--panel);border-radius:10px;padding:12px 14px;display:flex;flex-direction:column;justify-content:space-between}
.score .big{font-family:var(--serif);font-weight:900;font-size:var(--f-hero);line-height:1;color:var(--me)}
.score .big small{font-size:var(--f-sub);color:var(--muted);font-weight:600;margin-left:3px}
.score .rows{display:flex;flex-direction:column;gap:3px;font-size:var(--f-body);color:var(--ink2)}
.score .rows div{display:flex;justify-content:space-between}
.score .rows b{color:var(--ink)}
.up{color:var(--good)!important}.down{color:var(--bad)!important}
.tags{display:flex;flex-direction:column;gap:6px}
.tag{flex:1;border-radius:10px;padding:6px 11px;display:flex;flex-direction:column;justify-content:center}
.tag small{font-size:var(--f-note);color:var(--ink2)}
.tag b{font-size:var(--f-sub);font-weight:900}
.tag.good{background:var(--good-soft)}.tag.good b{color:var(--good)}
.tag.warn{background:var(--warn-soft)}.tag.warn b{color:var(--warn)}
.tag.me{background:var(--me-soft)}.tag.me b{color:var(--me-ink)}
.distw{display:flex;flex-direction:column;justify-content:flex-end}
.summary{font-size:var(--f-sub);padding:8px 12px;border-radius:8px;background:var(--panel);color:var(--ink)}
.summary b{color:var(--me-ink)}
/* 模块二 */
.m2{display:grid;grid-template-columns:340px 1fr;gap:18px;align-items:center}
.lg{display:flex;gap:14px;font-size:var(--f-note);color:var(--muted);justify-content:center;margin-top:2px}
.lg i{display:inline-block;width:12px;height:3px;border-radius:2px;vertical-align:middle;margin-right:4px}
.cmpt{width:100%;border-collapse:collapse}
.cmpt td{padding:calc(3px*var(--s)) 0;font-size:var(--f-body);border-bottom:1px solid var(--line)}
.cmpt td.n{width:78px;font-weight:700}
.cmpt td.v{width:44px;text-align:right}
.cmpt td.v b{color:var(--me-ink)}.cmpt td.v.c{color:var(--muted)}
.cmpt td.d{width:50px;text-align:right}
.dl{font-size:var(--f-note);font-weight:700;border-radius:4px;padding:0 5px}
.dl.up{background:var(--good-soft)}.dl.down{background:var(--bad-soft)}.dl.eq{background:var(--panel);color:var(--muted)}
.cmpt .trk2{height:6px;background:var(--panel);border-radius:3px;position:relative;margin:0 10px}
.cmpt .trk2 i{position:absolute;left:0;top:0;bottom:0;border-radius:3px;background:var(--me)}
.cmpt .trk2 u{position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--ink);margin-left:-1px}
.tb{display:grid;grid-template-columns:42px 1fr 74px;gap:8px;align-items:center}
.tb .tl{font-weight:700}
.tb .trk{height:8px;background:var(--panel);border-radius:4px;overflow:hidden}
.tb .trk i{display:block;height:100%;border-radius:4px}
.tb .trk.sm{height:5px;margin-top:3px}
.tb .tv{text-align:right;font-size:var(--f-note);color:var(--muted)}
.tb .tv b{font-size:var(--f-sub);color:var(--me-ink);margin-right:3px}
.qg{display:grid;grid-template-columns:repeat(9,1fr);gap:6px}
.qc{border-radius:7px;padding:calc(3px + 3px*var(--s)) 2px;text-align:center;display:flex;flex-direction:column;position:relative;line-height:1.3}
.qc b{font-size:var(--f-sub)}.qc span{font-size:var(--f-note);font-weight:700}.qc small{font-size:9.5px;color:var(--muted)}
.qc.full{background:var(--good-soft)}.qc.full b,.qc.full span{color:var(--good)}
.qc.part{background:var(--warn-soft)}.qc.part b,.qc.part span{color:var(--warn)}
.qc.zero{background:var(--bad-soft)}.qc.zero b,.qc.zero span{color:var(--bad)}
.qc em{position:absolute;top:3px;right:3px;font-style:normal;font-size:9px;font-weight:700;color:#fff;border-radius:3px;padding:0 3px;line-height:13px}
.k-hard{background:var(--muted)}.k-me{background:var(--bad)}
.ql{display:flex;gap:14px;flex-wrap:wrap;font-size:var(--f-note);color:var(--muted)}
.ql span{display:inline-flex;align-items:center;gap:4px;white-space:nowrap}
.ql i{width:10px;height:10px;border-radius:3px;display:inline-block}
.ql em{font-style:normal;color:#fff;border-radius:3px;padding:0 3px;font-size:9px;line-height:13px}
/* 模块三 */
.trt{width:100%;border-collapse:collapse}
.trt th{font-size:var(--f-note);color:var(--muted);font-weight:400;text-align:left;padding-bottom:4px;border-bottom:1px solid var(--line)}
.trt td{padding:calc(5px*var(--s)) 0;border-bottom:1px solid var(--line);vertical-align:middle}
.trt .nm b{font-weight:400;color:var(--muted);font-size:var(--f-note);margin-right:5px}.trt .nm span{font-weight:700;font-size:var(--f-sub)}
.dots{display:inline-flex;gap:3px;vertical-align:middle;margin-right:6px}.dots i{width:9px;height:9px;border-radius:50%}
.dots .y{background:var(--good)}.dots .n{background:var(--bad-soft);border:1.5px solid var(--bad)}
.trt small{font-size:var(--f-note);color:var(--muted)}
.ex{display:grid;grid-template-columns:1fr 78px;gap:8px;align-items:center;padding-right:14px}
.trt td.wr{font-size:var(--f-note);color:var(--ink2);line-height:1.45;padding-right:8px}.trt td.wr .ok{color:var(--good)}
.ex .trk{height:8px;background:var(--panel);border-radius:4px;position:relative}
.ex .trk i{position:absolute;left:0;top:0;bottom:0;border-radius:4px;background:var(--me)}
.ex .trk u{position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--ink);margin-left:-1px}
.ex b{color:var(--me-ink);font-size:var(--f-sub)}
.chip{display:inline-block;font-size:var(--f-note);font-weight:700;border-radius:10px;padding:1px 9px;white-space:nowrap}
.chip.good{background:var(--good-soft);color:var(--good)}.chip.fix{background:var(--fix-soft);color:var(--fix)}
.chip.warn{background:var(--warn-soft);color:var(--warn)}.chip.bad{background:var(--bad-soft);color:var(--bad)}
.legend{display:grid;grid-template-columns:repeat(4,auto);justify-content:start;gap:4px 18px;font-size:var(--f-note);color:var(--muted)}
.legend span{display:flex;align-items:center;gap:6px;white-space:nowrap}
/* 模块四 */
.lt{width:100%;border-collapse:collapse}
.lt th{font-size:var(--f-note);color:var(--muted);font-weight:400;text-align:left;padding:4px 6px;background:var(--panel)}
.lt td{padding:calc(4px*var(--s)) 6px;border-bottom:1px solid var(--line)}
.lt .c{text-align:center}.lt th.c{text-align:center}.lt .g{color:var(--muted)}
.lt td.sc{font-weight:700;color:var(--bad)}
.k{font-size:var(--f-note);font-weight:700;border-radius:4px;padding:1px 6px;white-space:nowrap}
.k.bad{background:var(--bad-soft);color:var(--bad)}.k.warn{background:var(--warn-soft);color:var(--warn)}.k.mu{background:var(--panel);color:var(--muted)}
.lt tr.more td{color:var(--muted);font-size:var(--f-note)}
.tiers{display:flex;flex-direction:column;border-top:1px solid var(--line)}
.tr{display:grid;grid-template-columns:118px 1fr;gap:16px;padding:calc(10px*var(--s)) 0;border-bottom:1px solid var(--line)}
.tr .tl{display:flex;flex-direction:column;gap:3px}
.tr .tl .chip{width:fit-content}
.tr .tl b{font-family:var(--serif);font-size:var(--f-h);font-weight:900}
.tr .tl small{font-size:var(--f-note);color:var(--muted);line-height:1.4}
.tr .tl em{font-style:normal;font-size:var(--f-note);color:var(--ink2)}
.tr .tl em b{font-family:var(--sans);font-size:var(--f-sub);color:var(--me-ink)}
.tr .tc{display:flex;flex-direction:column;gap:5px}
.tr .its{font-size:var(--f-note);color:var(--ink2);background:var(--panel);border-radius:6px;padding:5px 9px;line-height:1.6}
.tr .two{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.tr .two h3{font-size:var(--f-body);font-weight:700;margin-bottom:2px}
.tr ul{padding-left:14px}.tr li,.tr p{font-size:var(--f-body);color:var(--ink2);line-height:1.6}
/* 失分构成 */
.comp{display:grid;grid-template-columns:1fr 1fr;gap:26px;align-items:start}
.lbs{display:flex;flex-direction:column;gap:4px}
.lb{display:grid;grid-template-columns:64px 1fr 34px;gap:8px;align-items:center;font-size:var(--f-note)}
.lb .trk{height:8px;background:var(--panel);border-radius:4px;overflow:hidden}.lb .trk i{display:block;height:100%;background:var(--bad);border-radius:4px}
.lb b{text-align:right;color:var(--bad);font-size:var(--f-body)}
.stack{display:flex;height:14px;border-radius:7px;overflow:hidden;background:var(--panel)}.stack i{display:block;height:100%}
.kls{display:flex;flex-direction:column;gap:3px;margin-top:8px}
.kl{display:grid;grid-template-columns:10px 1fr auto;gap:7px;align-items:center;font-size:var(--f-body)}
.kl i{width:10px;height:10px;border-radius:3px}.kl b{font-size:var(--f-body)}
/* 模块五 */
.plan{display:flex;flex-direction:column;gap:calc(9px*var(--s))}
.ptop{display:flex;justify-content:space-between;align-items:flex-end;gap:12px}
.ptop b{font-family:var(--serif);font-size:var(--f-sub);font-weight:900;color:var(--fix)}
.ptop span{font-size:var(--f-note);color:var(--muted)}
.why{font-size:var(--f-body);background:var(--me-soft);border-radius:8px;padding:7px 11px;color:var(--ink)}
.why b{color:var(--me-ink)}
.stgs{display:grid;grid-template-columns:5fr 3fr 3fr;gap:8px}
.stg{background:var(--panel);border-radius:8px;padding:8px 10px}
.stg .sh{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:5px}
.stg .sh b{font-size:var(--f-sub)}.stg .sh span{font-size:var(--f-note);color:var(--muted)}
.stg ol{list-style:none;display:flex;flex-direction:column;gap:2px}
.stg li{display:flex;gap:7px;align-items:baseline;font-size:var(--f-body)}
.stg li i{font-style:normal;font-size:var(--f-note);color:var(--fix);font-weight:700;width:30px;flex:none}
.gns{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.gn b{font-size:var(--f-body);color:var(--fix);display:block}.gn span{font-size:var(--f-note);color:var(--ink2);line-height:1.5}
.cta{font-size:var(--f-note);color:var(--muted)}
/* 模块六 */
.msg{font-family:var(--serif);font-size:var(--f-sub);line-height:1.95;color:var(--ink);border-left:3px solid var(--me);padding:2px 0 2px 14px}
.sign{text-align:right;color:var(--muted);font-size:var(--f-body);margin-top:4px}
'''

def ph(d, n, total):
    return f'<div class="ph"><span><b>{e(d["name"])}</b>　{KIND}学情报告</span><span>{META["cls"]}｜{campus()}｜{META["teacher"]}</span></div>'
def pf(n, total):
    return f'<div class="pf"><span>{META["org"]}｜{META["title"]}</span><span>第 {n} 页 / 共 {total} 页</span></div>'

def m1(d):
    g = d['grade']; diff = d['diff']
    tg = ''.join(f'<div class="tag {c}"><small>{a}</small><b>{b}</b></div>' for a, b, c in tags(d))
    return f'''<div class="mod"><div class="mh"><h2><i>一</i>成绩总览与班级位置</h2><span>全班 {CLS["n"]} 人，班级平均 {CLS["avg"]} 分，报告不做排名</span></div>
<div class="m1">
 <div class="score"><div class="big">{fmt(d["total"])}<small>/ {fmt(CLS["full"])}</small></div>
  <div class="rows"><div><span>对比班均</span><b class="{'up' if diff>=0 else 'down'}">{'+' if diff>=0 else '−'}{abs(diff):.1f} 分</b></div>
   <div><span>成绩等级</span><b>{g[0]}　{g[1]}</b></div><div><span>出门测答对</span><b>{d["exit_total"]} / {d["exit_n"]}</b></div></div></div>
 <div class="tags">{tg}</div>
 <div class="distw">{dist(d, 300, 132)}<div class="note" style="text-align:center">全班分数分布，旗帜为孩子所在分数段</div></div>
</div>
<div class="summary"><b>一句话总结</b>　{e(HEADLINE.get(d["name"], ""))}</div></div>'''

def m2(d):
    rows = ''
    for L in d['lect']:
        df = round((L['exam'] - L['cls']) * 100)
        cl = 'up' if df > 0 else ('down' if df < 0 else 'eq')
        rows += f'''<tr><td class="n">{lname(L["no"])}</td><td><div class="trk2"><i style="width:{max(L["exam"],.01)*100:.1f}%"></i><u style="left:{L["cls"]*100:.1f}%"></u></div></td>
<td class="v"><b>{pct(L["exam"])}</b></td><td class="v c">{pct(L["cls"])}</td><td class="d"><span class="dl {cl}">{'+' if df>0 else ''}{df}</span></td></tr>'''
    tb = ''
    for t in CLS['types']:
        me, c = d['types'][t], CLS['types'][t]
        tb += f'''<div class="tb"><span class="tl">{t}题</span><div><div class="trk"><i style="width:{me*100:.1f}%;background:var(--me)"></i></div><div class="trk sm"><i style="width:{c*100:.1f}%;background:var(--cls)"></i></div></div><span class="tv"><b>{pct(me)}</b>班 {pct(c)}</span></div>'''
    return f'''<div class="mod"><div class="mh"><h2><i>二</i>和班级平均比一比</h2><span>橙色为孩子，灰色为班级平均</span></div>
<div class="m2"><div>{radar(d, 318, 11.5)}<div class="lg"><span><i style="background:var(--me)"></i>{e(d["name"])}</span><span><i style="background:var(--cls)"></i>班级平均</span></div></div>
 <div style="display:flex;flex-direction:column;gap:12px">
  <div><div class="sub" style="margin-bottom:4px">{cn(len(d["lect"]))}讲得分率</div>
   <table class="cmpt"><tbody>{rows}</tbody></table>
   <div class="note" style="margin-top:3px">竖线为班级平均，右侧数字为与班均相差的百分点</div></div>
  <div><div class="sub" style="margin-bottom:6px">{cn(len(CLS["types"]))}类题型得分率</div><div style="display:flex;flex-direction:column;gap:6px">{tb}</div></div>
 </div></div>
<div class="sub">{len(d["q18"])} 道题逐题得分</div>
<div class="qg">{qgrid(d)}</div>
<div class="ql"><span><i style="background:var(--good-soft);border:1px solid var(--good)"></i>满分</span><span><i style="background:var(--warn-soft);border:1px solid var(--warn)"></i>部分得分</span><span><i style="background:var(--bad-soft);border:1px solid var(--bad)"></i>未得分</span><span><em class="k-me">漏</em>全班多数做对、孩子失分</span><span><em class="k-hard">难</em>全班难题</span><span>「班」为全班得分率</span></div></div>'''

def m3(d):
    rows = ''
    for L in d['lect']:
        dots = ''.join(f'<i class="{"y" if v else "n"}"></i>' for v in L['exit'])
        rows += f'''<tr><td class="nm"><b>{L["no"]}</b><span>{lname(L["no"])}</span></td><td><span class="dots">{dots}</span><small>{sum(L["exit"])}/{len(L["exit"])}</small></td>
<td><div class="ex"><div class="trk"><i style="width:{max(L["exam"],.01)*100:.1f}%"></i><u style="left:{L["cls"]*100:.1f}%"></u></div><span><b>{pct(L["exam"])}</b> <small>班 {pct(L["cls"])}</small></span></div></td>
<td class="wr">{'、'.join(k for v,k in zip(L["exit"],L["exit_kp"]) if not v) or '<span class="ok">全部答对</span>'}</td>
<td style="text-align:right"><span class="chip {STC[L["status"]]}">{L["status"]}</span></td></tr>'''
    legend = ''.join(f'<span><span class="chip {STC[s]}">{s}</span>{STDESC[s]}</span>' for s in ['稳定掌握', '已经补上', '考试失分', '需要关注'])
    return f'''<div class="mod"><div class="mh"><h2><i>三</i>从课堂到考试</h2><span>出门测为每讲课尾 10 分钟的随堂测验</span></div>
<div class="note" style="font-size:var(--f-body);color:var(--ink2)">出门测反映孩子当堂听懂了多少，{KIND}考试检验一段时间后还记得多少。两者对照，就能看出哪些已经学扎实、哪些还要再练。</div>
<table class="trt"><thead><tr><th style="width:96px">讲次</th><th style="width:96px">出门测</th><th style="width:190px">{KIND}得分率（竖线为班均）</th><th>出门测出错的知识点</th><th style="width:76px;text-align:right">结论</th></tr></thead><tbody>{rows}</tbody></table>
<div class="legend">{legend}</div><div class="note">出门测一栏中，绿点为答对、红圈为答错。</div></div>'''

def m4a(d, cap):
    lost = sorted(d['lost'], key=lambda x: (x['kind'] != '个人漏洞', x['kind'] == '全班难题', -x['lost']))
    krow = {'个人漏洞': 'bad', '常规失分': 'warn', '全班难题': 'mu'}
    show, rest = lost[:cap], lost[cap:]
    rows = ''.join(f'''<tr><td class="c"><b>{x["id"]}</b></td><td>{e(x["kp"])}</td><td class="c g">{x["lect"]}</td><td class="c sc">{fmt(x["got"])} / {x["full"]}</td><td class="c">{pct(x["cls"])}</td><td class="c"><span class="k {krow[x["kind"]]}">{x["kind"]}</span></td></tr>''' for x in show)
    if rest: rows += f'<tr class="more"><td></td><td colspan="5">另有 {len(rest)} 处失分（{"、".join(x["id"] for x in rest)}），合计 {fmt(sum(x["lost"] for x in rest))} 分</td></tr>'
    if not lost: rows = '<tr><td colspan="6" class="c">本次没有失分题</td></tr>'
    bylec = [(lname(L['no']), L['lost']) for L in d['lect']]
    mx = max([v for _, v in bylec] + [1])
    lecbars = ''.join(f'<div class="lb"><span>{n}</span><div class="trk"><i style="width:{v/mx*100:.1f}%"></i></div><b>{fmt(v)}</b></div>' for n, v in bylec)
    kinds = [('个人漏洞', 'var(--bad)'), ('常规失分', 'var(--warn)'), ('全班难题', 'var(--cls)')]
    tot = sum(x['lost'] for x in lost) or 1
    seg = ''.join(f'<i style="width:{sum(x["lost"] for x in lost if x["kind"]==k)/tot*100:.2f}%;background:{c}"></i>' for k, c in kinds)
    kl = ''.join(f'<div class="kl"><i style="background:{c}"></i><span>{k}</span><b>{fmt(sum(x["lost"] for x in lost if x["kind"]==k))} 分</b></div>' for k, c in kinds)
    comp = f'''<div class="comp"><div><div class="sub" style="margin-bottom:5px">失分来自哪几讲</div><div class="lbs">{lecbars}</div></div>
<div><div class="sub" style="margin-bottom:5px">失分属于哪一类</div><div class="stack">{seg}</div><div class="kls">{kl}</div>
<div class="note" style="margin-top:6px">红色部分是最该优先补上的分数，灰色部分全班普遍失分，不必过度担心。</div></div></div>'''
    return f'''<div class="mod"><div class="mh"><h2><i>四</i>失分分析</h2><span>共 {len(lost)} 个得分点有失分，提分潜力 +{fmt(d["potential"])} 分</span></div>
<table class="lt"><thead><tr><th class="c" style="width:52px">题号</th><th>考察知识点</th><th class="c" style="width:56px">讲次</th><th class="c" style="width:56px">得分</th><th class="c" style="width:70px">全班得分率</th><th class="c" style="width:70px">类型</th></tr></thead><tbody>{rows}</tbody></table>
{comp}
<div class="note">个人漏洞：全班得分率不低于 80%；常规失分：60%–80%；全班难题：低于 60%。提分潜力按个人漏洞和常规失分全额、全班难题一半计算。</div></div>'''

def m4b(d, nit, ntip):
    T = tiers(d); out = ''; used = set()
    lab = {'t1': ('bad', '第一层'), 't2': ('warn', '第二层'), 't3': ('good', '第三层')}
    for t in T:
        c, idx = lab[t['key']]
        if t['key'] == 't3':
            if not t['good']: continue
            body = '、'.join(f'{lname(L["no"])}（{pct(L["exam"])}）' for L in t['good'])
            kid = f'{body}已经是孩子的优势，继续保持，课上可以主动挑战拓展题和压轴题。'
            par = '具体地肯定孩子的进步，比如"这一讲你考了满分"，比笼统的"真棒"更能建立信心。'
            pts = '<em>保持优势</em>'
        elif not t['items']:
            out += f'<div class="tr"><div class="tl"><span class="chip {c}">{idx}</span><b>{t["name"]}</b></div><div class="tc"><p>这一层没有需要处理的失分，非常好。</p></div></div>'
            continue
        else:
            srt = sorted(t['items'], key=lambda x: -x['lost'])
            its = '；'.join(f'第 {x["id"]} 题 {e(x["kp"])}' for x in srt[:nit]) + (f' 等 {len(srt)} 处' if len(srt) > nit else '')
            tips = []
            for x in srt:
                tp = ITEM_TIP.get(x['id'], '')
                if tp and tp not in tips: tips.append(tp)
            kid = '<ul>' + ''.join(f'<li>{e(tp)}</li>' for tp in tips[:ntip]) + '</ul>'
            cand = [l for l in t['lects']] + [x['lect'] for x in srt if x['kind'] != '全班难题']
            par = next((ADVICE.get(l, {}).get('parent', '') for l in cand if ADVICE.get(l, {}).get('parent') and ADVICE[l]['parent'] not in used), '')
            used.add(par)
            if t.get('hard'): par = (par + ' ' if par else '') + HARD_NOTE
            pts = f'<em>补上可多拿 <b>{fmt(t["pts"])}</b> 分</em>'
        itsh = f'<div class="its">{its}</div>' if t['key'] != 't3' else ''
        kidh = kid if kid.startswith('<ul>') else f'<p>{kid}</p>'
        out += f'''<div class="tr"><div class="tl"><span class="chip {c}">{idx}</span><b>{t["name"]}</b><small>{t["sub"]}</small>{pts}</div>
<div class="tc">{itsh}<div class="two"><div><h3>孩子怎么做</h3>{kidh}</div><div><h3>家长怎么配合</h3><p>{par}</p></div></div></div></div>'''
    return f'''<div class="mod"><div class="mh"><h2><i>四</i>下阶段建议</h2><span>按重要程度分三层，先补第一层</span></div><div class="tiers">{out}</div></div>'''

def m5(d):
    stages = ''.join(f'''<div class="stg"><div class="sh"><b>{s["name"]}</b><span>{s["map"]}</span></div><ol>{''.join(f'<li><i>第{n}讲</i>{t}</li>' for n, t in s["lects"])}</ol></div>''' for s in PLAN['stages'])
    gains = ''.join(f'<div class="gn"><b>{a}</b><span>{b}</span></div>' for a, b in PLAN['gains'])
    return f'''<div class="mod"><div class="mh"><h2><i>五</i>{e(PLAN.get("heading") or "后续课程规划")}</h2><span>{PLAN["title"]}，{PLAN["setup"]}</span></div>
<div class="plan"><div class="ptop"><b>{PLAN["theme"]}</b></div>
<div class="why"><b>和孩子本次表现的关系</b>　{e(plan_link(d))}</div>
<div class="stgs">{stages}</div><div class="gns">{gains}</div>
<div class="cta">具体排课时间与班级安排，欢迎咨询{META["teacher"]}。</div></div></div>'''

def m6(d):
    return f'''<div class="mod"><div class="mh"><h2><i>{'六' if PLAN else '五'}</i>老师寄语</h2></div>
<div class="msg">{e(MESSAGE.get(d["name"], ""))}<div class="sign">—— {META["teacher"]}</div></div></div>'''

def doc(d, cap=9, nit=4, ntip=3):
    cover = f'''<div class="cover"><div><h1>{e(d["name"])} 同学 · {KIND}学情分析</h1></div>
<div class="mt"><span>机构</span><b>{META["org"]}</b><span>班型</span><b>{META["cls"]}</b><span>校区</span><b>{campus()}</b><span>授课教师</span><b>{META["teacher"]}</b><span>测试范围</span><b>{META["range"]}</b></div></div>'''
    p1 = f'<section class="page" id="p1">{cover}<div class="body">{m1(d)}{m2(d)}</div>{pf(1,3)}</section>'
    p2 = f'<section class="page" id="p2">{ph(d,2,3)}<div class="body">{m3(d)}{m4a(d,cap)}</div>{pf(2,3)}</section>'
    p3 = f'<section class="page" id="p3">{ph(d,3,3)}<div class="body">{m4b(d,nit,ntip)}{m5(d) if PLAN else ""}{m6(d)}</div>{pf(3,3)}</section>'
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>{p1}{p2}{p3}</body></html>'

FIT_JS = '''() => [...document.querySelectorAll('.page .body')].map(b => {
  const kids=[...b.children]; const cs=getComputedStyle(b); const gap=parseFloat(cs.rowGap)||0;
  const used = kids.reduce((a,k)=>a+k.getBoundingClientRect().height,0) + gap*(kids.length-1) + parseFloat(cs.paddingTop);
  return {avail:b.clientHeight, used:Math.round(used)} })'''

def fit_page(pg, idx, lo=0.5, hi=1.45):
    """二分查找该页间距系数 --s，使内容填满且不溢出"""
    sel = f'#p{idx+1} .body'
    def measure(s):
        pg.evaluate(f"document.querySelector('{sel}').style.setProperty('--s','{s}')")
        r = pg.evaluate(FIT_JS)[idx]; return r['used'], r['avail']
    used, avail = measure(hi)
    if used <= avail: return hi, used / avail
    a, b = lo, hi
    for _ in range(14):
        m = (a + b) / 2; u, _ = measure(m)
        if u <= avail - 4: a = m
        else: b = m
    u, _ = measure(a)
    return a, u / avail

def build(names, outdir, workdir, progress=None, keys=None):
    """逐个学生排版并导出 PDF；返回 {姓名: pdf路径}。progress(i, n) 用于汇报进度。"""
    from playwright.sync_api import sync_playwright
    os.makedirs(outdir, exist_ok=True); os.makedirs(workdir, exist_ok=True); res_map = {}
    with sync_playwright() as p:
        br = p.chromium.launch(); pg = br.new_page(viewport={'width': 794, 'height': 1123})
        for k, n in enumerate(names):
            d = A['students'][n]
            key = keys[n] if keys else k
            html_path = os.path.join(workdir, f'{key}.html')
            for cap, nit, ntip in [(9, 4, 3), (8, 3, 3), (7, 3, 2), (6, 2, 2)]:
                open(html_path, 'w', encoding='utf-8').write(doc(d, cap, nit, ntip))
                pg.goto('file://' + os.path.abspath(html_path)); pg.wait_for_timeout(120)
                res = [fit_page(pg, i, hi=h) for i, h in zip(range(3), (2.4, 2.4, 2.2))]
                if all(f <= 1.0 for _, f in res): break
            pdf = os.path.join(outdir, f'{key}.pdf')
            pg.pdf(path=pdf, width='210mm', height='297mm', print_background=True, prefer_css_page_size=True)
            res_map[n] = pdf
            if progress: progress(k + 1, len(names))
        br.close()
    return res_map
