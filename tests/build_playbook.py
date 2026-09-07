import warnings, time, sys; warnings.filterwarnings('ignore')
sys.path.insert(0, "/home/user/ProTrader")
import strategies as S
from core import playbook as PB
t=time.time(); last=[0]
def prog(p, msg):
    if time.time()-last[0] > 20:
        last[0]=time.time(); print(f"{p:3d}% {msg} {time.time()-t:.0f}s", flush=True)
order = sys.argv[1:] or ["1d", "4h", "1h", "15m", "30m", "2h", "12h", "5m", "6h", "1wk", "3d", "3m", "1m"]
pb=PB.build_playbook(S.ALL_STRATEGIES, progress=prog, tfs=order)
print("best_wr:", {tf: pb.get("best_wr", {}).get(tf) for tf in order}, flush=True)
print("DONE", round(time.time()-t), flush=True)
for tf in order:
    for g, rows in pb["best"].get(tf, {}).items():
        if rows: print(tf, g, rows[:4], flush=True)
