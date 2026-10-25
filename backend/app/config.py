"""所有配置都从环境变量读取，部署时写在 .env 里。"""
import os

def _b(name, default):
    v = os.getenv(name)
    return default if v is None else v.strip().lower() in ('1', 'true', 'yes', 'on')

DATA_DIR = os.path.abspath(os.getenv('DATA_DIR', os.path.join(os.path.dirname(__file__), '..', 'data')))
SESSION_DAYS = int(os.getenv('SESSION_DAYS', '30'))
COOKIE_SECURE = _b('COOKIE_SECURE', False)          # 上线启用 HTTPS 后设为 true
ALLOW_REGISTER = _b('ALLOW_REGISTER', True)
MONTHLY_QUOTA = int(os.getenv('MONTHLY_QUOTA', '50'))  # 每个账号每月可生成的批次数
MAX_FILE_MB = int(os.getenv('MAX_FILE_MB', '20'))
INVITE_CODE = os.getenv('INVITE_CODE', '').strip()   # 注册邀请码；留空表示不需要。管理员在设置页改过后以设置页为准
ADMIN_USER = os.getenv('ADMIN_USER', '').strip()     # 管理员账号；留空时第一个注册的账号是管理员
LOGIN_MAX_FAIL = int(os.getenv('LOGIN_MAX_FAIL', '5'))
LOGIN_LOCK_MIN = int(os.getenv('LOGIN_LOCK_MIN', '15'))

# 大模型：任何兼容 OpenAI 接口的服务都可以（通义千问 / DeepSeek / 豆包……）
LLM_BASE_URL = os.getenv('LLM_BASE_URL', '')
LLM_API_KEY = os.getenv('LLM_API_KEY', '')
LLM_VISION_MODEL = os.getenv('LLM_VISION_MODEL', 'qwen3-vl-plus')   # 读图：试卷、拍照的成绩表和出门测表
LLM_TEXT_MODEL = os.getenv('LLM_TEXT_MODEL', 'qwen3-vl-plus')       # 写报告文字
LLM_TIMEOUT = int(os.getenv('LLM_TIMEOUT', '180'))
# 没配 Key 时进入演示模式：识别用规则兜底，文字用模板生成，方便本地跑通流程
LLM_MOCK = _b('LLM_MOCK', not LLM_API_KEY)

FRONTEND_DIR = os.path.abspath(os.getenv('FRONTEND_DIR', os.path.join(os.path.dirname(__file__), '..', '..', 'frontend', 'dist')))
os.makedirs(DATA_DIR, exist_ok=True)
