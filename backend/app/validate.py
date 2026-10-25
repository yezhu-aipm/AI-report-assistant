"""逐项校验识别结果。红色问题必须处理才能生成报告，黄色是提示。"""

def fmt(x):
    return ('%g' % x) if isinstance(x, (int, float)) else str(x)

def issues(d):
    items, names, res = d['items'], d['students'], d.get('resolved', {})
    out = []
    def add(id, lv, title, desc, tab='grade', stu=None, col=None, actions=()):
        out.append(dict(id=id, lv=lv, title=title, desc=desc, tab=tab, stu=stu, col=col, actions=list(actions), done=id in res, how=res.get(id)))
    seen = set()
    for n in names:
        if n in seen: add(f'dup:{n}', 'r', f'成绩表里有两个「{n}」', '请在成绩表里给其中一位改名，或删掉重复的一行。')
        seen.add(n)
    for k, it in enumerate(items):
        if it.get('full') is None:
            add(f'full:{k}', 'r', f'第 {it["id"]} 题缺少满分', '试卷和成绩表里都没找到这一小题的分值，请在「题目表」里填写。', 'q', col=k)
        if it.get('lect') is None:
            add(f'lect:{k}', 'r', f'第 {it["id"]} 题还没归到讲次', '请在「题目表」里选择这道题属于哪一讲。', 'q', col=k)
    for n in names:
        s = d['scores'][n]; tot = 0
        for k, it in enumerate(items):
            v = s[k] if k < len(s) else 0; tot += v or 0
            if it.get('full') is not None and v > it['full']:
                add(f'over:{n}:{k}', 'r', f'{n} · 第 {it["id"]} 题得分超过满分', f'表中为 {fmt(v)} 分，这一小题满分 {fmt(it["full"])} 分。请把格子改成正确的分数。',
                    stu=n, col=k, actions=[dict(key='set_full', label=f'改为 {fmt(it["full"])} 分', primary=True)])
        off = d['official'].get(n)
        if off is not None and abs(tot - off) > 1e-6 and not any(x['id'].startswith(f'over:{n}:') for x in out):
            add(f'sum:{n}', 'r', f'{n} · 各题合计与表中总分不一致', f'系统合计 {fmt(tot)} 分，表中总分 {fmt(off)} 分。请检查小题分数，或以系统合计为准。',
                stu=n, actions=[dict(key='use_system', label='以系统合计为准')])
    for b in d.get('blanks', []):
        if b['kind'] == 'grade' and b['stu'] in names:
            k = b['k']; add(f'blank:{b["stu"]}:{k}', 'y', f'{b["stu"]} · 第 {items[k]["id"]} 题是空白', '已按 0 分处理。如果不是 0 分，请直接改格子里的分数。', stu=b['stu'], col=k, actions=[dict(key='ok', label='确认是 0 分')])
    for b in d.get('low', []):
        if b['kind'] == 'grade' and b['stu'] in names and b['k'] < len(items):
            k = b['k']; v = d['scores'][b['stu']][k]
            add(f'low:{b["stu"]}:{k}', 'y', f'{b["stu"]} · 第 {items[k]["id"]} 题识别没把握', f'识别为 {fmt(v)} 分，这一格比较模糊，请确认。', stu=b['stu'], col=k, actions=[dict(key='ok', label='分数正确')])
        if b['kind'] == 'exit':
            add(f'lowx:{b["stu"]}:{b["l"]}:{b["j"]}', 'y', f'{b["stu"]} · 出门测有一格识别没把握', '请到「出门测」里核对这一格，点圆点可以切换对错。', 'exit', stu=b['stu'], actions=[dict(key='ok', label='知道了')])
    for n in names:
        if not d['exit'].get(n):
            add(f'noexit:{n}', 'y', f'出门测表里没有「{n}」', '这位学生的出门测会按未作答处理。如果是名字写法不同，请改成和成绩表一致后重新识别。', 'exit', stu=n, actions=[dict(key='ok', label='知道了')])
    for n in d.get('exit_extra', []):
        add(f'extra:{n}', 'y', f'出门测表里多了「{n}」', '成绩表里没有这位学生，生成报告时会忽略。', 'exit', actions=[dict(key='ok', label='知道了')])
    for i, L in enumerate(d['lectures']):
        if not L['kps']: add(f'kps:{i}', 'r', f'{L["no"]} 没有知识点', '出门测表里这一讲没有读到知识点，请检查表头后重新识别。', 'exit')
    return out

def red_count(iss): return sum(1 for x in iss if x['lv'] == 'r' and not x['done'])

def apply_action(d, issue_id, key):
    """执行问题卡片上的快捷按钮。"""
    if key == 'set_full' and issue_id.startswith('over:'):
        _, n, k = issue_id.split(':'); k = int(k)
        d['scores'][n][k] = d['items'][k]['full']
        return
    d.setdefault('resolved', {})[issue_id] = {'use_system': '以系统合计为准', 'ok': '已确认'}.get(key, '已确认')
    if key == 'use_system' and issue_id.startswith('sum:'):
        d['official'][issue_id[4:]] = None

def to_batch(d, meta):
    """校验通过后转成分析引擎需要的格式。"""
    names = d['students']
    return dict(meta=meta, lectures=d['lectures'], items=d['items'], scores={n: d['scores'][n] for n in names},
                official={n: d['official'].get(n) for n in names},
                exit={n: d['exit'].get(n) or [[0] * len(L['kps']) for L in d['lectures']] for n in names})
