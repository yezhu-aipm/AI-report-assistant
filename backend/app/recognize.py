"""识别四类材料，合并成一份结构化数据。表格类文件直接解析；图片、PDF、Word 试卷交给视觉模型。"""
import os, re, json
from . import llm, tables, config
from .tables import norm_id, qnum

IMG_EXT = ('jpg', 'jpeg', 'png', 'webp', 'bmp', 'heic')
TABLE_EXT = ('xlsx', 'xlsm', 'csv')

def ext(name): return name.lower().rsplit('.', 1)[-1]

def to_images(path, name, max_pages=8):
    """图片原样读入；PDF 每页转成图片。返回 [(bytes, mime)]。"""
    e = ext(name)
    if e in IMG_EXT:
        data = open(path, 'rb').read()
        if e in ('heic', 'bmp', 'webp'):
            from PIL import Image; import io
            im = Image.open(io.BytesIO(data)).convert('RGB'); buf = io.BytesIO(); im.save(buf, 'JPEG', quality=90); data = buf.getvalue()
            return [(data, 'image/jpeg')]
        return [(data, 'image/png' if e == 'png' else 'image/jpeg')]
    if e == 'pdf':
        import pymupdf
        doc = pymupdf.open(path); out = []
        for p in list(doc)[:max_pages]:
            out.append((p.get_pixmap(matrix=pymupdf.Matrix(2, 2)).tobytes('jpeg'), 'image/jpeg'))
        return out
    return []

def parts_for(files):
    """把一类材料的所有文件转成发给模型的内容：图片 part + Word 文本。"""
    parts = []
    for f in files:
        e = ext(f['name'])
        if e == 'docx':
            parts.append({'type': 'text', 'text': f'【文件 {f["name"]} 的文字内容】\n' + tables.docx_text(f['path'])[:20000]})
        else:
            for data, mime in to_images(f['path'], f['name']): parts.append(llm.image_part(data, mime))
    return parts

def table_rows(files):
    for f in files:
        if ext(f['name']) in TABLE_EXT or ext(f['name']) == 'docx':
            rows = tables.read_rows(f['path'], f['name'])
            if rows: return rows
    return None

# ---------------- prompts ----------------
SYS = '你是教培机构的教务助理，负责把老师上传的材料准确录入成结构化数据。只录入看到的内容，不推测、不补全；看不清的地方如实标出。只输出 JSON。'

def llm_grade(files):
    parts = parts_for(files) + [{'type': 'text', 'text': '''这是一份逐题成绩表。请输出：
{"cls":"表头上的班级名称，没有就空字符串","exam":"考试名称，没有就空字符串",
 "labels":["按表格从左到右的每个得分点题号，如 1、2、14(1)"],
 "full":[每个得分点的满分，表里没有就 null],
 "students":[{"name":"姓名","scores":[与 labels 对应的得分，空白填 null],"total":表中总分或 null}],
 "uncertain":[{"name":"姓名","label":"题号"}]}
uncertain 列出字迹模糊、你没把握的格子。'''}]
    r = llm.chat_json(SYS, parts, config.LLM_VISION_MODEL)
    labels = [norm_id(x) for x in r.get('labels', [])]
    students, scores, official, blanks = [], {}, {}, []
    for s in r.get('students', []):
        n = str(s.get('name', '')).replace(' ', '')
        if not n: continue
        vals = (s.get('scores') or []) + [None] * len(labels)
        students.append(n); official[n] = s.get('total')
        scores[n] = [float(v) if isinstance(v, (int, float)) else 0 for v in vals[:len(labels)]]
        blanks += [{'stu': n, 'k': k} for k, v in enumerate(vals[:len(labels)]) if not isinstance(v, (int, float))]
    low = [{'stu': str(u.get('name', '')).replace(' ', ''), 'k': labels.index(norm_id(u.get('label', '')))} for u in r.get('uncertain', []) if norm_id(u.get('label', '')) in labels]
    full = r.get('full') if r.get('full') and any(isinstance(v, (int, float)) for v in r['full']) else None
    meta = {k: r[k] for k in ('cls', 'exam') if r.get(k)}
    return dict(labels=labels, full=full, students=students, scores=scores, official=official, blanks=blanks, low=low, meta=meta)

def llm_exit(files):
    parts = parts_for(files) + [{'type': 'text', 'text': '''这是一份出门测记录表（每讲课尾的随堂小测）。✔/√ 表示答对，×/✗ 表示答错。请输出：
{"lectures":[{"no":"第1讲","name":"讲次名称","short":"2~5 个字的简称","kps":["该讲每个知识点，按从左到右顺序"]}],
 "students":[{"name":"姓名","marks":[[第1讲每个知识点 1 或 0],[第2讲…]]}],
 "uncertain":[{"name":"姓名","lecture":讲次序号从0开始,"index":知识点序号从0开始}]}
「正确率」「合计」之类的统计列不要录入。'''}]
    r = llm.chat_json(SYS, parts, config.LLM_VISION_MODEL)
    lectures = [dict(no=L.get('no') or f'第{i + 1}讲', name=L.get('name') or '', short=L.get('short') or tables.short_name(L.get('name') or ''), kps=[str(k) for k in L.get('kps', [])]) for i, L in enumerate(r.get('lectures', []))]
    students, marks = [], {}
    for s in r.get('students', []):
        n = str(s.get('name', '')).replace(' ', '')
        if not n: continue
        students.append(n)
        m = s.get('marks') or []
        marks[n] = [[1 if (m[l][j] if l < len(m) and j < len(m[l]) else 0) else 0 for j in range(len(L['kps']))] for l, L in enumerate(lectures)]
    low = [{'stu': str(u.get('name', '')).replace(' ', ''), 'l': u.get('lecture', 0), 'j': u.get('index', 0)} for u in r.get('uncertain', [])]
    return dict(lectures=lectures, students=students, marks=marks, blanks=[], low=low)

def llm_paper(files, lectures, labels):
    lect_txt = '\n'.join(f'{i}. {L["no"]} {L["name"]}：{"、".join(L["kps"])}' for i, L in enumerate(lectures))
    parts = parts_for(files) + [{'type': 'text', 'text': f'''这是一份考试试卷。成绩表里的得分点题号是：{"、".join(labels) or "（未提供）"}。
本阶段的讲次和知识点如下（序号从 0 开始）：
{lect_txt}

请为每个得分点输出：
{{"items":[{{"id":"与成绩表一致的题号","type":"选择/填空/判断/计算/解答 之一","full":分值,"kp":"考察的知识点，12 个字以内，说清考的是什么","lect":所属讲次序号}}]}}
题号以成绩表为准；试卷上找不到的题 full 填 null。lect 选最贴近的一讲。'''}]
    r = llm.chat_json(SYS, parts, config.LLM_VISION_MODEL)
    return [dict(id=norm_id(i.get('id', '')), type=i.get('type') or '解答', full=i.get('full'), kp=i.get('kp') or '', lect=i.get('lect')) for i in r.get('items', [])]

def llm_lect_map(items, lectures):
    """题目表里只写了讲次名称或没写时，让模型按知识点归到讲次。"""
    lect_txt = '\n'.join(f'{i}. {L["no"]} {L["name"]}：{"、".join(L["kps"])}' for i, L in enumerate(lectures))
    it_txt = '\n'.join(f'{x["id"]}：{x["kp"]}' for x in items)
    r = llm.chat_json(SYS, f'讲次（序号从 0 开始）：\n{lect_txt}\n\n题目和知识点：\n{it_txt}\n\n把每道题归到最贴近的一讲，输出 {{"map":{{"题号":讲次序号}}}}', config.LLM_TEXT_MODEL)
    return r.get('map', {})

def llm_plan(files):
    parts = parts_for(files) + [{'type': 'text', 'text': '''这是机构下一阶段的课程大纲。请整理成：
{"heading":"如 寒假课程规划、春季课程规划","title":"课程名称，如 2026 寒假小组课 · 预初逻辑 · 卓越班","theme":"一句话主题，20 字以内",
 "setup":"课时安排，如 7 节专题学习 + 3 节复习与测试，共 10 讲",
 "stages":[{"name":"阶段名称","map":"对标教材章节，没有就空字符串","lects":[["讲次编号","讲次标题"]]}],
 "gains":[["两到三个字的收获标签","一句话说明"]]}
stages 最多 4 个，gains 正好 4 条。只用大纲里有的信息。'''}]
    return llm.chat_json(SYS, parts, config.LLM_VISION_MODEL)

# ---------------- mock fallbacks（未配置大模型时） ----------------
def mock_paper(labels, lectures, full):
    out = []
    for k, i in enumerate(labels):
        q = qnum(i)
        out.append(dict(id=i, type='解答' if '(' in i else ('选择' if q <= 5 else '填空'), full=(full[k] if full and k < len(full) else None), kp=f'第 {i} 题（演示模式占位）', lect=min(len(lectures) - 1, k * len(lectures) // max(1, len(labels))) if lectures else None))
    return out

# ---------------- 主流程 ----------------
def run(files_by_kind, log):
    """files_by_kind: {paper:[...], grade:[...], exit:[...], plan:[...]}；log(text, step, state) 汇报进度。返回 data。"""
    data = {'notes': []}
    # 1. 出门测（先做，试卷归讲次要用到它）
    log('读取出门测记录表', 'exit', 'on')
    rows = table_rows(files_by_kind['exit'])
    if rows is not None:
        ex = tables.parse_exit(rows); src = '表格'
    elif llm.enabled():
        ex = llm_exit(files_by_kind['exit']); src = '图片识别'
    else:
        raise ValueError('演示模式下只能读取 Excel / Word 表格。请上传表格，或在 .env 里配置大模型 Key')
    log(f'出门测：{src}，{len(ex["lectures"])} 讲、{sum(len(L["kps"]) for L in ex["lectures"])} 个知识点、{len(ex["students"])} 名学生', 'exit', 'ok',
        f'识别出 {len(ex["lectures"])} 讲、{sum(len(L["kps"]) for L in ex["lectures"])} 个知识点')
    # 2. 成绩表
    log('读取逐题成绩表', 'grade', 'on')
    rows = table_rows(files_by_kind['grade'])
    if rows is not None:
        gr = tables.parse_grade(rows); gr['low'] = []; src = '表格'
    elif llm.enabled():
        gr = llm_grade(files_by_kind['grade']); src = '图片识别'
    else:
        raise ValueError('演示模式下只能读取 Excel / Word 表格。请上传表格，或在 .env 里配置大模型 Key')
    log(f'成绩表：{src}，{len(gr["students"])} 名学生 × {len(gr["labels"])} 个得分点', 'grade', 'ok', f'识别出 {len(gr["students"])} 名学生、{len(gr["labels"])} 个得分点')
    # 3. 试卷
    log('读取考试试卷', 'paper', 'on')
    labels, lectures = gr['labels'], ex['lectures']
    rows = table_rows(files_by_kind['paper'])
    items = None
    ptab = tables.parse_paper_table(rows) if rows else None
    if ptab:
        items = ptab; src = '题目表'
        name_to_idx = {}
        for i, L in enumerate(lectures):
            for key in (L['no'], L['name'], L['short']): name_to_idx[key.replace(' ', '')] = i
        need = []
        for it in items:
            ln = (it.pop('lect_name', '') or '').replace(' ', '')
            m = re.match(r'(第\d+讲)', ln)
            it['lect'] = name_to_idx.get(ln, name_to_idx.get(m.group(1) if m else '', None))
            if it['lect'] is None: need.append(it)
        if need and llm.enabled():
            mp = llm_lect_map(need, lectures)
            for it in need:
                v = mp.get(it['id']); it['lect'] = v if isinstance(v, int) and 0 <= v < len(lectures) else None
    elif llm.enabled():
        items = llm_paper(files_by_kind['paper'], lectures, labels); src = '图片识别'
    else:
        items = mock_paper(labels, lectures, gr.get('full')); src = '演示占位'
        data['notes'].append('演示模式：试卷没有经过大模型识别，题型、知识点和讲次是占位内容。配置大模型 Key 后会自动识别。')
    log(f'试卷：{src}，{len(items)} 个得分点', 'paper', 'ok', f'识别出 {len({qnum(i["id"]) for i in items})} 道题、{len(items)} 个得分点')
    # 合并：得分点顺序以成绩表为准
    by_id = {i['id']: i for i in items}
    merged = []
    for k, lab in enumerate(labels or [i['id'] for i in items]):
        it = by_id.get(lab, {})
        full = it.get('full')
        if full is None and gr.get('full') and k < len(gr['full']): full = gr['full'][k]
        lect = it.get('lect')
        merged.append(dict(id=lab, q=qnum(lab), type=it.get('type') or ('解答' if '(' in lab else '填空'), full=float(full) if isinstance(full, (int, float)) else None,
                           kp=it.get('kp') or '', lect=lect if isinstance(lect, int) and 0 <= lect < len(lectures) else None))
    # 4. 课程大纲（选填）
    plan = None
    if files_by_kind['plan']:
        log('读取续报课程大纲', 'plan', 'on')
        if llm.enabled():
            plan = llm_plan(files_by_kind['plan'])
            log(f'课程大纲：{len(plan.get("stages", []))} 个阶段', 'plan', 'ok', f'识别出 {len(plan.get("stages", []))} 个阶段、{sum(len(s.get("lects", [])) for s in plan.get("stages", []))} 讲')
        else:
            log('演示模式：课程大纲需要大模型识别，本次报告不含课程规划', 'plan', 'ok', '演示模式下跳过')
            data['notes'].append('演示模式：课程大纲没有识别，报告不含课程规划模块。')
    else:
        log('未上传课程大纲，报告不含课程规划', 'plan', 'ok', '未上传，报告不含课程规划')
    exit_marks = {}
    for n in gr['students']:
        exit_marks[n] = ex['marks'].get(n)
    data.update(lectures=lectures, items=merged, students=gr['students'], scores=gr['scores'], official=gr['official'],
                exit=exit_marks, exit_extra=[n for n in ex['students'] if n not in gr['students']], plan=plan,
                low=[dict(x, kind='grade') for x in gr.get('low', [])] + [dict(x, kind='exit') for x in ex.get('low', [])],
                blanks=[dict(x, kind='grade') for x in gr.get('blanks', [])] + [dict(x, kind='exit') for x in ex.get('blanks', [])],
                meta_guess=gr.get('meta', {}), resolved={}, seen={})
    return data
