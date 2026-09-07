"""resumable data fill for the playbook universe (cache-first, so re-runs skip finished symbols)"""
import warnings, time, sys; warnings.filterwarnings('ignore')
sys.path.insert(0, "/home/user/ProTrader")
from core import playbook as PB
from core.data import get_ohlcv
t=time.time()
tfs = sys.argv[1:] or PB.TFS
for tf in tfs:
    for g, syms in PB.GROUPS.items():
        for s in syms:
            try:
                df = get_ohlcv(s, tf, max_age_sec=12*3600)
                print(f"{tf} {s} {len(df)} {time.time()-t:.0f}s", flush=True)
            except Exception as e:
                print(f"{tf} {s} ERR {e}", flush=True)
print("FILL DONE", flush=True)
