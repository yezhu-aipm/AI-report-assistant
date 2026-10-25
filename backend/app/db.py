"""SQLite 存储。单机部署足够；数据文件在 DATA_DIR/app.db。"""
import sqlite3, json, threading, time, os
from .config import DATA_DIR

DB_PATH = os.path.join(DATA_DIR, 'app.db')
_local = threading.local()

SCHEMA = '''
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, pw TEXT NOT NULL, name TEXT NOT NULL DEFAULT '', created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS folders(
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, name TEXT NOT NULL, sort REAL NOT NULL DEFAULT 0, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS batches(
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, folder_id INTEGER, status TEXT NOT NULL DEFAULT 'draft',
  meta TEXT NOT NULL DEFAULT '{}', data TEXT, issues TEXT, content TEXT, result TEXT, progress TEXT,
  confirmed TEXT NOT NULL DEFAULT '[]', error TEXT, counted INTEGER NOT NULL DEFAULT 0,
  created REAL NOT NULL, updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS files(
  id INTEGER PRIMARY KEY, batch_id INTEGER NOT NULL, kind TEXT NOT NULL, name TEXT NOT NULL, path TEXT NOT NULL,
  size INTEGER NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS usage(user_id INTEGER NOT NULL, month TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(user_id, month));
CREATE INDEX IF NOT EXISTS ix_batches_user ON batches(user_id);
CREATE INDEX IF NOT EXISTS ix_files_batch ON files(batch_id);
'''

def conn():
    c = getattr(_local, 'c', None)
    if c is None:
        c = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        _local.c = c
    return c

MIGRATIONS = [
    "ALTER TABLE users ADD COLUMN disabled INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE users ADD COLUMN quota INTEGER",
    "ALTER TABLE users ADD COLUMN prefs TEXT NOT NULL DEFAULT '{}'",
    "ALTER TABLE batches ADD COLUMN sort REAL",
    "ALTER TABLE batches ADD COLUMN title TEXT",
]
EXTRA = '''
CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY, v TEXT NOT NULL);
UPDATE batches SET sort=-created WHERE sort IS NULL;
'''

def init():
    c = conn(); c.executescript(SCHEMA)
    for m in MIGRATIONS:          # 老数据库自动补字段，升级不丢数据
        try: c.execute(m)
        except sqlite3.OperationalError: pass
    c.executescript(EXTRA); c.commit()

def get_setting(k, default=None):
    r = one('SELECT v FROM settings WHERE k=?', (k,)); return r['v'] if r else default

def set_setting(k, v):
    run('INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v', (k, v))

def q(sql, args=()):
    return [dict(r) for r in conn().execute(sql, args).fetchall()]

def one(sql, args=()):
    r = conn().execute(sql, args).fetchone()
    return dict(r) if r else None

def run(sql, args=()):
    c = conn(); cur = c.execute(sql, args); c.commit(); return cur.lastrowid

def now(): return time.time()

JSON_COLS = ('meta', 'data', 'issues', 'content', 'result', 'progress', 'confirmed')
def load_batch(row):
    if not row: return None
    for k in JSON_COLS:
        if k in row and row[k] is not None and isinstance(row[k], str): row[k] = json.loads(row[k])
    return row

def save_batch(bid, **cols):
    sets, args = [], []
    for k, v in cols.items():
        sets.append(f'{k}=?'); args.append(json.dumps(v, ensure_ascii=False) if k in JSON_COLS and v is not None else v)
    sets.append('updated=?'); args.append(now()); args.append(bid)
    run(f'UPDATE batches SET {", ".join(sets)} WHERE id=?', args)
