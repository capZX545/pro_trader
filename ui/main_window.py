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

    # ---- desktop notifications (Phase 12 alerts) + persistence tray (طلای ایران + background analysis)
    def _init_tray(self):
        try:
            from core import alerts as AL
            from core.paths import data as _data
            import json, os
            self.tray = QtWidgets.QSystemTrayIcon(self.windowIcon() if not self.windowIcon().isNull() else self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_ComputerIcon), self)
            self.tray.setToolTip(t("app") + " - Background analysis active")
            
            # Tray menu with persistence options
            self.tray_menu = QtWidgets.QMenu()
            self.tray_menu.setStyleSheet("QMenu { background: #1e1e2f; color: #eee; }")
            
            # Show/Hide
            act_show = self.tray_menu.addAction("📈 Show ProTrader")
            act_show.triggered.connect(lambda: (self.showNormal(), self.raise_(), self.activateWindow()))
            
            self.tray_menu.addSeparator()
            
            # Background status
            try:
                from core import persistence, auto_evolution, iran_gold, resilient
                pid = persistence.get_background_pid()
                act_status = self.tray_menu.addAction(f"⚙️ Background PID: {pid} - Running")
                act_status.setEnabled(False)
                
                # Iran Gold quick price
                try:
                    prices = iran_gold.get_all_live_prices()
                    if prices:
                        self.tray_menu.addSeparator()
                        act_gold_title = self.tray_menu.addAction("💰 طلای ایران - Live:")
                        act_gold_title.setEnabled(False)
                        for sym in ["طلای 18 عیار / 750", "سکه امامی", "دلار آزاد"][:3]:
                            if sym in prices:
                                p = prices[sym]
                                price_str = f"{p['price']:,.0f} {p.get('currency','IRR')}"
                                act = self.tray_menu.addAction(f"  {sym}: {price_str}")
                                act.setEnabled(False)
                except Exception:
                    pass
                
                # Network health
                try:
                    health = resilient.health_check()
                    ok_count = sum(1 for v in health.values() if v)
                    act_net = self.tray_menu.addAction(f"🌐 Network: {ok_count}/{len(health)} OK (anti-filter active)")
                    act_net.setEnabled(False)
                except Exception:
                    pass
                
            except Exception:
                pass
            
            self.tray_menu.addSeparator()
            
            # Evolution status
            act_evo = self.tray_menu.addAction("🧬 Auto-Evolution: خودشو پیشرفت میده")
            act_evo.setEnabled(False)
            
            self.tray_menu.addSeparator()
            
            act_quit = self.tray_menu.addAction("❌ Exit Completely (Stop Background)")
            act_quit.triggered.connect(self._force_quit)
            
            self.tray.setContextMenu(self.tray_menu)
            
            # Double click to show
            self.tray.activated.connect(self._tray_activated)
            
            if QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
                self.tray.show()
                # Show initial message about background persistence
                QtCore.QTimer.singleShot(2000, lambda: self.tray.showMessage(
                    "ProTrader - Background Active",
                    "برنامه در پس‌زمینه فعاله و تحلیل میکنه\nحتی اگه فیلتر وصل نباشه به چارتا وصله\nطلای ایران فعاله",
                    QtWidgets.QSystemTrayIcon.MessageIcon.Information, 5000
                ))
            
            self._notify_sig.connect(self._notify)
            AL.set_desktop_hook(lambda title, body: self._notify_sig.emit(title, body))
            
            # Flag for force quit
            self._force_quit_flag = False
            
        except Exception as e:
            print(f"[tray] init failed: {e}")
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
    
    def _tray_activated(self, reason):
        if reason == QtWidgets.QSystemTrayIcon.ActivationReason.DoubleClick or reason == QtWidgets.QSystemTrayIcon.ActivationReason.Trigger:
            self.showNormal()
            self.raise_()
            self.activateWindow()
    
    def _force_quit(self):
        self._force_quit_flag = True
        self.close()

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
        # === PERSISTENCE MODE: minimize to tray instead of exit ===
        # حتی اگه ران نشده بود بتونه خودش تحلیل کنه - تا وقتی از تسک منیجر متوقف نشده
        try:
            from core.paths import data as _data
            import json, os
            settings_path = _data("settings.json")
            settings = {}
            if os.path.exists(settings_path):
                try:
                    settings = json.load(open(settings_path, encoding="utf-8"))
                except Exception:
                    pass
            
            minimize_to_tray = settings.get("minimize_to_tray", True)
            background_analysis = settings.get("background_analysis", True)
            
            # If force quit flag set (via tray menu Exit), do full exit
            if getattr(self, "_force_quit_flag", False):
                print("[ProTrader] Force quit requested - stopping all background services")
                # stop live sockets / timers cleanly
                for _, _, pg_ in self.pages:
                    for m in ("stop_stream", "stop"):
                        fn = getattr(pg_, m, None)
                        if callable(fn):
                            try:
                                fn()
                            except Exception:
                                pass
                for _, _, pg_ in self.pages:
                    eng = getattr(pg_, "engine", None)
                    if eng is not None and hasattr(eng, "stop"):
                        try:
                            eng.stop()
                        except Exception:
                            pass
                try:
                    from core import maintenance, auto_evolution, iran_gold, persistence
                    maintenance.stop()
                    auto_evolution.stop()
                    iran_gold.stop_background_updater()
                    persistence.stop_background_service()
                except Exception:
                    pass
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
                return
            
            # If minimize to tray enabled and background analysis enabled, hide to tray
            if minimize_to_tray and background_analysis:
                e.ignore()
                self.hide()
                if hasattr(self, "tray") and self.tray.isVisible():
                    self.tray.showMessage(
                        "ProTrader - در پس‌زمینه فعال",
                        "برنامه بسته نشد، در پس‌زمینه تحلیل میکنه\nبرای خروج کامل روی آیکون راست کلیک کنید\nطلای ایران + ضدفیلتر فعال",
                        QtWidgets.QSystemTrayIcon.MessageIcon.Information,
                        4000
                    )
                # Keep background services running
                print("[ProTrader] Minimized to tray - background analysis continues")
                return
        except Exception as ex:
            print(f"[closeEvent] persistence check failed: {ex}")
        
        # Normal close (if minimize_to_tray disabled)
        for _, _, pg_ in self.pages:
            for m in ("stop_stream", "stop"):
                fn = getattr(pg_, m, None)
                if callable(fn):
                    try:
                        fn()
                    except Exception:
                        pass
        for _, _, pg_ in self.pages:
            eng = getattr(pg_, "engine", None)
            if eng is not None and hasattr(eng, "stop"):
                try:
                    eng.stop()
                except Exception:
                    pass
        try:
            from core import maintenance, auto_evolution, iran_gold, persistence
            # Don't stop background if persistence wants to keep alive?
            # For normal close, we keep persistence alive unless force quit
            # So only stop maintenance, keep evolution and iran_gold if background enabled
            from core.paths import data as _data
            import json, os
            settings_path = _data("settings.json")
            settings = {}
            if os.path.exists(settings_path):
                try:
                    settings = json.load(open(settings_path, encoding="utf-8"))
                except Exception:
                    pass
            if not settings.get("background_analysis", True):
                maintenance.stop()
                auto_evolution.stop()
                iran_gold.stop_background_updater()
                persistence.stop_background_service()
            else:
                # Keep background alive, just stop UI-related maintenance?
                # Actually keep all alive
                print("[ProTrader] Keeping background services alive after UI close")
                pass
        except Exception:
            pass
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
