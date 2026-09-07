import os,sys,time,warnings; warnings.filterwarnings('ignore'); R=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0,R); os.chdir(R)
from ui.theme import I18N, QSS; I18N.lang=sys.argv[1] if len(sys.argv)>1 else 'fa'
from PyQt6 import QtWidgets; app=QtWidgets.QApplication([]); app.setStyleSheet(QSS)
from ui.main_window import MainWindow; w=MainWindow(); w.resize(1500,920); w.show()
def wait(ms):
    t0=time.time()
    while time.time()-t0<ms/1000: app.processEvents(); time.sleep(0.02)
def ww(p,to=400):
    t0=time.time()
    while time.time()-t0<to:
        app.processEvents(); time.sleep(0.05)
        if p.workers and all(k.isFinished() for k in p.workers): wait(400); return
    print("TIMEOUT")
os.makedirs('tests/shots',exist_ok=True); L=I18N.lang
w.goto('nav_ai'); p=w.page('nav_ai'); wait(300)
p.tabs.setCurrentIndex(0); p.run_fc(); ww(p); print(p.status.text()); w.grab().save(f'tests/shots/{L}_ai_fc.png')
p.tabs.setCurrentIndex(1); p.run_sent(); ww(p); print(p.status.text()); w.grab().save(f'tests/shots/{L}_ai_sent.png')
p.tabs.setCurrentIndex(2); p.rl_ep.setValue(10); p.rl_seeds.setValue(2); p.run_rl(); ww(p); print(p.status.text()); w.grab().save(f'tests/shots/{L}_ai_rl.png')
p.tabs.setCurrentIndex(3); p.run_eng(); ww(p); print(p.status.text()); w.grab().save(f'tests/shots/{L}_ai_eng.png')
print('ok')
p.tabs.setCurrentIndex(4); p.run_an(); ww(p); print(p.status.text()); p.an_q.setText('روند چیه؟' if L=='fa' else 'what is the trend?'); p.ask_an(); wait(200); w.grab().save(f'tests/shots/{L}_ai_an.png'); print('ok2')
