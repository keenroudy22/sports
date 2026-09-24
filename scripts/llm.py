"""A thin client for the local model, plus the two guards that keep its prose honest.

The model writes explanation, never data. It is served by Ollama on this machine and reached over
its native chat endpoint with urllib, thinking switched off, so the zero-dependency property holds.
If Ollama is not running the client raises LLMUnavailable; nothing here ever returns empty prose.

Two guards run on everything the model writes before it can reach the record:

  check_style(text)            the house style: no em or en dashes, plain words, short sentences,
                               no model or version names, no marketing, no advice
  numbers_ok(text, pick, ...)  every number in the text appears in the pick's own fields, the desk
                               output or the facts it was given; an invented figure fails

Stdlib only.
"""
import json
import os
import re
import urllib.error
import urllib.request

DEFAULT_BASE = 'http://localhost:11434'
DEFAULT_MODEL = 'qwen3:32b'
NUM_CTX = 16384
KEEP_ALIVE = '15m'


def base_url():
    return os.environ.get('KEENROUDY_LLM_BASE') or os.environ.get('OLLAMA_HOST') or DEFAULT_BASE


def model_name():
    return os.environ.get('KEENROUDY_LLM_MODEL') or DEFAULT_MODEL


class LLMUnavailable(RuntimeError):
    """Ollama is down, timed out, refused, or returned nothing usable."""


def transport(url, body, headers, timeout):
    request = urllib.request.Request(url, data=json.dumps(body).encode('utf-8'),
                                     headers={'Content-Type': 'application/json', **headers}, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        raise LLMUnavailable(f'{url} returned HTTP {error.code}: {error.read()[:200]!r}') from None
    except (urllib.error.URLError, OSError, TimeoutError) as error:
        raise LLMUnavailable(f'{url} unreachable: {error}') from None


def available(base=None, timeout=2):
    try:
        with urllib.request.urlopen(f'{base or base_url()}/api/version', timeout=timeout) as response:
            return response.status == 200
    except (urllib.error.URLError, OSError, TimeoutError, ValueError):
        return False


def strip_thinking(text):
    """Reasoning models may wrap their scratch work in <think> tags; only the answer counts."""
    return re.sub(r'<think>.*?</think>', '', text or '', flags=re.DOTALL).strip()


def draft(system, user, max_tokens=400, temperature=0.2, timeout=90, model=None, base=None, send=None):
    """One completion over Ollama's native chat endpoint, thinking off. Raises LLMUnavailable rather than returning ''.

    The OpenAI-compatible endpoint cannot switch a reasoning model's thinking off, and the model then
    spends the whole token budget on scratch work and returns nothing; the native endpoint can.
    """
    body = {'model': model or model_name(), 'stream': False, 'think': False, 'keep_alive': KEEP_ALIVE,
            'options': {'num_ctx': NUM_CTX, 'temperature': temperature, 'num_predict': max_tokens},
            'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]}
    raw = (send or transport)(f'{base or base_url()}/api/chat', body, {}, timeout)
    try:
        payload = json.loads(raw)
        text = strip_thinking(payload['message']['content'])
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise LLMUnavailable(f'malformed completion: {error}') from None
    if not text:
        raise LLMUnavailable('the model returned no text')
    return text


def draft_json(system, user, schema, max_tokens=400, temperature=0.0, timeout=90, model=None, base=None, send=None):
    """A structured answer over Ollama's native endpoint, constrained to `schema` (a JSON schema dict)."""
    body = {'model': model or model_name(), 'stream': False, 'format': schema, 'think': False,
            'keep_alive': KEEP_ALIVE, 'options': {'num_ctx': NUM_CTX, 'temperature': temperature, 'num_predict': max_tokens},
            'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]}
    raw = (send or transport)(f'{base or base_url()}/api/chat', body, {}, timeout)
    try:
        payload = json.loads(raw)
        content = strip_thinking(payload['message']['content'])
        return json.loads(content)
    except (ValueError, KeyError, TypeError) as error:
        raise LLMUnavailable(f'malformed structured answer: {error}') from None


# ------------------------------------------------------------------ house style

STYLE_SYSTEM = """You write short plain English for a sports stats site that grades its own picks in public.
Rules, all of them hard:
- Never use an em dash or an en dash. Use a comma, a period or the word "and".
- Short sentences. Plain words. No hype, no slang for betting, no exclamation marks, no emoji.
- Never say lock, guaranteed, free money, smash, hammer, can't lose, easy, sure thing, or give advice.
- Never name a model, a model version or a company. Say "our number" or "our projection".
- Never invent a number. Use only the numbers in the material you are given, written the same way.
- It is entertainment; the reader is a friend, not a customer."""

DASHES = re.compile('[–—]')
VERSION_WORDS = re.compile(r'\bv\d+(?:\.\d+)?\b', re.IGNORECASE)
MODEL_WORDS = re.compile(r'\b(qwen|claude|gpt|chatgpt|llama|gemma|mistral|openai|anthropic|ollama|elo)\b', re.IGNORECASE)
MARKETING = re.compile(r"\b(lock|locks|guaranteed|guarantee|free money|smash|hammer|can't lose|cannot lose|easy money|sure thing|"
                       r"bet the house|max bet|no brainer|no-brainer|must bet|must-bet)\b", re.IGNORECASE)
ADVICE = re.compile(r'\b(you should bet|bet this|take this bet|place this bet|wager on this)\b', re.IGNORECASE)
EMOJI = re.compile('[\U0001F300-\U0001FAFF☀-➿\U0001F000-\U0001F2FF]')
LONG_SENTENCE = 220


def check_style(text):
    """The house-style problems in a text, as short strings; empty means it passes."""
    problems = []
    if DASHES.search(text):
        problems.append('contains an em or en dash')
    if VERSION_WORDS.search(text):
        problems.append('names a model version')
    if MODEL_WORDS.search(text):
        problems.append('names a model or company')
    if MARKETING.search(text):
        problems.append(f'marketing language: {MARKETING.search(text).group(0)}')
    if ADVICE.search(text):
        problems.append('gives betting advice')
    if EMOJI.search(text):
        problems.append('contains an emoji')
    if '!' in text:
        problems.append('exclamation mark')
    for sentence in re.split(r'(?<=[.?])\s+|\n', text):       # a line break ends a sentence: a list is short lines
        if len(sentence) > LONG_SENTENCE:
            problems.append(f'a sentence runs {len(sentence)} characters')
            break
    return problems


# ------------------------------------------------------------------ numbers guard

URL = re.compile(r'https?://\S+')
NUMBER = re.compile(r'(?<![\w.])[-+]?\d+(?:\.\d+)?')
ALWAYS_ALLOWED = {'10', '80', '100', '50'}      # "1 to 10", "80% range", per cent, coin flip


def normal(token):
    try:
        return f'{float(token.lstrip("+-")):g}'
    except ValueError:
        return None


def numbers_in(text):
    """Every number in a text, normalized so 43.50 and 43.5 agree and a sign does not matter."""
    return {n for n in (normal(m) for m in NUMBER.findall(URL.sub(' ', text or ''))) if n is not None}


def allowed_numbers(pick, extra=()):
    """Every number in the pick's own fields, the desk output and any extra material."""
    found = set()

    def walk(value):
        if isinstance(value, dict):
            for v in value.values():
                walk(v)
        elif isinstance(value, (list, tuple)):
            for v in value:
                walk(v)
        elif isinstance(value, bool) or value is None:
            return
        elif isinstance(value, (int, float)):
            found.add(f'{abs(float(value)):g}')      # signs do not matter: -105 in a field allows "-105" or "105"
        elif isinstance(value, str):
            found.update(numbers_in(value))

    walk(pick)
    for item in extra:
        walk(item)
    return found | ALWAYS_ALLOWED


def numbers_ok(text, pick, extra=()):
    """(ok, the numbers in the text that came from nowhere)."""
    strays = sorted(numbers_in(text) - allowed_numbers(pick, extra), key=lambda n: float(n))
    return not strays, strays
