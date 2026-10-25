"""大模型调用封装：兼容 OpenAI 接口，统一要求返回 JSON。"""
import base64, json, re, time, logging
from . import config

log = logging.getLogger('llm')
_client = None

def client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL or None, timeout=config.LLM_TIMEOUT)
    return _client

def enabled(): return not config.LLM_MOCK

def image_part(data: bytes, mime='image/jpeg'):
    return {'type': 'image_url', 'image_url': {'url': f'data:{mime};base64,{base64.b64encode(data).decode()}'}}

def _parse(text):
    text = text.strip()
    m = re.search(r'```(?:json)?\s*(.*?)```', text, re.S)
    if m: text = m.group(1)
    a, b = text.find('{'), text.rfind('}')
    if a >= 0 and b > a: text = text[a:b + 1]
    return json.loads(text)

def chat_json(system: str, user_parts, model: str, temperature=0.2, retries=2):
    """user_parts: 字符串，或 [文字/图片 part] 列表。返回解析后的 dict。"""
    content = user_parts if isinstance(user_parts, list) else [{'type': 'text', 'text': user_parts}]
    msgs = [{'role': 'system', 'content': system}, {'role': 'user', 'content': content}]
    err = None
    for attempt in range(retries + 1):
        try:
            r = client().chat.completions.create(model=model, messages=msgs, temperature=temperature,
                                                 response_format={'type': 'json_object'})
            return _parse(r.choices[0].message.content or '{}')
        except Exception as e:  # 网络抖动、JSON 不完整时重试
            err = e; log.warning('LLM 调用失败（第 %s 次）：%s', attempt + 1, e); time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f'大模型调用失败：{err}')
