"""账号密码登录。密码用 scrypt 加盐哈希；会话 token 存在 HttpOnly Cookie。"""
import hashlib, hmac, os, re, secrets
from fastapi import Request, HTTPException
from . import db
from .config import SESSION_DAYS

COOKIE = 'xq_session'
USER_RE = re.compile(r'^[A-Za-z0-9]{4,20}$')

def hash_pw(pw: str) -> str:
    salt = os.urandom(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1)
    return 'scrypt$' + salt.hex() + '$' + h.hex()

def check_pw(pw: str, stored: str) -> bool:
    try:
        _, salt, h = stored.split('$')
        got = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2 ** 14, r=8, p=1)
        return hmac.compare_digest(got.hex(), h)
    except Exception:
        return False

def new_session(user_id: int) -> str:
    tok = secrets.token_urlsafe(32)
    db.run('INSERT INTO sessions(token,user_id,expires) VALUES(?,?,?)', (tok, user_id, db.now() + SESSION_DAYS * 86400))
    return tok

def current_user(request: Request):
    tok = request.cookies.get(COOKIE)
    if not tok: raise HTTPException(401, '请先登录')
    s = db.one('SELECT * FROM sessions WHERE token=?', (tok,))
    if not s or s['expires'] < db.now(): raise HTTPException(401, '登录已过期，请重新登录')
    u = db.one('SELECT id, username, name, disabled, quota, prefs, created FROM users WHERE id=?', (s['user_id'],))
    if not u: raise HTTPException(401, '账号不存在')
    if u['disabled']: raise HTTPException(401, '账号已被停用，请联系管理员')
    return u

def is_admin(u) -> bool:
    from .config import ADMIN_USER
    if ADMIN_USER: return u['username'].lower() == ADMIN_USER.lower()
    first = db.one('SELECT MIN(id) m FROM users')
    return bool(first) and first['m'] == u['id']
