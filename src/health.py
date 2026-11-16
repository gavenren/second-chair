'''Health and timing check: a few advice-sized calls per hosted model, in parallel.'''
import sys, time, threading
from concurrent.futures import ThreadPoolExecutor
from adaption import Adaption
c = Adaption(max_retries=0, timeout=100)
Q = 'My former landlord kept my $1,800 deposit for a carpet that was already eight years old when I moved in. Case %d. What should I do?'

def one(job):
    m, i = job
    t = time.time(); text = ''; first = None
    try:
        for ev in c.responses.create(model=m, input=[{'role': 'user', 'content': Q % i}], temperature=0.7, max_output_tokens=6000, tools=[], store=False, stream=True):
            if getattr(ev, 'type', '') == 'response.output_text.delta':
                if first is None: first = time.time() - t
                text += ev.delta
        return m, round(time.time() - t, 1), len(text.split()), 'ok' if text.strip() else 'EMPTY'
    except Exception as e:
        return m, round(time.time() - t, 1), 0, repr(e)[:60]

models = sys.argv[2:]
n = int(sys.argv[1])
with ThreadPoolExecutor(len(models) * n) as ex:
    for r in ex.map(one, [(m, i) for i in range(n) for m in models]):
        print(time.strftime('%H:%M:%S'), *r, flush=True)
