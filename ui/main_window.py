from PyQt6 import QtCore, QtGui, QtWidgets
from .theme import C, QSS, t, I18N
from .pages import DashboardPage, ChartPage, ScannerPage, BacktestPage, AcademyPage, RiskPage, JournalPage, SettingsPage
from .web_page import WebAnalyzerPage
from .lab_page import ValidationLabPage
from .live_page import LiveMarketPage
from .advisor_page import AdvisorPage
from .ml_page import MLPage
from .forward_page import ForwardPage
from .health_page import HealthPage
from .quant_page import QuantLabPage


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
            ("nav_chart", "📈", ChartPage()),
            ("nav_scan", "📡", ScannerPage()),
            ("nav_advisor", "🎯", AdvisorPage()),
            ("nav_forward", "🔬", ForwardPage()),
            ("nav_live", "⚡", LiveMarketPage()),
            ("nav_bt", "🧪", BacktestPage()),
            ("nav_web", "🌐", WebAnalyzerPage()),
            ("nav_lab", "🧬", ValidationLabPage()),
            ("nav_ml", "🧠", MLPage()),
            ("nav_quant", "📐", QuantLabPage()),
            ("nav_academy", "🎓", AcademyPage()),
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
        h.addWidget(self.stack, 1)
        self.nav_group.idClicked.connect(self.stack.setCurrentIndex)
        self.nav_group.button(0).setChecked(True)
        self.pages[0][2].goto.connect(self.goto)
        self.setStatusBar(QtWidgets.QStatusBar())
        self.statusBar().showMessage(t("ready"))
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

    def open_chart(self, sym, tf, sid):
        page = self.pages[1][2]
        self.goto(1)
        if sym is None:
            sym = page.bar.symbol()
        if tf is None:
            tf = page.bar.timeframe()
        page.set_context(sym, tf, sid)
