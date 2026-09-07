"""Reusable UI widgets."""
from PyQt6 import QtCore, QtGui, QtWidgets
from .theme import C, t


class Card(QtWidgets.QFrame):
    def __init__(self, title=None, parent=None, obj="card"):
        super().__init__(parent)
        self.setObjectName(obj)
        self.v = QtWidgets.QVBoxLayout(self)
        self.v.setContentsMargins(16, 14, 16, 14)
        self.v.setSpacing(10)
        if title:
            self.title = QtWidgets.QLabel(title)
            self.title.setObjectName("h2")
            self.v.addWidget(self.title)

    def add(self, w):
        self.v.addWidget(w)
        return w


class StatTile(QtWidgets.QFrame):
    def __init__(self, label, value="—", color=None, parent=None):
        super().__init__(parent)
        self.setObjectName("card2")
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(14, 10, 14, 10)
        v.setSpacing(2)
        self.lbl = QtWidgets.QLabel(label)
        self.lbl.setObjectName("statlbl")
        self.val = QtWidgets.QLabel(str(value))
        self.val.setObjectName("stat")
        if color:
            self.val.setStyleSheet(f"color:{color}")
        v.addWidget(self.lbl)
        v.addWidget(self.val)

    def set(self, value, color=None):
        self.val.setText(str(value))
        self.val.setStyleSheet(f"color:{color}" if color else "")


class Badge(QtWidgets.QLabel):
    def __init__(self, text, color=C["accent"], parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(f"background:{color}22; color:{color}; border:1px solid {color}66; border-radius:9px; padding:2px 8px; font-size:11px; font-weight:600;")
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)


def side_badge(side: int):
    return Badge(t("long") if side == 1 else t("short"), C["green"] if side == 1 else C["red"])


def hline():
    f = QtWidgets.QFrame()
    f.setFrameShape(QtWidgets.QFrame.Shape.HLine)
    f.setStyleSheet(f"color:{C['border']}")
    return f


def stars(n, mx=5):
    return "★" * n + "☆" * (mx - n)


def fmt_money(v):
    return f"{v:,.2f}"


def fmt_pct(v):
    return f"{v:+.2f}%"


def color_for(v, invert=False):
    if v is None:
        return C["muted"]
    good = v > 0 if not invert else v < 0
    return C["green"] if good else (C["red"] if v != 0 else C["muted"])


def make_table(headers):
    tb = QtWidgets.QTableWidget(0, len(headers))
    tb.setHorizontalHeaderLabels(headers)
    tb.verticalHeader().setVisible(False)
    tb.setAlternatingRowColors(True)
    tb.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
    tb.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
    tb.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
    tb.horizontalHeader().setStretchLastSection(True)
    tb.setSortingEnabled(True)
    tb.setShowGrid(False)
    return tb


def cell(text, color=None, align_right=False, sort_value=None):
    it = QtWidgets.QTableWidgetItem()
    it.setData(QtCore.Qt.ItemDataRole.DisplayRole, str(text))
    if sort_value is not None:
        it.setData(QtCore.Qt.ItemDataRole.UserRole, sort_value)
    if color:
        it.setForeground(QtGui.QColor(color))
    if align_right:
        it.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
    return it


class NumItem(QtWidgets.QTableWidgetItem):
    def __lt__(self, other):
        a = self.data(QtCore.Qt.ItemDataRole.UserRole)
        b = other.data(QtCore.Qt.ItemDataRole.UserRole)
        try:
            return float(a) < float(b)
        except Exception:
            return super().__lt__(other)


def ncell(value, fmt="{:.2f}", color=None):
    it = NumItem()
    try:
        it.setData(QtCore.Qt.ItemDataRole.DisplayRole, fmt.format(value))
    except Exception:
        it.setData(QtCore.Qt.ItemDataRole.DisplayRole, str(value))
    it.setData(QtCore.Qt.ItemDataRole.UserRole, float(value) if value is not None and value == value and value not in (float("inf"),) else 0.0)
    if color:
        it.setForeground(QtGui.QColor(color))
    it.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
    return it


class Worker(QtCore.QThread):
    done = QtCore.pyqtSignal(object)
    error = QtCore.pyqtSignal(str)
    progress = QtCore.pyqtSignal(int, str)

    def __init__(self, fn, *args, **kw):
        super().__init__()
        self.fn, self.args, self.kw = fn, args, kw

    def run(self):
        try:
            self.done.emit(self.fn(*self.args, progress=self.progress.emit, **self.kw) if "progress" in self.fn.__code__.co_varnames else self.fn(*self.args, **self.kw))
        except Exception as e:
            import traceback
            self.error.emit(f"{e}\n{traceback.format_exc()}")
