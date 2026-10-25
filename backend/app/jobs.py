"""后台任务：识别材料、生成报告、重排单份报告。用线程池跑，排版放在独立子进程里。"""
import json, os, subprocess, sys, threading, time, traceback, logging, shutil
from concurrent.futures import ThreadPoolExecutor
from . import db, recognize, validate, writer
from .config import DATA_DIR

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pool = ThreadPoolExecutor(max_workers=int(os.getenv('WORKERS', '2')))
log = logging.getLogger('jobs')
_locks = {}

def bdir(bid, *p):
    d = os.path.join(DATA_DIR, 'batches', str(bid), *p); os.makedirs(d, exist_ok=True); return d

def lock(bid): return _locks.setdefault(bid, threading.Lock())

def files_by_kind(bid):
    rows = db.q('SELECT * FROM files WHERE batch_id=? ORDER BY id', (bid,))
    out = {k: [] for k in ('paper', 'grade', 'exit', 'plan')}
    for r in rows: out.setdefault(r['kind'], []).append(r)
    return out

def issue_view(d):
    """当前问题 + 之前出现过、现在已经不存在的问题（显示为已处理）。"""
    cur = validate.issues(d); ids = {x['id'] for x in cur}
    seen = d.setdefault('seen', {})
    for x in cur:
        if not x['done']: seen[x['id']] = {k: x[k] for k in ('id', 'lv', 'title', 'tab', 'stu', 'col')}
    for i, x in seen.items():
        if i not in ids: cur.append(dict(x, desc='', actions=[], done=True, how=d.get('resolved', {}).get(i) or '已修改'))
    order = {('r', False): 0, ('y', False): 1}
    cur.sort(key=lambda x: order.get((x['lv'], x['done']), 2))
    return cur

# ---------------- 识别 ----------------
STEPS = [('paper', '考试试卷'), ('grade', '逐题成绩表'), ('exit', '出门测记录表'), ('plan', '续报课程大纲')]

def start_recognize(bid):
    prog = dict(steps=[dict(key=k, label=t, state='wait', summary='等待中') for k, t in STEPS], log=[], error=None)
    db.save_batch(bid, status='recognizing', progress=prog, error=None)
    pool.submit(_recognize, bid)

def _recognize(bid):
    with lock(bid):
        b = db.load_batch(db.one('SELECT * FROM batches WHERE id=?', (bid,)))
        prog = b['progress']
        def lg(text, step=None, state=None, summary=None):
            prog['log'].append(text)
            if step:
                for s in prog['steps']:
                    if s['key'] == step:
                        s['state'] = state or s['state']
                        s['summary'] = summary or ('识别中…' if state == 'on' else s['summary'])
            db.save_batch(bid, progress=prog)
        try:
            data = recognize.run(files_by_kind(bid), lg)
            iss = issue_view(data)
            r = validate.red_count(iss); y = sum(1 for x in iss if x['lv'] == 'y' and not x['done'])
            lg(f'校验完成：{r} 处必须处理，{y} 处提示' if (r or y) else '校验完成：没有发现问题')
            meta = b['meta']
            for k in ('cls', 'exam'):
                if not meta.get(k) and data['meta_guess'].get(k): meta[k] = data['meta_guess'][k]
            db.save_batch(bid, status='check', data=data, issues=iss, meta=meta, progress=prog, content=None, result=None, confirmed=[])
        except Exception as e:
            log.error(traceback.format_exc())
            prog['error'] = str(e); prog['log'].append(f'识别失败：{e}')
            db.save_batch(bid, status='draft', progress=prog, error=str(e))

# ---------------- 生成 ----------------
def meta_for(b):
    m = dict(b['meta'])
    exam = m.get('exam', '')
    m['kind'] = next((k for k in ('期中', '期末', '月考', '单元测', '周测', '阶段测') if k[:2] in exam), '学情') if exam else '期中'
    m.setdefault('range', '')
    if not m.get('range'):
        import re
        nums = [re.sub(r'\D', '', L['no']) for L in b['data']['lectures']]
        m['range'] = f'{nums[0]}–{nums[-1]}讲' if nums and nums[0] and nums[-1] else ''
    m['title'] = m.get('exam', ''); m['cls'] = m.get('cls', '')
    return m

def start_generate(bid):
    prog = dict(phase='writing', done=0, total=0, log=['开始生成'], error=None)
    db.save_batch(bid, status='generating', progress=prog, error=None)
    pool.submit(_generate, bid)

def _engine(bid, analysis, content, names, keys):
    out = bdir(bid, 'out'); work = bdir(bid, 'work')
    job = dict(analysis=analysis, content=content, names=names, keys=keys, outdir=out, workdir=work, result_path=os.path.join(work, f'result-{time.time_ns()}.json'))
    jp = os.path.join(work, 'job.json'); json.dump(job, open(jp, 'w', encoding='utf-8'), ensure_ascii=False)
    pp = os.path.join(out, 'progress.json')
    if os.path.exists(pp): os.remove(pp)
    p = subprocess.Popen([sys.executable, '-m', 'engine.run', jp], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    while p.poll() is None:
        time.sleep(0.7)
        try: yield json.load(open(pp))
        except Exception: pass
    tail = p.stdout.read()[-2000:]
    if p.returncode != 0: raise RuntimeError('排版失败：' + tail)
    yield {'result': json.load(open(job['result_path']))}

def _generate(bid):
    with lock(bid):
        b = db.load_batch(db.one('SELECT * FROM batches WHERE id=?', (bid,)))
        prog = b['progress']
        try:
            from engine.analyze import analyze
            data = b['data']; meta = meta_for(b)
            A = analyze(validate.to_batch(data, meta))
            def lg(t): prog['log'].append(t); db.save_batch(bid, progress=prog)
            content = writer.write(A, data.get('plan'), lg)
            names = list(A['students']); keys = {n: i for i, n in enumerate(names)}
            prog.update(phase='rendering', total=len(names), done=0); lg('排版生成 PDF')
            res = None
            for ev in _engine(bid, A, content, names, keys):
                if 'result' in ev: res = ev['result']
                else: prog.update(done=ev.get('done', 0)); db.save_batch(bid, progress=prog)
            result = dict(analysis=A, keys=keys, version=int(time.time()), files={n: dict(pdf=res['pdfs'][n], previews=res['previews'][n]) for n in names})
            prog.update(phase='done', done=len(names)); prog['log'].append('全部完成')
            db.save_batch(bid, status='review', content=content, result=result, progress=prog, confirmed=[])
        except Exception as e:
            log.error(traceback.format_exc())
            prog['error'] = str(e); prog['log'].append(f'生成失败：{e}')
            db.save_batch(bid, status='check', progress=prog, error=str(e))

def render_one(bid, name):
    """老师改了某位学生的总结或寄语后，只重排这一份。同步执行，几秒钟。"""
    with lock(bid):
        b = db.load_batch(db.one('SELECT * FROM batches WHERE id=?', (bid,)))
        res = b['result']; A = res['analysis']
        for ev in _engine(bid, A, b['content'], [name], {name: res['keys'][name]}):
            if 'result' in ev:
                r = ev['result']; res['files'][name] = dict(pdf=r['pdfs'][name], previews=r['previews'][name])
        res['version'] = int(time.time())
        db.save_batch(bid, result=res)
        return res
