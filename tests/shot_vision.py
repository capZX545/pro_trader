import os,sys,time,warnings; warnings.filterwarnings('ignore'); R=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0,R); os.chdir(R)
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
os.makedirs('tests/shots',exist_ok=True); L=I18N.lang
w.goto('nav_vision'); v=w.page('nav_vision'); wait(300)
v.load_path('tests/vision_samples/tv_channel.png'); ww(v,'w'); v.selftest(); ww(v,'w2'); w.grab().save(f'tests/shots/{L}_vision.png'); print('ok')
