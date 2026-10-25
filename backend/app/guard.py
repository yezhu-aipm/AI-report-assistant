"""防攻击：图形验证码、登录失败锁定、接口频率限制。数据都放在内存里，服务重启会清空（单机部署足够）。"""
import base64, io, random, secrets, threading, time
from collections import defaultdict, deque
from fastapi import Request, HTTPException
from . import config

_lock = threading.Lock()

def client_ip(request: Request) -> str:
    # Nginx 会把真实访客 IP 追加在 X-Forwarded-For 最后；前面的部分可以被伪造，所以只取最后一个
    xff = request.headers.get('x-forwarded-for', '')
    if xff: return xff.split(',')[-1].strip()
    return request.headers.get('x-real-ip') or (request.client.host if request.client else '-')

# ---------------- 图形验证码 ----------------
CHARS = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'   # 去掉了容易看混的 0 O 1 I L
_caps = {}

def _font(size):
    from PIL import ImageFont
    for p in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',
              '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'):
        try: return ImageFont.truetype(p, size)
        except Exception: pass
    try: return ImageFont.load_default(size=size)
    except Exception: return ImageFont.load_default()

def new_captcha():
    from PIL import Image, ImageDraw, ImageFilter
    code = ''.join(random.choice(CHARS) for _ in range(4))
    W, H = 132, 44
    img = Image.new('RGB', (W, H), (246, 244, 255)); d = ImageDraw.Draw(img)
    for _ in range(5):  # 干扰线
        d.line([(random.randint(0, W), random.randint(0, H)), (random.randint(0, W), random.randint(0, H))],
               fill=tuple(random.randint(150, 210) for _ in range(3)), width=2)
    f = _font(28)
    for i, ch in enumerate(code):
        layer = Image.new('RGBA', (36, 44), (0, 0, 0, 0)); ImageDraw.Draw(layer).text((4, 2), ch, font=f,
            fill=(random.randint(40, 110), random.randint(30, 80), random.randint(120, 200), 255))
        layer = layer.rotate(random.uniform(-25, 25), resample=Image.BICUBIC, expand=0)
        img.paste(layer, (8 + i * 30 + random.randint(-3, 3), random.randint(-3, 3)), layer)
    for _ in range(120):  # 噪点
        d.point((random.randint(0, W - 1), random.randint(0, H - 1)), fill=tuple(random.randint(100, 200) for _ in range(3)))
    img = img.filter(ImageFilter.SMOOTH)
    buf = io.BytesIO(); img.save(buf, 'PNG')
    cid = secrets.token_urlsafe(12)
    with _lock:
        now = time.time()
        for k in [k for k, v in _caps.items() if v[1] < now]: _caps.pop(k, None)
        if len(_caps) > 5000: _caps.clear()
        _caps[cid] = (code, now + 300)
    return {'id': cid, 'img': 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()}

def check_captcha(cid, answer):
    """一次性：无论对错都作废，防止反复试。"""
    with _lock: v = _caps.pop(cid or '', None)
    if not v or v[1] < time.time(): raise HTTPException(400, {'error': '验证码已过期，请换一张', 'captcha': True})
    if (answer or '').strip().upper() != v[0]: raise HTTPException(400, {'error': '验证码不对，请重新输入', 'captcha': True})

# ---------------- 登录失败锁定 ----------------
_fails = {}   # key -> [次数, 锁定到期时间, 最后失败时间]

def _keys(username, ip): return ['u:' + (username or '').lower(), 'ip:' + ip]

def login_state(username, ip):
    """返回 (是否锁定剩余秒数, 是否需要验证码)"""
    now, need, wait = time.time(), False, 0
    with _lock:
        for k in _keys(username, ip):
            v = _fails.get(k)
            if not v: continue
            if v[2] < now - 3600: _fails.pop(k, None); continue   # 一小时没再错就清零
            if v[1] > now: wait = max(wait, int(v[1] - now))
            if v[0] >= 1: need = True
    return wait, need

def login_failed(username, ip):
    now = time.time()
    with _lock:
        for k in _keys(username, ip):
            v = _fails.setdefault(k, [0, 0, now]); v[0] += 1; v[2] = now
            limit = config.LOGIN_MAX_FAIL * (4 if k.startswith('ip:') else 1)   # 同一 IP 可能是一个校区多位老师，放宽一些
            if v[0] >= limit: v[1] = now + config.LOGIN_LOCK_MIN * 60; v[0] = 1   # 解锁后仍要填验证码
        if len(_fails) > 20000: _fails.clear()

def login_ok(username, ip):
    with _lock: _fails.pop('u:' + (username or '').lower(), None)

# ---------------- 频率限制 ----------------
_hits = defaultdict(deque)

def rate(request: Request, bucket: str, limit: int, per: int):
    key = bucket + ':' + client_ip(request); now = time.time()
    with _lock:
        q = _hits[key]
        while q and q[0] < now - per: q.popleft()
        if len(q) >= limit: raise HTTPException(429, '操作太频繁了，请稍等一会儿再试')
        q.append(now)
        if len(_hits) > 50000: _hits.clear()
