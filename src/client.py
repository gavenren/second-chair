'''Thin client for the Adaption Responses API: streaming, disk cache, shared rate limiter, retries.'''
from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time

NL = chr(10)


class RateLimiter:
    '''Spaces calls evenly so that no more than per_minute start in any minute.'''

    def __init__(self, per_minute: float):
        self.gap = 60.0 / per_minute
        self.next = time.time()
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            now = time.time()
            self.next = max(self.next, now) + self.gap
            delay = self.next - self.gap - now
        if delay > 0:
            time.sleep(delay)

    def pause(self, seconds: float):
        """Hold every caller back, after the server reports its rate limit was hit."""
        with self.lock:
            self.next = max(self.next, time.time() + seconds)


# With effort none, GLM 5.3 Flash writes its reasoning into the visible reply; with low it
# produces no reasoning tokens and a clean reply.
EFFORT_OVERRIDE = {'glm-5.3-flash': 'low'}


class Client:
    def __init__(self, cache_dir: str, per_minute: float = 40, effort: str | None = 'none'):
        from adaption import Adaption
        self.c = Adaption(max_retries=0, timeout=240)
        self.cache_dir = cache_dir
        # reasoning effort sent with every call; None leaves the platform default (the highest setting)
        self.effort = effort
        os.makedirs(cache_dir, exist_ok=True)
        self.limiter = RateLimiter(per_minute)
        self.lock = threading.Lock()
        self.cache: dict[str, dict] = {}
        self.loaded: set[str] = set()
        self.stats = {'calls': 0, 'cached': 0, 'in': 0, 'out': 0, 'cost': 0.0, 'rate_limited': 0, 'errors': 0, 'invalid': 0}

    def _path(self, model: str) -> str:
        return os.path.join(self.cache_dir, model.replace('/', '_') + '.jsonl')

    def _load(self, model: str):
        with self.lock:
            if model in self.loaded:
                return
            p = self._path(model)
            if os.path.exists(p):
                for line in open(p, encoding='utf-8'):
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    self.cache[r['key']] = r
            self.loaded.add(model)

    def call(self, model: str, messages: list[dict], system: str | None = None, temperature: float = 0.0,
             max_tokens: int = 4000, draw: int = 0, valid=None, tries: int = 6) -> dict:
        '''Returns {text, in, out, cost} or {text: None, error}. valid(text) -> bool marks a
        reply as usable; unusable replies are asked again and are not cached.'''
        self._load(model)
        effort = EFFORT_OVERRIDE.get(model, self.effort) if self.effort else None
        ident = [model, system, messages, temperature, draw] + ([effort] if effort else [])
        key = hashlib.sha1(json.dumps(ident, sort_keys=True).encode()).hexdigest()
        hit = self.cache.get(key)
        if hit is not None:
            with self.lock:
                self.stats['cached'] += 1
            return hit
        err, cap = None, max_tokens
        for attempt in range(tries):
            self.limiter.wait()
            try:
                kw = dict(model=model, input=messages, temperature=temperature, max_output_tokens=cap, tools=[], store=False)
                if system:
                    kw['instructions'] = system
                if effort:
                    kw['extra_body'] = {'reasoning': {'effort': effort}}
                # streamed, because the gateway drops non-streamed requests that take over 60 s
                text, u = '', None
                for ev in self.c.responses.create(stream=True, **kw):
                    k = getattr(ev, 'type', '')
                    if k == 'response.output_text.delta':
                        text += ev.delta
                    elif k == 'response.completed':
                        u = getattr(ev.response, 'usage', None)
                    elif k == 'error':
                        raise RuntimeError('stream error: ' + str(getattr(ev, 'message', ev))[:200])
                text = text.strip()
                rec = {'key': key, 'text': text, 'in': getattr(u, 'input_tokens', None),
                       'out': getattr(u, 'output_tokens', None), 'cost': getattr(u, 'cost', None)}
                ok = bool(text) and (valid is None or valid(text))
                with self.lock:
                    self.stats['calls'] += 1
                    self.stats['in'] += rec['in'] or 0
                    self.stats['out'] += rec['out'] or 0
                    self.stats['cost'] += rec['cost'] or 0.0
                    if not ok:
                        self.stats['invalid'] += 1
                if not ok:
                    err = 'invalid reply: ' + text[:80]
                    cap = min(24000, cap * 2)  # an empty reply usually means the cap was spent on reasoning
                    print('client:', time.strftime('%H:%M:%S'), model, err, file=sys.stderr, flush=True)
                    continue
                with self.lock:
                    self.cache[key] = rec
                    with open(self._path(model), 'a', encoding='utf-8') as f:
                        f.write(json.dumps(rec, ensure_ascii=False) + NL)
                return rec
            except Exception as e:  # noqa: BLE001
                err = repr(e)[:300]
                print('client:', time.strftime('%H:%M:%S'), model, err[:160], file=sys.stderr, flush=True)
                with self.lock:
                    self.stats['errors'] += 1
                if '429' in err or 'rate' in err.lower():
                    with self.lock:
                        self.stats['rate_limited'] += 1
                    self.limiter.pause(62)
                    time.sleep(5)
                else:
                    time.sleep(min(30, 2 ** attempt))
        return {'key': key, 'text': None, 'error': err}


def parse_json(text: str | None) -> dict | None:
    '''Pull the first JSON object out of a reply.'''
    if not text:
        return None
    i, j = text.find('{'), text.rfind('}')
    if i < 0 or j <= i:
        return None
    for a, b in ((i, j), (text.rfind('{'), j)):      # the whole span, then the last object
        try:
            obj = json.loads(text[a:b + 1])
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def to_number(x) -> float | None:
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        s = x.replace('$', '').replace(',', '').replace('%', '').strip()
        try:
            return float(s)
        except ValueError:
            return None
    return None
