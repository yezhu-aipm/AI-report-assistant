"""学情报告助手 API。前端打包后的静态文件也由这里提供，部署时只需要跑这一个服务。"""
import io, json, os, re, time, zipfile, shutil, logging, secrets
from datetime import datetime
from fastapi import FastAPI, Request, Response, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Any
from . import db, auth, jobs, validate, writer, config, llm, guard

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
app = FastAPI(title='学情报告助手', docs_url='/api/docs', openapi_url='/api/openapi.json')
db.init()
# 服务重启时，把卡在「识别中/生成中」的批次退回上一步，避免一直转圈
for b in db.q("SELECT id, status FROM batches WHERE status IN ('recognizing','generating')"):
    db.save_batch(b['id'], status='draft' if b['status'] == 'recognizing' else 'check', error='服务重启，任务已中断，请重新操作')

Me = Depends(auth.current_user)
def month(): return datetime.now().strftime('%Y-%m')
def used(uid):
    r = db.one('SELECT count FROM usage WHERE user_id=? AND month=?', (uid, month())); return r['count'] if r else 0

@app.exception_handler(HTTPException)
async def http_err(request, exc):
    body = exc.detail if isinstance(exc.detail, dict) else {'error': exc.detail}
    return JSONResponse(body, status_code=exc.status_code)

def user_quota(u): return u['quota'] if u.get('quota') is not None else config.MONTHLY_QUOTA
def invite_code(): return db.get_setting('invite', config.INVITE_CODE) or ''
def next_month_day():
    n = datetime.now(); return f'{n.year + (n.month == 12)}-{n.month % 12 + 1:02d}-01'

# ================= 账号 =================
class Cred(BaseModel):
    username: str; password: str; password2: Optional[str] = None; agree: Optional[bool] = None; name: Optional[str] = None
    invite: Optional[str] = None; cid: Optional[str] = None; captcha: Optional[str] = None

def set_cookie(resp, tok):
    resp.set_cookie(auth.COOKIE, tok, max_age=config.SESSION_DAYS * 86400, httponly=True, samesite='lax', secure=config.COOKIE_SECURE)

PREF_KEYS = ('org', 'campus', 'teacher', 'subject')
def prefs_of(u):
    try: p = json.loads(u.get('prefs') or '{}')
    except Exception: p = {}
    return {k: p.get(k, '') for k in PREF_KEYS}

def fresh(uid): return db.one('SELECT id, username, name, disabled, quota, prefs, created FROM users WHERE id=?', (uid,))

def me_view(u):
    return dict(id=u['id'], username=u['username'], name=u['name'] or u['username'], quota=user_quota(u), used=used(u['id']),
                reset=next_month_day(), llm=llm.enabled(), allow_register=config.ALLOW_REGISTER, admin=auth.is_admin(u), prefs=prefs_of(u))

@app.get('/api/auth/captcha')
def captcha(request: Request):
    guard.rate(request, 'cap', 30, 60)
    return guard.new_captcha()

@app.post('/api/auth/register')
def register(c: Cred, request: Request, response: Response):
    guard.rate(request, 'reg', 10, 3600)
    if not config.ALLOW_REGISTER: raise HTTPException(403, '暂未开放注册')
    guard.check_captcha(c.cid, c.captcha)
    code = invite_code()
    if code and (c.invite or '').strip() != code: raise HTTPException(400, {'error': '邀请码不对，请向管理员确认', 'captcha': True})
    if not auth.USER_RE.match(c.username): raise HTTPException(400, {'error': '账号需要 4–20 位字母或数字', 'captcha': True})
    if len(c.password) < 8: raise HTTPException(400, {'error': '密码至少 8 位', 'captcha': True})
    if c.password2 is not None and c.password2 != c.password: raise HTTPException(400, {'error': '两次输入的密码不一致', 'captcha': True})
    if not c.agree: raise HTTPException(400, {'error': '请先勾选同意用户协议和隐私政策', 'captcha': True})
    if db.one('SELECT id FROM users WHERE username=?', (c.username,)): raise HTTPException(400, {'error': '这个账号已经被注册了', 'captcha': True})
    name = (c.name or '').strip()[:20]
    uid = db.run('INSERT INTO users(username,pw,name,created,prefs) VALUES(?,?,?,?,?)',
                 (c.username, auth.hash_pw(c.password), name, db.now(), json.dumps({'teacher': name, 'subject': '数学'}, ensure_ascii=False)))
    db.run('INSERT INTO folders(user_id,name,sort,created) VALUES(?,?,?,?)', (uid, '示例文件夹', 0, db.now()))
    set_cookie(response, auth.new_session(uid))
    return me_view(fresh(uid))

@app.get('/api/auth/login-state')
def login_state(request: Request, username: str = ''):
    wait, need = guard.login_state(username, guard.client_ip(request)); return {'captcha': need, 'wait': wait}

@app.post('/api/auth/login')
def login(c: Cred, request: Request, response: Response):
    guard.rate(request, 'login', 30, 60)
    ip = guard.client_ip(request)
    wait, need = guard.login_state(c.username, ip)
    if wait: raise HTTPException(429, {'error': f'密码错误次数太多，请 {max(1, (wait + 59) // 60)} 分钟后再试', 'captcha': True})
    if need: guard.check_captcha(c.cid, c.captcha)
    u = db.one('SELECT * FROM users WHERE username=?', (c.username,))
    if not u or not auth.check_pw(c.password, u['pw']):
        guard.login_failed(c.username, ip); raise HTTPException(400, {'error': '账号或密码不对', 'captcha': True})
    if u['disabled']: raise HTTPException(403, '账号已被停用，请联系管理员')
    guard.login_ok(c.username, ip)
    set_cookie(response, auth.new_session(u['id']))
    return me_view(u)

@app.post('/api/auth/logout')
def logout(request: Request, response: Response):
    tok = request.cookies.get(auth.COOKIE)
    if tok: db.run('DELETE FROM sessions WHERE token=?', (tok,))
    response.delete_cookie(auth.COOKIE); return {'ok': True}

@app.get('/api/auth/me')
def me(request: Request):
    try: u = auth.current_user(request)
    except HTTPException: return None          # 未登录返回 null，避免首页控制台报错
    return me_view(u)

class MeIn(BaseModel):
    name: Optional[str] = None; prefs: Optional[dict] = None
@app.patch('/api/auth/me')
def me_update(x: MeIn, u=Me):
    if x.name is not None:
        n = x.name.strip()[:20]
        if not n: raise HTTPException(400, '称呼不能为空')
        db.run('UPDATE users SET name=? WHERE id=?', (n, u['id']))
    if x.prefs is not None:
        p = {k: str(x.prefs.get(k) or '').strip()[:40] for k in PREF_KEYS}
        db.run('UPDATE users SET prefs=? WHERE id=?', (json.dumps(p, ensure_ascii=False), u['id']))
    return me_view(fresh(u['id']))

class PwIn(BaseModel): old: str = ''; new: str = ''
@app.post('/api/auth/password')
def change_pw(x: PwIn, request: Request, u=Me):
    guard.rate(request, 'pw', 10, 600)
    row = db.one('SELECT pw FROM users WHERE id=?', (u['id'],))
    if not auth.check_pw(x.old, row['pw']): raise HTTPException(400, '当前密码不对')
    if len(x.new) < 8: raise HTTPException(400, '新密码至少 8 位')
    if x.new == x.old: raise HTTPException(400, '新密码不能和当前密码一样')
    db.run('UPDATE users SET pw=? WHERE id=?', (auth.hash_pw(x.new), u['id']))
    db.run('DELETE FROM sessions WHERE user_id=? AND token<>?', (u['id'], request.cookies.get(auth.COOKIE, '')))
    return {'ok': True}

@app.post('/api/auth/logout-others')
def logout_others(request: Request, u=Me):
    n = db.one('SELECT COUNT(*) c FROM sessions WHERE user_id=? AND token<>?', (u['id'], request.cookies.get(auth.COOKIE, '')))['c']
    db.run('DELETE FROM sessions WHERE user_id=? AND token<>?', (u['id'], request.cookies.get(auth.COOKIE, '')))
    return {'ok': True, 'n': n}

def wipe_user(uid):
    for b in db.q('SELECT id FROM batches WHERE user_id=?', (uid,)):
        db.run('DELETE FROM files WHERE batch_id=?', (b['id'],))
        shutil.rmtree(os.path.join(config.DATA_DIR, 'batches', str(b['id'])), ignore_errors=True)
    for t in ('batches', 'folders', 'sessions', 'usage'): db.run(f'DELETE FROM {t} WHERE user_id=?', (uid,))
    db.run('DELETE FROM users WHERE id=?', (uid,))

class DelIn(BaseModel): password: str = ''
@app.post('/api/auth/delete')
def delete_me(x: DelIn, request: Request, response: Response, u=Me):
    guard.rate(request, 'pw', 10, 600)
    if auth.is_admin(u): raise HTTPException(400, '管理员账号不能注销')
    if not auth.check_pw(x.password, db.one('SELECT pw FROM users WHERE id=?', (u['id'],))['pw']): raise HTTPException(400, '密码不对')
    wipe_user(u['id']); response.delete_cookie(auth.COOKIE); return {'ok': True}

# ================= 管理员 =================
def Admin(u=Me):
    if not auth.is_admin(u): raise HTTPException(403, '只有管理员可以操作')
    return u

@app.get('/api/admin/users')
def admin_users(a=Depends(Admin)):
    rows = db.q('SELECT id, username, name, disabled, quota, created FROM users ORDER BY id')
    return [dict(r, used=used(r['id']), quota=user_quota(r), custom_quota=r['quota'] is not None, admin=auth.is_admin(r),
                 batches=db.one('SELECT COUNT(*) c FROM batches WHERE user_id=?', (r['id'],))['c']) for r in rows]

class AdminUserIn(BaseModel): disabled: Optional[bool] = None; quota: Optional[int] = None; reset_quota: Optional[bool] = None
@app.patch('/api/admin/users/{uid}')
def admin_user_edit(uid: int, x: AdminUserIn, a=Depends(Admin)):
    t = db.one('SELECT * FROM users WHERE id=?', (uid,))
    if not t: raise HTTPException(404, '账号不存在')
    if x.disabled is not None:
        if uid == a['id']: raise HTTPException(400, '不能停用自己的账号')
        db.run('UPDATE users SET disabled=? WHERE id=?', (1 if x.disabled else 0, uid))
        if x.disabled: db.run('DELETE FROM sessions WHERE user_id=?', (uid,))
    if x.reset_quota: db.run('UPDATE users SET quota=NULL WHERE id=?', (uid,))
    elif x.quota is not None:
        if not 0 <= x.quota <= 10000: raise HTTPException(400, '额度要在 0–10000 之间')
        db.run('UPDATE users SET quota=? WHERE id=?', (x.quota, uid))
    return {'ok': True}

@app.post('/api/admin/users/{uid}/password')
def admin_reset_pw(uid: int, a=Depends(Admin)):
    if not db.one('SELECT id FROM users WHERE id=?', (uid,)): raise HTTPException(404, '账号不存在')
    pw = ''.join(secrets.choice('abcdefghjkmnpqrstuvwxyz23456789') for _ in range(10))
    db.run('UPDATE users SET pw=? WHERE id=?', (auth.hash_pw(pw), uid)); db.run('DELETE FROM sessions WHERE user_id=?', (uid,))
    return {'password': pw}

@app.get('/api/admin/invite')
def admin_invite(a=Depends(Admin)): return {'code': invite_code(), 'default_quota': config.MONTHLY_QUOTA}

class InviteIn(BaseModel): code: str = ''
@app.put('/api/admin/invite')
def admin_invite_set(x: InviteIn, a=Depends(Admin)):
    c = x.code.strip()
    if c and not re.match(r'^[A-Za-z0-9_\-]{4,32}$', c): raise HTTPException(400, '邀请码需要 4–32 位字母、数字、下划线或横线')
    db.set_setting('invite', c); return {'code': c}

@app.get('/api/config')
def public_config(): return dict(allow_register=config.ALLOW_REGISTER, invite=bool(invite_code()), llm=llm.enabled(), quota=config.MONTHLY_QUOTA, max_file_mb=config.MAX_FILE_MB)

# ================= 文件夹 =================
class FolderIn(BaseModel): name: Optional[str] = None; sort: Optional[float] = None

def folder_of(u, fid):
    f = db.one('SELECT * FROM folders WHERE id=? AND user_id=?', (fid, u['id']))
    if not f: raise HTTPException(404, '文件夹不存在')
    return f

@app.get('/api/folders')
def folders(u=Me): return db.q('SELECT id,name,sort FROM folders WHERE user_id=? ORDER BY sort,id', (u['id'],))

@app.post('/api/folders')
def folder_new(x: FolderIn, u=Me):
    name = (x.name or '').strip()[:20] or '未命名文件夹'
    mx = db.one('SELECT MAX(sort) m FROM folders WHERE user_id=?', (u['id'],))['m'] or 0
    fid = db.run('INSERT INTO folders(user_id,name,sort,created) VALUES(?,?,?,?)', (u['id'], name, mx + 1, db.now()))
    return db.one('SELECT id,name,sort FROM folders WHERE id=?', (fid,))

@app.patch('/api/folders/{fid}')
def folder_edit(fid: int, x: FolderIn, u=Me):
    folder_of(u, fid)
    if x.name is not None:
        n = x.name.strip()[:20]
        if not n: raise HTTPException(400, '文件夹名称不能为空')
        db.run('UPDATE folders SET name=? WHERE id=?', (n, fid))
    if x.sort is not None: db.run('UPDATE folders SET sort=? WHERE id=?', (x.sort, fid))
    return db.one('SELECT id,name,sort FROM folders WHERE id=?', (fid,))

class OrderIn(BaseModel): ids: list[int]
@app.post('/api/folders/order')
def folder_order(x: OrderIn, u=Me):
    for i, fid in enumerate(x.ids): db.run('UPDATE folders SET sort=? WHERE id=? AND user_id=?', (i, fid, u['id']))
    return folders(u)

@app.delete('/api/folders/{fid}')
def folder_del(fid: int, u=Me):
    folder_of(u, fid)
    db.run('UPDATE batches SET folder_id=NULL WHERE folder_id=? AND user_id=?', (fid, u['id']))
    db.run('DELETE FROM folders WHERE id=?', (fid,)); return {'ok': True}

# ================= 报告批次 =================
def batch_of(u, bid):
    b = db.load_batch(db.one('SELECT * FROM batches WHERE id=? AND user_id=?', (bid, u['id'])))
    if not b: raise HTTPException(404, '报告不存在')
    return b

def summary(b):
    m = b['meta'] if isinstance(b['meta'], dict) else json.loads(b['meta'])
    d = b.get('data')
    if isinstance(d, str): d = json.loads(d)
    names = (d or {}).get('students', [])
    return dict(id=b['id'], folder_id=b['folder_id'], status=b['status'], cls=m.get('cls', ''), exam=m.get('exam', ''), n=len(names), names=names,
                title=b.get('title') or '', created=b['created'], updated=b['updated'])

@app.get('/api/batches')
def batches(u=Me):
    rows = db.q('SELECT id,folder_id,status,meta,data,title,created,updated FROM batches WHERE user_id=? ORDER BY COALESCE(sort,-created), created DESC', (u['id'],))
    return [summary(r) for r in rows]

class BOrderIn(BaseModel): ids: list[int]
@app.post('/api/batches/order')
def batch_order(x: BOrderIn, u=Me):
    """拖动排序：传入同一个文件夹里报告的新顺序"""
    for i, bid in enumerate(x.ids): db.run('UPDATE batches SET sort=? WHERE id=? AND user_id=?', (i, bid, u['id']))
    return {'ok': True}

class MetaIn(BaseModel):
    org: Optional[str] = None; campus: Optional[str] = None; teacher: Optional[str] = None; cls: Optional[str] = None
    exam: Optional[str] = None; subject: Optional[str] = None; folder_id: Optional[int] = None; move: Optional[bool] = None
    title: Optional[str] = None

META_KEYS = ('org', 'campus', 'teacher', 'cls', 'exam', 'subject')
@app.post('/api/batches')
def batch_new(x: MetaIn, u=Me):
    meta = {k: (getattr(x, k) or '').strip()[:40] for k in META_KEYS}; meta['subject'] = meta['subject'] or '数学'
    if x.folder_id: folder_of(u, x.folder_id)
    bid = db.run('INSERT INTO batches(user_id,folder_id,status,meta,created,updated,sort) VALUES(?,?,?,?,?,?,?)',
                 (u['id'], x.folder_id, 'draft', json.dumps(meta, ensure_ascii=False), db.now(), db.now(), -db.now()))
    return detail(bid, u)

@app.get('/api/batches/{bid}')
def detail(bid: int, u=Me):
    b = batch_of(u, bid)
    fl = db.q('SELECT id,kind,name,size FROM files WHERE batch_id=? ORDER BY id', (bid,))
    out = summary(b); out.update(meta=b['meta'], files=fl, progress=b['progress'], error=b['error'], confirmed=b['confirmed'])
    d = b['data']
    if d:
        out['data'] = {k: d[k] for k in ('lectures', 'items', 'students', 'scores', 'official', 'exit', 'notes') if k in d}
        out['data']['has_plan'] = bool(d.get('plan'))
        out['issues'] = b['issues'] or []
    if b['content'] and b['result']:
        r = b['result']
        out['report'] = dict(version=r['version'], students=[dict(name=n, key=r['keys'][n], total=r['analysis']['students'][n]['total'], pages=len(r['files'][n]['previews']),
                                                                  headline=b['content']['headline'].get(n, ''), message=b['content']['message'].get(n, '')) for n in r['keys']],
                             has_plan=bool(b['content'].get('plan')), full=r['analysis']['class']['full'])
    return out

@app.patch('/api/batches/{bid}')
def batch_edit(bid: int, x: MetaIn, u=Me):
    b = batch_of(u, bid)
    if x.move:
        if x.folder_id: folder_of(u, x.folder_id)
        db.save_batch(bid, folder_id=x.folder_id)
    meta = b['meta']
    for k in META_KEYS:
        v = getattr(x, k)
        if v is not None: meta[k] = v.strip()[:40]
    if x.title is not None: db.save_batch(bid, title=x.title.strip()[:40] or None)
    db.save_batch(bid, meta=meta)
    return detail(bid, u)

@app.delete('/api/batches/{bid}')
def batch_del(bid: int, u=Me):
    batch_of(u, bid)
    db.run('DELETE FROM files WHERE batch_id=?', (bid,)); db.run('DELETE FROM batches WHERE id=?', (bid,))
    shutil.rmtree(os.path.join(config.DATA_DIR, 'batches', str(bid)), ignore_errors=True)
    return {'ok': True}

def copy_name(u, exam):
    base = re.sub(r'（副本(?: \d+)?）$', '', exam or '')
    exams = {summary(r)['exam'] for r in db.q('SELECT id,folder_id,status,meta,data,title,created,updated FROM batches WHERE user_id=?', (u['id'],))}
    n = 1
    while True:
        name = base + ('（副本）' if n == 1 else f'（副本 {n}）')
        if name not in exams: return name
        n += 1

@app.post('/api/batches/{bid}/copy')
def batch_copy(bid: int, u=Me):
    """创建副本：沿用机构信息、试卷和课程大纲，成绩表和出门测需要重新上传。"""
    b = batch_of(u, bid); meta = dict(b['meta']); meta['exam'] = copy_name(u, meta.get('exam'))
    nid = db.run('INSERT INTO batches(user_id,folder_id,status,meta,created,updated,sort) VALUES(?,?,?,?,?,?,?)',
                 (u['id'], b['folder_id'], 'draft', json.dumps(meta, ensure_ascii=False), db.now(), db.now(), (b.get('sort') or 0) + 0.5))
    for f in db.q("SELECT * FROM files WHERE batch_id=? AND kind IN ('paper','plan')", (bid,)):
        dst = os.path.join(jobs.bdir(nid, 'uploads'), os.path.basename(f['path'])); shutil.copy(f['path'], dst)
        db.run('INSERT INTO files(batch_id,kind,name,path,size,created) VALUES(?,?,?,?,?,?)', (nid, f['kind'], f['name'], dst, f['size'], db.now()))
    return detail(nid, u)

# ---------------- 上传 ----------------
ALLOWED = ('jpg', 'jpeg', 'png', 'webp', 'bmp', 'heic', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'xlsm', 'csv')
@app.post('/api/batches/{bid}/files')
async def upload(bid: int, kind: str = Form(...), files: list[UploadFile] = File(...), u=Me):
    b = batch_of(u, bid)
    if kind not in ('paper', 'grade', 'exit', 'plan'): raise HTTPException(400, '未知的材料类型')
    if b['status'] in ('recognizing', 'generating'): raise HTTPException(409, '正在处理中，请稍后再改')
    saved = []
    for f in files:
        name = os.path.basename(f.filename or 'file')
        e = name.lower().rsplit('.', 1)[-1] if '.' in name else ''
        if e not in ALLOWED: raise HTTPException(400, f'{name}：只支持图片、PDF、Word、Excel')
        if e == 'doc': raise HTTPException(400, f'{name}：请在 Word 里另存为 .docx 后再上传')
        data = await f.read()
        if len(data) > config.MAX_FILE_MB * 1024 * 1024: raise HTTPException(400, f'{name} 超过 {config.MAX_FILE_MB} MB，请压缩后再传')
        path = os.path.join(jobs.bdir(bid, 'uploads'), f'{int(time.time() * 1000)}_{len(saved)}.{e}')
        open(path, 'wb').write(data)
        fid = db.run('INSERT INTO files(batch_id,kind,name,path,size,created) VALUES(?,?,?,?,?,?)', (bid, kind, name, path, len(data), db.now()))
        saved.append(dict(id=fid, kind=kind, name=name, size=len(data)))
    return saved

@app.delete('/api/batches/{bid}/files/{fid}')
def file_del(bid: int, fid: int, u=Me):
    batch_of(u, bid)
    f = db.one('SELECT * FROM files WHERE id=? AND batch_id=?', (fid, bid))
    if f:
        try: os.remove(f['path'])
        except OSError: pass
        db.run('DELETE FROM files WHERE id=?', (fid,))
    return {'ok': True}

@app.post('/api/batches/{bid}/recognize')
def do_recognize(bid: int, u=Me):
    b = batch_of(u, bid)
    if b['status'] in ('recognizing', 'generating'): raise HTTPException(409, '正在处理中')
    fk = jobs.files_by_kind(bid)
    miss = [t for k, t in (('paper', '考试试卷'), ('grade', '逐题成绩表'), ('exit', '出门测记录表')) if not fk[k]]
    if miss: raise HTTPException(400, '还差：' + '、'.join(miss))
    jobs.start_recognize(bid); return detail(bid, u)

# ---------------- 核对 ----------------
class DataIn(BaseModel):
    scores: Optional[dict[str, list[float]]] = None      # {姓名: [...]}，只传改动的学生
    items: Optional[list[dict[str, Any]]] = None          # 题目表：full / type / kp / lect
    exit: Optional[dict[str, list[list[int]]]] = None
    action: Optional[dict[str, str]] = None               # {issue: id, key: set_full|use_system|ok}

@app.put('/api/batches/{bid}/data')
def data_edit(bid: int, x: DataIn, u=Me):
    b = batch_of(u, bid)
    if b['status'] not in ('check', 'review', 'done'): raise HTTPException(409, '现在不能修改识别结果')
    d = b['data']
    if x.scores:
        for n, s in x.scores.items():
            if n in d['scores'] and len(s) == len(d['items']):
                if any(v < 0 for v in s): raise HTTPException(400, '分数不能是负数')
                old = d['scores'][n]
                for k, (a, c) in enumerate(zip(old, s)):
                    if a != c: d['resolved'].pop(f'low:{n}:{k}', None); d['resolved'][f'low:{n}:{k}'] = '已修改'
                d['scores'][n] = s
                d['blanks'] = [bl for bl in d.get('blanks', []) if not (bl['kind'] == 'grade' and bl['stu'] == n and old[bl['k']] != s[bl['k']])]
    if x.items:
        for k, it in enumerate(x.items[:len(d['items'])]):
            for f in ('full', 'type', 'kp', 'lect'):
                if f in it: d['items'][k][f] = it[f]
    if x.exit:
        for n, m in x.exit.items():
            if n in d['exit']: d['exit'][n] = [[1 if v else 0 for v in row] for row in m]
    if x.action: validate.apply_action(d, x.action['issue'], x.action['key'])
    iss = jobs.issue_view(d)
    # 生成之后再改数据，报告要重新生成
    status = 'check' if b['status'] != 'check' else b['status']
    db.save_batch(bid, data=d, issues=iss, status=status)
    return detail(bid, u)

@app.post('/api/batches/{bid}/generate')
def do_generate(bid: int, u=Me):
    b = batch_of(u, bid)
    if b['status'] != 'check': raise HTTPException(409, '请先完成识别和核对')
    if validate.red_count(b['issues'] or []): raise HTTPException(400, '还有红色问题没处理')
    if not b['counted']:
        if used(u['id']) >= user_quota(u): raise HTTPException(429, f'本月 {user_quota(u)} 个批次已经用完，下个月 1 日恢复')
        db.run('INSERT INTO usage(user_id,month,count) VALUES(?,?,1) ON CONFLICT(user_id,month) DO UPDATE SET count=count+1', (u['id'], month()))
        db.save_batch(bid, counted=1)
    jobs.start_generate(bid); return detail(bid, u)

# ---------------- 预览与修改 ----------------
class TextIn(BaseModel): headline: Optional[str] = None; message: Optional[str] = None

def stu_check(b, name):
    if not b['result'] or name not in b['result']['keys']: raise HTTPException(404, '没有这位学生的报告')

@app.put('/api/batches/{bid}/students/{name}')
def stu_text(bid: int, name: str, x: TextIn, u=Me):
    b = batch_of(u, bid); stu_check(b, name); c = b['content']
    if x.headline is not None: c['headline'][name] = x.headline.strip()[:60]
    if x.message is not None: c['message'][name] = x.message.strip()[:600]
    db.save_batch(bid, content=c)
    jobs.render_one(bid, name)
    return detail(bid, u)

@app.post('/api/batches/{bid}/students/{name}/rewrite')
def stu_rewrite(bid: int, name: str, u=Me):
    b = batch_of(u, bid); stu_check(b, name)
    s = writer.rewrite_one(b['result']['analysis'], name)
    return dict(headline=s.get('headline', ''), message=s.get('message', ''))

@app.post('/api/batches/{bid}/students/{name}/confirm')
def stu_confirm(bid: int, name: str, u=Me):
    b = batch_of(u, bid); stu_check(b, name); cf = b['confirmed'] or []
    if name not in cf: cf.append(name)
    db.save_batch(bid, confirmed=cf); return detail(bid, u)

@app.post('/api/batches/{bid}/finish')
def finish(bid: int, u=Me):
    b = batch_of(u, bid)
    if b['status'] not in ('review', 'done'): raise HTTPException(409, '报告还没生成')
    db.save_batch(bid, status='done'); return detail(bid, u)

def safe(s): return re.sub(r'[\\/:*?"<>|\s]+', '', s or '') or '报告'

@app.get('/api/batches/{bid}/preview/{key}/{page}')
def preview(bid: int, key: int, page: int, u=Me):
    b = batch_of(u, bid)
    if not b['result']: raise HTTPException(404, '报告还没生成')
    for n, k in b['result']['keys'].items():
        if k == key:
            pv = b['result']['files'][n]['previews']
            if 1 <= page <= len(pv): return FileResponse(pv[page - 1], media_type='image/jpeg', headers={'Cache-Control': 'private, max-age=600'})
    raise HTTPException(404, '页面不存在')

@app.get('/api/batches/{bid}/pdf/{key}')
def pdf(bid: int, key: int, u=Me):
    b = batch_of(u, bid)
    if not b['result']: raise HTTPException(404, '报告还没生成')
    for n, k in b['result']['keys'].items():
        if k == key:
            return FileResponse(b['result']['files'][n]['pdf'], media_type='application/pdf', filename=f'{safe(n)}_{safe(b["meta"].get("exam"))}_学情报告.pdf')
    raise HTTPException(404, '报告不存在')

@app.get('/api/batches/{bid}/zip')
def zipall(bid: int, u=Me):
    b = batch_of(u, bid)
    if not b['result']: raise HTTPException(404, '报告还没生成')
    buf = io.BytesIO()
    ex = safe(b['meta'].get('exam'))
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for n in b['result']['keys']: z.write(b['result']['files'][n]['pdf'], f'{safe(n)}_{ex}_学情报告.pdf')
    buf.seek(0)
    from urllib.parse import quote
    fn = f'{safe(b["meta"].get("cls"))}_{ex}_学情报告.zip'
    return StreamingResponse(buf, media_type='application/zip', headers={'Content-Disposition': f"attachment; filename*=UTF-8''{quote(fn)}"})

# ---------------- Excel 模板 ----------------
@app.get('/api/templates/{kind}')
def template(kind: str):
    from .templates import grade_template, exit_template
    if kind not in ('grade', 'exit'): raise HTTPException(404, '模板不存在')
    data, fn = (grade_template(), '逐题成绩表模板.xlsx') if kind == 'grade' else (exit_template(), '出门测记录表模板.xlsx')
    from urllib.parse import quote
    return Response(data, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={'Content-Disposition': f"attachment; filename*=UTF-8''{quote(fn)}"})

@app.get('/api/health')
def health(): return {'ok': True, 'llm': llm.enabled()}

# ---------------- 前端静态文件 ----------------
if os.path.isdir(config.FRONTEND_DIR):
    app.mount('/assets', StaticFiles(directory=os.path.join(config.FRONTEND_DIR, 'assets')), name='assets')
    @app.get('/{path:path}')
    def spa(path: str):
        if path.startswith('api/'): raise HTTPException(404, '接口不存在')
        f = os.path.join(config.FRONTEND_DIR, path)
        if path and os.path.isfile(f): return FileResponse(f)
        return FileResponse(os.path.join(config.FRONTEND_DIR, 'index.html'))
