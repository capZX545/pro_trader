"""Headless smoke test: opens each page, runs the main actions, and saves screenshots."""
import os, sys, json, time
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import warnings; warnings.filterwarnings("ignore")
from PyQt6 import QtWidgets, QtCore, QtGui
from ui.theme import QSS, I18N

lang = sys.argv[1] if len(sys.argv) > 1 else "en"
I18N.lang = lang
app = QtWidgets.QApplication([])
app.setStyle("Fusion"); app.setStyleSheet(QSS)
from ui.main_window import MainWindow
w = MainWindow()
w.resize(1500, 920)
w.show()
out = os.path.join(os.path.dirname(__file__), "shots"); os.makedirs(out, exist_ok=True)
errors = []

def wait(ms):
    t0 = time.time()
    while time.time() - t0 < ms / 1000:
        app.processEvents(); time.sleep(0.02)

def wait_worker(page, attr="w", timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        app.processEvents(); time.sleep(0.05)
        wk = getattr(page, attr, None)
        if wk is not None and wk.isFinished():
            wait(400); return True
    return False

def shot(name):
    app.processEvents()
    w.grab().save(os.path.join(out, f"{lang}_{name}.png"))
    print("saved", name)

# dashboard (auto refresh)
dash = w.pages[0][2]
wait(500); wait_worker(dash); shot("1_dashboard")
# chart
w.goto('nav_chart'); ch = w.page('nav_chart')
ch.bar.set_strategy("ict_fvg"); ch.run(); wait_worker(ch); shot("2_chart")
# scanner (restrict to crypto for speed)
w.goto('nav_scan'); sc = w.page('nav_scan')
for c, cb in sc.cats.items(): cb.setChecked(c == "Crypto")
sc.tf.setCurrentText("4h"); sc.recent.setValue(5); sc.minpf.setValue(0.8)
sc.scan(); wait_worker(sc, timeout=180); shot("3_scanner")
# backtester
w.goto('nav_bt'); bt = w.page('nav_bt')
bt.bar.tf.setCurrentText("1d"); bt.bar.set_strategy("turtle"); bt.run(); wait_worker(bt); shot("4_backtest")
bt.compare(); wait_worker(bt, "w2", timeout=120); shot("4b_compare")
# web analyzer
w.goto('nav_web'); wp = w.page('nav_web'); wp.url.setText("https://www.tradingview.com/symbols/BTCUSDT/"); wp.analyze(); wait_worker(wp, timeout=180); shot("4c_web")
wp.tabs.setCurrentIndex(1); shot("4d_web_live")
# academy
w.goto('nav_lab'); lab = w.page('nav_lab'); lab.tbl.selectRow(0); wait(400); shot("7_lab")
w.goto('nav_ml'); mlp = w.page('nav_ml'); mlp.bar.sym.setCurrentText("BTC/USDT"); mlp.bar.tf.setCurrentText("1h"); mlp.load_saved(); wait(1500); shot("8_ml")
w.goto('nav_advisor'); ad = w.page('nav_advisor'); ad.bar.sym.setCurrentText("NVIDIA (NVDA)"); ad.run(); wait_worker(ad, timeout=120); wait(300); shot("3_advisor")
w.goto('nav_live'); lv = w.page('nav_live'); lv.topn.setValue(15); lv.toggle(); wait(30000); shot("4_live"); lv.toggle()
w.goto('nav_academy'); ac = w.page('nav_academy'); ac.list.setCurrentRow(list(s.id for s in __import__('strategies').ALL_STRATEGIES).index("ict_ob")); wait(300); shot("9_academy"); ac.tabs.setCurrentIndex(1); wait(300); shot("9b_indicators"); ac.tabs.setCurrentIndex(0)
w.goto("nav_risk"); wait(300); shot("10_risk")
w.goto('nav_journal'); j = w.page('nav_journal'); j.entry.setValue(100); j.stop.setValue(98); j.exit.setValue(105); j.notes.setText("test"); j.add(); wait(200); shot("11_journal")
j.rows.clear(); j.save()
w.goto("nav_settings"); wait(200); shot("12_settings")
w.goto("nav_forward"); fw = w.page("nav_forward"); fw.update_now(); wait_worker(fw, timeout=120); wait(300); shot("13_forward")
w.goto("nav_health"); hp = w.page("nav_health"); wait_worker(hp, timeout=60); wait(300); shot("14_health")
print("DONE")
