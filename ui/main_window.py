from PyQt6 import QtCore, QtGui, QtWidgets
from .theme import C, QSS, t, I18N
from .pages import DashboardPage, ChartPage, ScannerPage, BacktestPage, AcademyPage, RiskPage, JournalPage, SettingsPage
from .web_page import WebAnalyzerPage
from .lab_page import ValidationLabPage
from .live_page import LiveMarketPage
from .fast_page import FastSignalsPage
from .advisor_page import AdvisorPage
from .ml_page import MLPage
from .forward_page import ForwardPage
from .health_page import HealthPage
from .desk_page import DeskPage
from .vision_page import VisionPage
from .ai_page import AIPage
from .quant_page import QuantLabPage
from .portfolio_page import PortfolioPage

# Optional advanced TradingView page - safe fallback if missing
try:
    from .tradingview_page import TradingViewAdvancedPage
    HAS_TV = True
except Exception:
    HAS_TV = False
    TradingViewAdvancedPage = None

# Strategy Intelligence - هوش استراتژی
try:
    from .strategy_intelligence_page import StrategyIntelligencePage
    HAS_INTEL = True
except Exception as e:
    print(f"[MainWindow] Strategy Intelligence not available: {e}")
    HAS_INTEL = False
    StrategyIntelligencePage = None



class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(t("app"))
        self.resize(1500, 920)
        self.setMinimumSize(1100, 700)
        root = QtWidgets.QWidget()
        self.setCentralWidget(root)
        h = QtWidgets.QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        if I18N.rtl():
            self.setLayoutDirection(QtCore.Qt.LayoutDirection.RightToLeft)

        side = QtWidgets.QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(220)
        sv = QtWidgets.QVBoxLayout(side)
        sv.setContentsMargins(12, 16, 12, 16)
        sv.setSpacing(4)
        brand = QtWidgets.QLabel("◆ " + t("app"))
        brand.setWordWrap(True)
        brand.setObjectName("brand")
        sv.addWidget(brand)
        sv.addSpacing(12)
        self.stack = QtWidgets.QStackedWidget()
        self.pages = [
            ("nav_dash", "🏠", DashboardPage()),
            ("nav_desk", "🗞", DeskPage()),
            ("nav_chart", "📈", ChartPage()),
            ("nav_tv", "📊", TradingViewAdvancedPage() if HAS_TV and TradingViewAdvancedPage is not None else ChartPage()),
            ("nav_intelligence", "🧠", StrategyIntelligencePage() if HAS_INTEL and StrategyIntelligencePage is not None else ChartPage()),
            ("nav_scan", "📡", ScannerPage()),
            ("nav_advisor", "🎯", AdvisorPage()),
            ("nav_forward", "🔬", ForwardPage()),
            ("nav_live", "⚡", LiveMarketPage()),
            ("nav_fast", "🎯", FastSignalsPage()),
            ("nav_bt", "🧪", BacktestPage()),
            ("nav_web", "🌐", WebAnalyzerPage()),
            ("nav_lab", "🧬", ValidationLabPage()),
            ("nav_ml", "🧠", MLPage()),
            ("nav_quant", "📐", QuantLabPage()),
            ("nav_vision", "👁", VisionPage()),
            ("nav_ai", "🤖", AIPage()),
            ("nav_academy", "🎓", AcademyPage()),
            ("nav_portfolio", "💼", PortfolioPage()),
            ("nav_risk", "🛡", RiskPage()),
            ("nav_journal", "📓", JournalPage()),
            ("nav_health", "🩺", HealthPage()),
            ("nav_settings", "⚙", SettingsPage()),
        ]
        self.nav_group = QtWidgets.QButtonGroup(self)
        self.nav_group.setExclusive(True)
        for i, (key, icon, page) in enumerate(self.pages):
            b = QtWidgets.QPushButton(f"{icon}   {t(key)}")
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            self.nav_group.addButton(b, i)
            sv.addWidget(b)
            self.stack.addWidget(page)
            if key == "nav_academy":
                sv.addSpacing(8)
        sv.addStretch()
        disc = QtWidgets.QLabel(t("disclaimer"))
        disc.setWordWrap(True)
        disc.setStyleSheet(f"color:{C['muted']}; font-size:10px;")
        sv.addWidget(disc)
        h.addWidget(side)
        # ---- global clock strip (Phase 18): computer clock = master clock of every section + world clock in the top corner
        right = QtWidgets.QWidget(); rv = QtWidgets.QVBoxLayout(right); rv.setContentsMargins(0, 0, 0, 0); rv.setSpacing(0)
        self.clock_bar = QtWidgets.QFrame(); self.clock_bar.setObjectName("clockbar"); self.clock_bar.setFixedHeight(26)
        cb = QtWidgets.QHBoxLayout(self.clock_bar); cb.setContentsMargins(14, 0, 14, 0); cb.setSpacing(18)
        self.lbl_local = QtWidgets.QLabel(); self.lbl_local.setStyleSheet(f"color:{C['accent2']};font-weight:600;font-family:monospace;")
        self.lbl_world = QtWidgets.QLabel(); self.lbl_world.setStyleSheet(f"color:{C['muted']};font-family:monospace;font-size:11px;")
        cb.addWidget(self.lbl_local); cb.addStretch(); cb.addWidget(self.lbl_world)
        rv.addWidget(self.clock_bar); rv.addWidget(self.stack, 1)
        h.addWidget(right, 1)
        self._clock_timer = QtCore.QTimer(self); self._clock_timer.timeout.connect(self._tick_clock); self._clock_timer.start(1000)
        self._tick_clock()
        self.nav_group.idClicked.connect(self.stack.setCurrentIndex)
        self.nav_group.button(0).setChecked(True)
        self.pages[0][2].goto.connect(self.goto)
        self.setStatusBar(QtWidgets.QStatusBar())
        self.statusBar().showMessage(t("ready"))
        self._init_tray()

    def _tick_clock(self):
        try:
            from core import clock
            loc, day, utc = clock.now_strings()
            self.lbl_local.setText(f"🖥 {day}  {loc}  ({clock.tz_name()})")
            self.lbl_world.setText(clock.world_line())
        except Exception:
            pass

    # ---- desktop notifications (Phase 12 alerts)
    def _init_tray(self):
        try:
            from core import alerts as AL
            self.tray = QtWidgets.QSystemTrayIcon(self.windowIcon() if not self.windowIcon().isNull() else self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_ComputerIcon), self)
            self.tray.setToolTip(t("app"))
            self.tray.activated.connect(lambda r: (self.showNormal(), self.raise_()))
            if QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
                self.tray.show()
            self._notify_sig.connect(self._notify)
            AL.set_desktop_hook(lambda title, body: self._notify_sig.emit(title, body))
        except Exception:
            pass

    _notify_sig = QtCore.pyqtSignal(str, str)

    def _notify(self, title, body):
        try:
            if getattr(self, "tray", None) and self.tray.isVisible():
                self.tray.showMessage(title, body, QtWidgets.QSystemTrayIcon.MessageIcon.Information, 15000)
            self.statusBar().showMessage(f"🔔 {title}: {body.splitlines()[0]}", 30000)
        except Exception:
            pass
        QtCore.QTimer.singleShot(300, self.pages[0][2].refresh)

    def index_of(self, key):
        for i, (k, _, _) in enumerate(self.pages):
            if k == key:
                return i
        return 0

    def page(self, key):
        return self.pages[self.index_of(key)][2]

    def goto(self, i):
        if isinstance(i, str):
            i = self.index_of(i)
        self.nav_group.button(i).setChecked(True)
        self.stack.setCurrentIndex(i)

    def closeEvent(self, e):
        # stop live sockets / timers cleanly so the process exits (Windows would otherwise keep a ghost process)
        for _, _, pg_ in self.pages:
            for m in ("stop_stream", "stop"):
                fn = getattr(pg_, m, None)
                if callable(fn):
                    try:
                        fn()
                    except Exception:
                        pass
        for _, _, pg_ in self.pages:                      # Live-Market engine
            eng = getattr(pg_, "engine", None)
            if eng is not None and hasattr(eng, "stop"):
                try:
                    eng.stop()
                except Exception:
                    pass
        try:
            from core import maintenance; maintenance.stop()
        except Exception:
            pass
        # Destroying a running QThread aborts the process ("QThread: Destroyed while thread is still running")
        try:
            import time as _t
            from ui.widgets import _LIVE_WORKERS
            deadline = _t.time() + 4
            for w in list(_LIVE_WORKERS):
                try:
                    w.cancel(); w.wait(max(1, int((deadline - _t.time()) * 1000)))
                except Exception:
                    pass
        except Exception:
            pass
        super().closeEvent(e)

    def open_chart(self, sym, tf, sid):
        page = self.pages[1][2]
        self.goto(1)
        if sym is None:
            sym = page.bar.symbol()
        if tf is None:
            tf = page.bar.timeframe()
        page.set_context(sym, tf, sid)