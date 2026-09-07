"""Validation Lab page — walk-forward / Monte-Carlo robustness ranking of all strategies."""
import time
from PyQt6 import QtCore, QtWidgets

import strategies as S
from core import validation as V
from .theme import C, t, I18N
from .widgets import Card, StatTile, make_table, cell, ncell, Worker, color_for


def _name(cls):
    return cls.name_fa if I18N.lang == "fa" else cls.name_en


def score_color(s):
    return C["green"] if s >= 55 else (C["yellow"] if s >= 40 else (C["muted"] if s >= 25 else C["red"]))


def verdict(s):
    if s >= 55:
        return t("lab_v_robust"), C["green"]
    if s >= 40:
        return t("lab_v_ok"), C["yellow"]
    if s >= 25:
        return t("lab_v_weak"), C["muted"]
    return t("lab_v_fail"), C["red"]


class ValidationLabPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(10)
        title = QtWidgets.QLabel(t("lab_title"))
        title.setObjectName("h1")
        v.addWidget(title)
        sub = QtWidgets.QLabel(t("lab_sub"))
        sub.setObjectName("subtitle")
        sub.setWordWrap(True)
        v.addWidget(sub)

        top = QtWidgets.QHBoxLayout()
        self.btn = QtWidgets.QPushButton("🧬  " + t("lab_run"))
        self.btn.setObjectName("primary")
        self.btn.clicked.connect(self.run_all)
        top.addWidget(self.btn)
        self.sel_btn = QtWidgets.QPushButton(t("lab_run_sel"))
        self.sel_btn.clicked.connect(self.run_selected)
        top.addWidget(self.sel_btn)
        self.prog = QtWidgets.QProgressBar()
        self.prog.setRange(0, 100)
        self.prog.setValue(0)
        top.addWidget(self.prog, 1)
        self.status = QtWidgets.QLabel("")
        self.status.setObjectName("subtitle")
        top.addWidget(self.status)
        v.addLayout(top)

        tiles = QtWidgets.QHBoxLayout()
        self.t_n = StatTile(t("lab_t_validated"))
        self.t_rob = StatTile(t("lab_t_robust"), color=C["green"])
        self.t_fail = StatTile(t("lab_t_fail"), color=C["red"])
        self.t_ens = StatTile(t("lab_t_ens"), color=C["accent"])
        for x in (self.t_n, self.t_rob, self.t_fail, self.t_ens):
            tiles.addWidget(x)
        v.addLayout(tiles)

        split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.tbl = make_table([t("strategy"), t("category"), t("lab_score"), t("lab_verdict"), t("lab_oos_pf"), t("lab_oos_pos"),
                               t("lab_mc_dd"), t("trades"), t("lab_markets"), t("lab_best")])
        hh = self.tbl.horizontalHeader()
        hh.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Interactive)
        for i, w in enumerate([300, 100, 80, 120, 70, 80, 90, 70, 60, 260]):
            self.tbl.setColumnWidth(i, w)
        self.tbl.itemSelectionChanged.connect(self._detail)
        self.tbl.itemDoubleClicked.connect(self._open)
        split.addWidget(self.tbl)
        right = Card(t("lab_detail"))
        self.det = make_table([t("symbol"), t("timeframe"), t("trades"), t("pf"), t("winrate"), t("return"), t("max_dd"), t("lab_oos_folds"), t("lab_mc_dd")])
        right.v.addWidget(self.det, 1)
        self.expl = QtWidgets.QLabel(t("lab_expl"))
        self.expl.setWordWrap(True)
        self.expl.setObjectName("subtitle")
        right.v.addWidget(self.expl)
        split.addWidget(right)
        split.setSizes([900, 500])
        v.addWidget(split, 1)
        self.refresh()

    # ------------------------------------------------------------------ data
    def refresh(self):
        cache = V.load_cache()
        rows = []
        for cls in S.ALL_STRATEGIES:
            r = cache.get(cls.id)
            rows.append((cls, r))
        rows.sort(key=lambda x: -(x[1]["score"] if x[1] else -1))
        self.tbl.setSortingEnabled(False)
        self.tbl.setRowCount(0)
        n_val = n_rob = n_fail = 0
        for cls, r in rows:
            i = self.tbl.rowCount()
            self.tbl.insertRow(i)
            it = cell(_name(cls))
            it.setData(QtCore.Qt.ItemDataRole.UserRole, cls.id)
            self.tbl.setItem(i, 0, it)
            self.tbl.setItem(i, 1, cell(cls.category, C["muted"]))
            if not r:
                self.tbl.setItem(i, 2, cell("—", C["muted"]))
                self.tbl.setItem(i, 3, cell(t("lab_not_run"), C["muted"]))
                continue
            n_val += 1
            s = r["score"]
            n_rob += s >= 55
            n_fail += s < 25
            vt, vc = verdict(s)
            self.tbl.setItem(i, 2, ncell(s, "{:.0f}", score_color(s)))
            self.tbl.setItem(i, 3, cell(vt, vc))
            self.tbl.setItem(i, 4, ncell(r.get("oos_pf_mean", 0), "{:.2f}", color_for(r.get("oos_pf_mean", 0) - 1)))
            self.tbl.setItem(i, 5, ncell(r.get("oos_pos_ratio", 0) * 100, "{:.0f}%"))
            self.tbl.setItem(i, 6, ncell(r.get("mc_dd95_median", 0), "{:.1f}%", C["red"] if r.get("mc_dd95_median", 0) > 25 else None))
            self.tbl.setItem(i, 7, ncell(r.get("total_trades", 0), "{:.0f}"))
            self.tbl.setItem(i, 8, ncell(r.get("n", 0), "{:.0f}"))
            best = ", ".join(f"{a} {b}" for a, b in r.get("best_markets", [])[:3])
            self.tbl.setItem(i, 9, cell(best, C["muted"]))
        self.tbl.setSortingEnabled(True)
        self.tbl.sortItems(2, QtCore.Qt.SortOrder.DescendingOrder)
        self.t_n.set(f"{n_val} / {len(S.ALL_STRATEGIES)}")
        self.t_rob.set(str(n_rob))
        self.t_fail.set(str(n_fail))
        ens = cache.get("ensemble")
        self.t_ens.set(f"{ens['score']:.0f}" if ens else "—")
        if cache:
            ts = max((r.get("ts", 0) for r in cache.values()), default=0)
            if ts:
                self.status.setText(t("lab_last") + " " + time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)))

    def _detail(self):
        items = self.tbl.selectedItems()
        if not items:
            return
        sid = self.tbl.item(items[0].row(), 0).data(QtCore.Qt.ItemDataRole.UserRole)
        r = V.load_cache().get(sid)
        self.det.setSortingEnabled(False)
        self.det.setRowCount(0)
        if not r:
            return
        for row in r.get("rows", []):
            i = self.det.rowCount()
            self.det.insertRow(i)
            self.det.setItem(i, 0, cell(row.get("symbol", "")))
            self.det.setItem(i, 1, cell(row.get("tf", "")))
            if "error" in row:
                self.det.setItem(i, 2, cell(row["error"][:40], C["red"]))
                continue
            self.det.setItem(i, 2, ncell(row["trades"], "{:.0f}"))
            self.det.setItem(i, 3, ncell(row["pf"], "{:.2f}", color_for(row["pf"] - 1)))
            self.det.setItem(i, 4, ncell(row["wr"], "{:.0f}%"))
            self.det.setItem(i, 5, ncell(row["ret"], "{:+.1f}%", color_for(row["ret"])))
            self.det.setItem(i, 6, ncell(row["dd"], "{:.1f}%", C["red"]))
            folds = " · ".join(("∞" if x == float("inf") else f"{x:.2f}") for x in row.get("oos_pf", []))
            npos = sum(1 for x in row.get("oos_pf", []) if x > 1)
            self.det.setItem(i, 7, cell(folds, C["green"] if npos >= 2 else (C["yellow"] if npos == 1 else C["red"])))
            self.det.setItem(i, 8, ncell(row.get("mc_dd95", 0), "{:.1f}%"))
        self.det.resizeColumnsToContents()

    def _open(self, item):
        sid = self.tbl.item(item.row(), 0).data(QtCore.Qt.ItemDataRole.UserRole)
        r = V.load_cache().get(sid)
        best = r.get("best_markets") if r else None
        if best:
            self.window().open_chart(best[0][0], best[0][1], sid)
        else:
            self.window().open_chart(None, None, sid)

    # ------------------------------------------------------------------ run
    def run_selected(self):
        items = self.tbl.selectedItems()
        if not items:
            return
        sid = self.tbl.item(items[0].row(), 0).data(QtCore.Qt.ItemDataRole.UserRole)
        self._run([S.REGISTRY[sid]])

    def run_all(self):
        # ensemble last, because it consumes the others' results
        classes = [c for c in S.ALL_STRATEGIES if c.id != "ensemble"] + [S.REGISTRY["ensemble"]]
        self._run(classes)

    def _run(self, classes):
        self.btn.setEnabled(False)
        self.sel_btn.setEnabled(False)
        self.status.setText(t("lab_running"))

        def work(progress=None):
            V.run_all(classes, progress=progress)
            return True

        self.w = Worker(work)
        self.w.progress.connect(lambda p, s: (self.prog.setValue(p), self.status.setText(s)))
        self.w.done.connect(self._done)
        self.w.error.connect(lambda e: (self._done(False), QtWidgets.QMessageBox.warning(self, "Error", e)))
        self.w.start()

    def _done(self, ok=True):
        self.btn.setEnabled(True)
        self.sel_btn.setEnabled(True)
        self.prog.setValue(100 if ok else 0)
        self.refresh()
