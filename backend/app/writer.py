"""报告文字：一句话总结、老师寄语、各讲建议、逐题提示、课程规划关联。
数字全部来自分析结果，大模型只负责把结论写成家长听得懂的话。"""
import json
from . import llm, config

def nick(n): return n[-2:] if len(n) >= 3 else n
def pct(x): return f'{round(x * 100)}%'
def fmt(x): return '%g' % x

STYLE = '''写作要求：
- 读者是家长。口吻像带班老师，温和、具体、不说空话，不用感叹号堆砌。
- 只用给到的数据，不编造分数、排名或事实。报告不做排名，不要出现"第几名"。
- 提到题目用「第 N 题」，提到分数写具体数字，中文和数字之间留一个空格。
- 不出现"优秀学生""学霸""差生"这类标签，不贬低孩子，也不过度夸张。'''

EXAMPLE_HEAD = '三讲考出满分，基础扎实，稳住细节就能冲上 90 分'
EXAMPLE_MSG = '一航这次考了 88.5 分，比班级平均高 5 分多。整除、分数、有理数运算三讲在期中拿了满分，基础非常扎实。丢掉的分里，第 17 题库存计算的 4 分和代数式书写规范的 3 分最可惜，都是会做却没拿稳的题。接下来把审题和书写规范抓一抓，90 分以上很有希望。'

def student_brief(d, A):
    L = d['lect']
    lost = sorted(d['lost'], key=lambda x: -x['lost'])[:6]
    return dict(name=d['name'], call=nick(d['name']), total=d['total'], full=A['class']['full'], class_avg=A['class']['avg'], diff=round(d['diff'], 1),
                potential=d['potential'], exit=f'{d["exit_total"]}/{d["exit_n"]}',
                lectures=[dict(lect=f'{x["no"]}{x["name"]}', exam=pct(x['exam']), class_avg=pct(x['cls']), exit=pct(x['exit_rate']), status=x['status']) for x in L],
                biggest_losses=[dict(q=f'第 {x["id"]} 题', kp=x['kp'], lost=x['lost'], type=x['kind'], class_rate=pct(x['cls'])) for x in lost])

def class_brief(A):
    items = {}
    for d in A['students'].values():
        for x in d['lost']: items.setdefault(x['id'], dict(id=x['id'], kp=x['kp'], lect=x['lect'], class_rate=pct(x['cls']), type=x['kind']))
    return dict(lectures=[dict(no=L['no'], name=L['name'], exam=pct(L['exam']), exit=pct(L['exit'])) for L in A['class']['lect']], lost_items=list(items.values()))

# ---------------- 大模型版本 ----------------
def llm_class(A, plan):
    cb = class_brief(A)
    plan_txt = json.dumps(plan, ensure_ascii=False) if plan else '无'
    r = llm.chat_json('你是一位经验丰富的数学老师，给家长写学情报告。' + STYLE, f'''本次考试全班情况：
{json.dumps(cb, ensure_ascii=False)}

下一阶段课程大纲：{plan_txt}

请输出 JSON：
{{"advice":{{"讲次编号如 第1讲":{{"kid":"孩子怎么做，2~3 句，给具体方法","parent":"家长怎么配合，1~2 句，可在家里做的小事"}}}},
 "item_tip":{{"题号":"针对这道题的一句提示，40 字以内，告诉孩子具体怎么避免丢分"}},
 "hard_note":"一句话安抚：全班得分率低于 60% 的题老师会在课上集中讲评（列出题号）。没有这类题就输出空字符串",
 "plan_link":{{"讲次编号":"如果孩子这一讲最薄弱，下一阶段课程和它有什么关系，一句话，50 字以内", "_default":"孩子各讲都掌握得好时的一句话"}}}}
item_tip 要覆盖 lost_items 里的每一道题。没有课程大纲时 plan_link 输出空对象。''', config.LLM_TEXT_MODEL, temperature=0.5)
    return r

def llm_students(A, names):
    out = {}
    for i in range(0, len(names), 5):
        group = [student_brief(A['students'][n], A) for n in names[i:i + 5]]
        r = llm.chat_json('你是一位经验丰富的数学老师，给家长写学情报告。' + STYLE, f'''请为下面每位学生写两段话：
- headline：一句话总结，16~28 个字，抓住这个孩子最突出的一点和下一步方向。例：{EXAMPLE_HEAD}
- message：老师寄语，150~220 个字，用 call 字段称呼孩子。先肯定做得好的具体地方，再指出最可惜的失分（具体题号和分数），最后给下一步建议。例：{EXAMPLE_MSG}

学生数据：
{json.dumps(group, ensure_ascii=False)}

输出 JSON：{{"students":[{{"name":"姓名","headline":"…","message":"…"}}]}}''', config.LLM_TEXT_MODEL, temperature=0.7)
        for s in r.get('students', []):
            if s.get('name') in A['students']: out[s['name']] = s
    return out

# ---------------- 模板版本（演示模式 / 大模型失败时兜底） ----------------
def mock_class(A, plan):
    adv = {}
    for L in A['class']['lect']:
        nm = L['short']
        adv[L['no']] = dict(kid=f'把{nm}这一讲的错题重新做一遍，每一步写清依据；再找两道同类题限时练习，确认真正掌握。',
                            parent=f'请孩子给您讲一讲{nm}里做错的一道题，讲得清楚、算得对，就说明这一讲补上了。')
    tips, hard = {}, []
    rates = {}
    for d in A['students'].values():
        for x in d['lost']: rates[x['id']] = x
    for i, x in rates.items():
        tips[i] = f'回到「{x["kp"]}」的课堂例题，对照答案找出出错的那一步，整理进错题本。' if x['kp'] else '对照答案找出出错的那一步，整理进错题本。'
        if x['cls'] < 0.6: hard.append(i)
    note = f'第 {"、".join(hard[:4])} 题是本次全班得分率最低的题，老师会在课上集中讲评，家长不必过度担心。' if hard else ''
    pl = {'_default': '孩子本阶段基础扎实，下一阶段课程可以在此基础上继续拓展提高。'} if plan else {}
    if plan:
        for L in A['class']['lect']: pl[L['no']] = f'下一阶段课程会持续用到{L["short"]}的方法，正好帮助孩子补上本次在这一讲的失分。'
    return dict(advice=adv, item_tip=tips, hard_note=note, plan_link=pl)

def mock_student(d, A):
    c = nick(d['name']); diff = d['diff']
    good = sorted([L for L in d['lect'] if L['status'] in ('稳定掌握', '已经补上')], key=lambda L: -L['exam'])
    full_l = [L for L in d['lect'] if L['exam'] >= 0.999]
    lost = sorted([x for x in d['lost'] if x['kind'] != '全班难题'], key=lambda x: -x['lost'])
    weak = sorted([L for L in d['lect'] if L['status'] in ('需要关注', '考试失分')], key=lambda L: L['exam'] - L['cls'])
    def sh(L): return L.get('short') or L['name']
    lmap = {L['no']: L for L in A['class']['lect']}
    if full_l: head = f'{"、".join(sh(lmap[L["no"]]) for L in full_l[:2])}拿到满分，' + (f'{sh(lmap[weak[0]["no"]])}是接下来的提分点' if weak else '保持细心继续拔高')
    elif weak: head = f'{sh(lmap[good[0]["no"]]) if good else "基础题"}掌握得不错，{sh(lmap[weak[0]["no"]])}是接下来的突破口'
    else: head = '各讲掌握均衡，稳住细节还能再进一步'
    s1 = f'{c}这次考了 {fmt(d["total"])} 分，比班级平均{"高" if diff >= 0 else "低"} {abs(diff):.1f} 分。'
    s2 = (f'{"、".join(sh(lmap[L["no"]]) for L in good[:2])}掌握得比较扎实，' if good else '') + f'出门测答对 {d["exit_total"]} / {d["exit_n"]} 个知识点。'
    s3 = f'丢分里最可惜的是第 {lost[0]["id"]} 题{lost[0]["kp"] and "（" + lost[0]["kp"] + "）"}的 {fmt(lost[0]["lost"])} 分' + (f'和第 {lost[1]["id"]} 题的 {fmt(lost[1]["lost"])} 分' if len(lost) > 1 else '') + '，属于能拿回来的分。' if lost else '这次没有出现全班多数做对而孩子丢分的题，非常难得。'
    s4 = f'接下来先把{sh(lmap[weak[0]["no"]])}这一讲补扎实，按报告里的建议每周练一练，提分潜力还有 {fmt(d["potential"])} 分。' if weak else '接下来可以多接触综合题和拓展题，继续保持这份细心。'
    return dict(name=d['name'], headline=head[:30], message=s1 + s2 + s3 + s4)

# ---------------- 入口 ----------------
def write(A, plan, log=lambda *a: None):
    names = list(A['students'])
    if llm.enabled():
        log('撰写各讲建议和逐题提示')
        try: cls = llm_class(A, plan)
        except Exception as e: log(f'大模型写作失败，改用模板：{e}'); cls = mock_class(A, plan)
        log('撰写每位学生的一句话总结和老师寄语')
        try: st = llm_students(A, names)
        except Exception as e: log(f'大模型写作失败，改用模板：{e}'); st = {}
    else:
        cls, st = mock_class(A, plan), {}
    base = mock_class(A, plan)
    for k in ('advice', 'item_tip', 'plan_link'):   # 模型漏写的条目用模板补齐
        merged = dict(base[k]); merged.update(cls.get(k) or {}); cls[k] = merged
    if not cls.get('hard_note') and base['hard_note'] and llm.enabled() is False: cls['hard_note'] = base['hard_note']
    headline, message = {}, {}
    for n in names:
        s = st.get(n) or mock_student(A['students'][n], A)
        headline[n] = s.get('headline') or mock_student(A['students'][n], A)['headline']
        message[n] = s.get('message') or mock_student(A['students'][n], A)['message']
    content = dict(advice=cls['advice'], item_tip=cls['item_tip'], hard_note=cls.get('hard_note', ''), headline=headline, message=message,
                   plan=plan, plan_link=cls['plan_link'] if plan else {})
    return content

def rewrite_one(A, name):
    if not llm.enabled(): return mock_student(A['students'][name], A)
    return llm_students(A, [name]).get(name) or mock_student(A['students'][name], A)
