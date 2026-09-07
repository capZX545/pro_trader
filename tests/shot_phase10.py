import os,sys,time,warnings; warnings.filterwarnings('ignore'); sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ui.theme import I18N, QSS; I18N.lang=sys.argv[1] if len(sys.argv)>1 else 'fa'
from PyQt6 import QtWidgets; app=QtWidgets.QApplication([]); app.setStyleSheet(QSS)
from ui.main_window import MainWindow; w=MainWindow(); w.resize(1500,920); w.show()
def wait(ms):
    t0=time.time()
    while time.time()-t0<ms/1000: app.processEvents(); time.sleep(0.02)
def ww(p,a='w',to=300):
    t0=time.time()
    while time.time()-t0<to:
        app.processEvents(); time.sleep(0.05); k=getattr(p,a,None)
        if k is not None and k.isFinished(): wait(400); return
    print("TIMEOUT",a)
os.makedirs('tests/shots',exist_ok=True); L=I18N.lang
w.goto('nav_quant'); q=w.page('nav_quant')
q.tabs.setCurrentIndex(2); q.bar3.sym.setCurrentText('NVIDIA (NVDA)'); q.bar3.tf.setCurrentText('1d'); q.bar3.set_strategy('davey_robust'); q.run_overfit(); ww(q,'w3'); w.grab().save(f'tests/shots/{L}_q3_overfit.png')
q.tabs.setCurrentIndex(5); q.bar6.sym.setCurrentText('BTC/USDT'); q.bar6.tf.setCurrentText('1h'); q.run_bots(); ww(q,'w6'); w.grab().save(f'tests/shots/{L}_q6_bots.png')
w.goto('nav_chart'); ch=w.page('nav_chart')
for sid in ['chan_kalman','elder_impulse_safezone','jesse_anchor','oneil_sell_rules','freqtrade_sample']:
    ch.bar.set_strategy(sid); ch.run(); ww(ch); w.grab().save(f'tests/shots/{L}_chart_{sid}.png')
print('ok')
