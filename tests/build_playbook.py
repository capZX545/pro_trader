import warnings, time, sys; warnings.filterwarnings('ignore')
import strategies as S
from core import playbook as PB
t=time.time()
def prog(p, msg):
    print(f"{p:3d}% {msg} {time.time()-t:.0f}s", flush=True)
pb=PB.build_playbook(S.ALL_STRATEGIES, progress=prog)
print("DONE", round(time.time()-t))
for tf in PB.TFS:
    for g, rows in pb["best"].get(tf, {}).items():
        if rows: print(tf, g, rows[:4])
