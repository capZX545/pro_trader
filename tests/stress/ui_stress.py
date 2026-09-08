"""UI stress / stall profiler (dev tool, not part of pytest).
    QT_QPA_PLATFORM=offscreen PROTRADER_DATA=/tmp/sd PROTRADER_TRAIN_DELAY=2 python tests/stress/ui_stress.py [seconds]
Drives the real MainWindow: page switching, double-runs, live chart stream, Live-Market engine, self-training ON.
Reports UI-loop lag percentiles, where the main thread stalled (>0.7 s) and crash.log contents."""
import sys, os, time, random, threading, traceback, collections, faulthandler
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT); os.chdir(ROOT)
faulthandler.enable(); sys.setswitchinterval(0.001)
DUR = int(sys.argv[1]) if len(sys.argv) > 1 else 150

# --- main-thread stall watchdog
_main = threading.main_thread().ident; _beat = [time.time()]; hits = collections.Counter()
def _wd():
    while True:
        time.sleep(0.1)
        if time.time() - _beat[0] > 0.35:
            fr = sys._current_frames().get(_main)
            if fr:
                st = traceback.extract_stack(fr)
                hits[" <- ".join(f"{f.name}@{os.path.basename(f.filename)}:{f.lineno}" for f in st[::-1] if ROOT in f.filename)[:300]] += 1
threading.Thread(target=_wd, daemon=True).start()

import main as M
M._install_crash_handlers()
from PyQt6 import QtWidgets, QtCore
from ui.theme import QSS, I18N; I18N.lang = "fa"
app = QtWidgets.QApplication([]); app.setStyle("Fusion"); app.setStyleSheet(QSS)
from ui.main_window import MainWindow
w = MainWindow(); w.resize(1500, 900); w.show()
from core import maintenance; maintenance.start()
import gc
_gct=[0]; gcl=[]
def _gcb(ph, info):
    if ph=='start': _gct[0]=time.time()
    else:
        d=time.time()-_gct[0]
        if d>0.05: gcl.append((round(d,3), info['generation'], round(time.time()-T0,1)))
gc.callbacks.append(_gcb)
lag = []; lagt = []; T0 = time.time(); last = [time.time()]
tm = QtCore.QTimer(); tm.setInterval(50)
def beat():
    now = time.time(); lag.append(now - last[0] - 0.05); lagt.append((now - last[0] - 0.05, round(now - T0, 1))); last[0] = now; _beat[0] = now
tm.timeout.connect(beat); tm.start()
random.seed(1)
keys = ["nav_dash", "nav_chart", "nav_live", "nav_scan", "nav_bt", "nav_advisor", "nav_forward", "nav_health", "nav_portfolio", "nav_chart", "nav_dash", "nav_live"]
t0 = time.time(); step = 0
while time.time() - t0 < DUR:
    app.processEvents(); time.sleep(0.005)
    if int(time.time() - t0) // 6 > step:
        step += 1; k = keys[step % len(keys)]; i = w.index_of(k); w.goto(i); pg = w.pages[i][2]
        try:
            if k == "nav_chart":
                pg.bar.tf.setCurrentText(random.choice(["1m", "5m", "1h"])); pg.run(); pg.run()
            elif k == "nav_live":
                if getattr(pg, "engine", None) is None:
                    pg.toggle()
            elif k == "nav_bt": pg.run()
            elif k == "nav_dash": pg.refresh()
            elif k == "nav_scan" and step < 12 and hasattr(pg, "run"): pg.run()
            elif hasattr(pg, "refresh"): pg.refresh()
        except Exception as e:
            print("ACTION ERR", k, e)
        print(f"{int(time.time() - t0):3d}s {k:14s} train={maintenance.STATE.get('stage')} {str(maintenance.STATE.get('detail', ''))[:30]}", flush=True)
import numpy as np
a = np.array(lag) * 1000
print("UI loop lag ms: p50 %.0f p95 %.0f p99 %.0f max %.0f" % (np.percentile(a, 50), np.percentile(a, 95), np.percentile(a, 99), a.max()))
print("worst lag events (s, at t):", sorted(lagt)[-6:])
print("slow GC passes (s, gen, at t):", gcl[-10:], "gc.get_count", gc.get_count(), "objects", len(gc.get_objects()))
print("--- main-thread stall sites (0.25 s samples) ---")
for k, v in hits.most_common(6): print(v, k)
from core.paths import data as _d
print("crash.log:", open(_d("crash.log")).read()[-2000:] if os.path.exists(_d("crash.log")) else "none")
w.close(); maintenance.stop(); print("clean exit")
