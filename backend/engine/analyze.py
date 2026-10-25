"""成绩分析：只用规则计算，不调用大模型。同样的输入永远得到同样的结果。

输入 batch（dict）：
  meta:     {org, campus, teacher, cls, title, range, kind}
  lectures: [{no:'第1讲', name:'整除综合进阶', short:'整除', kps:[知识点...]}]
  items:    [{id:'14(1)', type:'解答', full:4, kp:'...', lect:0, q:14}]   lect 为讲次下标，q 为大题号
  scores:   {姓名: [每个得分点的得分]}
  official: {姓名: 表中总分或 None}
  exit:     {姓名: [[每讲每个知识点 1/0]]}
"""
TYPE_ORDER = ['选择', '判断', '填空', '计算', '解答', '应用', '综合']
BINS = [('90–100', 90, 101), ('80–89', 80, 90), ('70–79', 70, 80), ('60–69', 60, 70), ('60以下', 0, 60)]

def r1(x): return round(x + 1e-9, 1)
def kind(rate): return '全班难题' if rate < 0.6 else ('个人漏洞' if rate >= 0.8 else '常规失分')
def grade(x): return ('A', '优秀') if x >= 90 else ('B', '良好') if x >= 80 else ('C', '中等') if x >= 70 else ('D', '合格') if x >= 60 else ('E', '待提升')
def status(e, x):
    if x >= 0.8 and e >= 0.6: return '稳定掌握'
    if x >= 0.8: return '已经补上'
    if e >= 0.6: return '考试失分'
    return '需要关注'

def analyze(b):
    items, lects = b['items'], b['lectures']
    N = list(b['scores']); NI = len(items); LN = len(lects)
    FULL = [float(i['full']) for i in items]
    S = {n: [min(float(v or 0), FULL[k]) for k, v in enumerate(s[:NI])] + [0.0] * (NI - len(s)) for n, s in b['scores'].items()}
    EXIT = {}
    for n in N:
        rows = (b.get('exit') or {}).get(n) or []
        EXIT[n] = [[1 if v else 0 for v in (rows[l] if l < len(rows) else [])][:len(lects[l]['kps'])] + [0] * max(0, len(lects[l]['kps']) - len(rows[l] if l < len(rows) else [])) for l in range(LN)]
    total_full = sum(FULL)
    scale = 100 / total_full if total_full else 1          # 非百分制按百分制折算分数段与等级
    cls_rate = [sum(S[n][k] for n in N) / len(N) / FULL[k] if FULL[k] else 1 for k in range(NI)]
    tot = {n: sum(S[n]) for n in N}; avg = sum(tot.values()) / len(N)
    lfull = [sum(FULL[k] for k in range(NI) if items[k]['lect'] == l) for l in range(LN)]
    def lrate(n, l): return sum(S[n][k] for k in range(NI) if items[k]['lect'] == l) / lfull[l] if lfull[l] else 0
    present = [t for t in TYPE_ORDER if any(i['type'] == t for i in items)] + sorted({i['type'] for i in items} - set(TYPE_ORDER))
    tfull = {t: sum(FULL[k] for k in range(NI) if items[k]['type'] == t) for t in present}
    def trate(n, t): return sum(S[n][k] for k in range(NI) if items[k]['type'] == t) / tfull[t]
    def erate(n, l): L = EXIT[n][l]; return sum(L) / len(L) if L else 0
    cls_l = [sum(lrate(n, l) for n in N) / len(N) for l in range(LN)]
    cls_t = {t: sum(trate(n, t) for n in N) / len(N) for t in present}
    cls_e = [sum(erate(n, l) for n in N) / len(N) for l in range(LN)]
    bins = [sum(1 for n in N if a <= tot[n] * scale < c) for _, a, c in BINS]
    qs = []
    for i in items:
        if i['q'] not in qs: qs.append(i['q'])
    out = {'meta': b['meta'], 'class': dict(avg=r1(avg), n=len(N), full=total_full, bins=[(x[0], c) for x, c in zip(BINS, bins)],
        lect=[dict(no=lects[l]['no'], name=lects[l]['name'], short=lects[l].get('short') or lects[l]['name'], full=lfull[l], exam=cls_l[l], exit=cls_e[l]) for l in range(LN)],
        types={t: cls_t[t] for t in present}, item_rate=cls_rate), 'students': {}}
    for n in N:
        s = S[n]; lost = []
        for k in range(NI):
            if s[k] < FULL[k]:
                it = items[k]
                lost.append(dict(id=it['id'], q=it['q'], type=it['type'], kp=it['kp'], lect=lects[it['lect']]['no'], got=s[k], full=FULL[k], lost=FULL[k] - s[k], cls=cls_rate[k], kind=kind(cls_rate[k])))
        pot = sum(x['lost'] * (0.5 if x['kind'] == '全班难题' else 1) for x in lost)
        lect = []
        for l in range(LN):
            x = lrate(n, l); e = erate(n, l)
            ctrl = sum(FULL[k] - s[k] for k in range(NI) if items[k]['lect'] == l and cls_rate[k] >= 0.6)
            xc = 1 - ctrl / lfull[l] if lfull[l] else 1
            lect.append(dict(no=lects[l]['no'], name=lects[l]['name'], full=lfull[l], got=sum(s[k] for k in range(NI) if items[k]['lect'] == l), exam=x, cls=cls_l[l],
                exit=EXIT[n][l], exit_kp=lects[l]['kps'], exit_rate=e, exit_cls=cls_e[l], status=status(e, xc),
                lost=sum(FULL[k] - s[k] for k in range(NI) if items[k]['lect'] == l)))
        qrows = []
        for q in qs:
            ks = [k for k in range(NI) if items[k]['q'] == q]
            g = sum(s[k] for k in ks); f = sum(FULL[k] for k in ks); c = sum(cls_rate[k] * FULL[k] for k in ks) / f if f else 1
            qrows.append(dict(q=q, got=g, full=f, cls=c, type=items[ks[0]]['type']))
        t = tot[n]; ts = t * scale
        out['students'][n] = dict(name=n, total=t, official=(b.get('official') or {}).get(n), diff=t - avg, grade=grade(ts),
            bin=next(x[0] for x in BINS if x[1] <= ts < x[2]), types={tt: trate(n, tt) for tt in present}, lect=lect, lost=lost,
            potential=round(pot * 2) / 2, q18=qrows, exit_total=sum(sum(L) for L in EXIT[n]), exit_n=sum(len(L) for L in EXIT[n]))
    return out
