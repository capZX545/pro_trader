
"""
Iran Gold Dashboard — داشبورد اختصاصی طلای ایران
"""

from PyQt6 import QtCore, QtGui, QtWidgets
import time

from .theme import C, t, I18N
from .widgets import Card, StatTile, make_table, cell, ncell, color_for, Worker

class IranGoldPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(12)
        title = QtWidgets.QLabel("🇮🇷 طلای ایران - Iran Gold Dashboard")
        title.setObjectName("h1")
        v.addWidget(title)
        sub = QtWidgets.QLabel("قیمت زنده طلا، سکه، حباب، همبستگی، آربیتراژ و سیگنال‌های طلای ایران")
        sub.setObjectName("subtitle")
        sub.setWordWrap(True)
        v.addWidget(sub)
        top = QtWidgets.QHBoxLayout()
        self.refresh_btn = QtWidgets.QPushButton("🔄 بروزرسانی")
        self.refresh_btn.setObjectName("primary")
        self.refresh_btn.clicked.connect(self.refresh)
        self.auto_cb = QtWidgets.QCheckBox("بروزرسانی خودکار (30 ثانیه)")
        self.auto_cb.setChecked(True)
        top.addWidget(self.refresh_btn)
        top.addWidget(self.auto_cb)
        top.addStretch()
        self.status_lbl = QtWidgets.QLabel("آماده")
        self.status_lbl.setObjectName("subtitle")
        top.addWidget(self.status_lbl)
        v.addLayout(top)
        tiles = QtWidgets.QHBoxLayout()
        self.t_gold18 = StatTile("طلای 18 عیار", color=C["accent"])
        self.t_emami = StatTile("سکه امامی", color=C["accent2"])
        self.t_dollar = StatTile("دلار آزاد", color=C["green"])
        self.t_bubble = StatTile("بیشترین حباب", color=C["yellow"])
        self.t_arb = StatTile("فرصت آربیتراژ", color=C["red"])
        for tile in (self.t_gold18, self.t_emami, self.t_dollar, self.t_bubble, self.t_arb):
            tiles.addWidget(tile)
        v.addLayout(tiles)
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        left_card = Card("💰 قیمت زنده - Live Prices")
        self.price_table = make_table(["نماد", "قیمت (ریال)", "قیمت (تومان)", "تغییر", "واحد"])
        left_card.v.addWidget(self.price_table, 1)
        splitter.addWidget(left_card)
        right_card = Card("🎈 حباب سکه‌ها - Bubble Analysis")
        self.bubble_table = make_table(["سکه", "بازار", "ذاتی", "حباب %", "سیگنال"])
        right_card.v.addWidget(self.bubble_table, 1)
        splitter.addWidget(right_card)
        splitter.setSizes([500, 500])
        v.addWidget(splitter, 1)
        bottom_split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        arb_card = Card("🔍 آربیتراژ - Arbitrage")
        self.arb_table = make_table(["نماد", "اختلاف %", "سیگنال", "توضیح"])
        arb_card.v.addWidget(self.arb_table, 1)
        bottom_split.addWidget(arb_card)
        corr_card = Card("🔗 همبستگی - Correlation & Dollar Impact")
        self.corr_text = QtWidgets.QTextBrowser()
        self.corr_text.setStyleSheet(f"background:{C['panel']}; border:1px solid {C['border']}; border-radius:8px; padding:10px;")
        corr_card.v.addWidget(self.corr_text, 1)
        bottom_split.addWidget(corr_card)
        sig_card = Card("📡 سیگنال‌های طلای ایران - Iran Gold Signals")
        self.sig_table = make_table(["نماد", "استراتژی", "جهت", "قیمت", "امتیاز", "WR%", "توضیح"])
        sig_card.v.addWidget(self.sig_table, 1)
        bottom_split.addWidget(sig_card)
        bottom_split.setSizes([300, 300, 400])
        v.addWidget(bottom_split, 1)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(30000)
        QtCore.QTimer.singleShot(500, self.refresh)

    def refresh(self):
        if not self.auto_cb.isChecked() and self.sender() == self.timer:
            return
        self.status_lbl.setText("در حال بروزرسانی...")
        self.refresh_btn.setEnabled(False)
        def _do():
            result = {}
            try:
                from core import iran_gold
                prices = iran_gold.get_all_live_prices()
                result["prices"] = prices
            except Exception as e:
                result["prices"] = {}
                result["prices_error"] = str(e)
            try:
                from core.bubble import get_all_bubbles, get_bubble_signal
                bubbles = get_all_bubbles()
                signals = {}
                for coin in bubbles.keys():
                    signals[coin] = get_bubble_signal(coin)
                result["bubbles"] = bubbles
                result["bubble_signals"] = signals
            except Exception as e:
                result["bubbles"] = {}
                result["bubble_error"] = str(e)
            try:
                from core.arbitrage import detect_gold_arbitrage
                arb = detect_gold_arbitrage()
                result["arbitrage"] = arb
            except Exception as e:
                result["arbitrage"] = []
                result["arb_error"] = str(e)
            try:
                from core.correlation import analyze_iran_gold_correlations, get_dollar_impact_on_gold
                from core.jalali import get_seasonal_pattern
                corr = analyze_iran_gold_correlations()
                impact = get_dollar_impact_on_gold()
                seasonal = get_seasonal_pattern()
                result["correlation"] = corr
                result["impact"] = impact
                result["seasonal"] = seasonal
            except Exception as e:
                result["correlation"] = {}
                result["corr_error"] = str(e)
            try:
                from core.iran_gold_signals import get_all_iran_gold_signals
                sigs = get_all_iran_gold_signals(timeframe="1d", min_score=30)
                result["signals"] = sigs
            except Exception as e:
                result["signals"] = {}
                result["signals_error"] = str(e)
            return result

        def _done(res):
            self._update_ui(res)
            self.status_lbl.setText(f"آخرین بروزرسانی: {time.strftime('%H:%M:%S')}")
            self.refresh_btn.setEnabled(True)

        def _err(e):
            self.status_lbl.setText(f"خطا: {e}")
            self.refresh_btn.setEnabled(True)

        w = Worker(lambda: _do())
        w.done.connect(_done)
        w.error.connect(_err)
        w.start()

    def _update_ui(self, res):
        prices = res.get("prices", {})
        self.price_table.setRowCount(0)
        max_bubble = 0
        max_bubble_coin = ""
        for sym, data in prices.items():
            r = self.price_table.rowCount()
            self.price_table.insertRow(r)
            price = data.get("price", 0)
            price_toman = price / 10
            change = data.get("change", 0)
            self.price_table.setItem(r, 0, cell(sym))
            self.price_table.setItem(r, 1, ncell(price, "{:,.0f}"))
            self.price_table.setItem(r, 2, ncell(price_toman, "{:,.0f}"))
            self.price_table.setItem(r, 3, ncell(change, "{:+.2f}%", color_for(change)))
            self.price_table.setItem(r, 4, cell(data.get("currency", "IRR")))
            if "18 عیار" in sym:
                self.t_gold18.set(f"{price_toman:,.0f} تومان", color_for(change))
            elif "امامی" in sym:
                self.t_emami.set(f"{price_toman:,.0f} تومان", color_for(change))
            elif "دلار آزاد" in sym:
                self.t_dollar.set(f"{price_toman:,.0f} تومان", color_for(change))
        bubbles = res.get("bubbles", {})
        bubble_signals = res.get("bubble_signals", {})
        self.bubble_table.setRowCount(0)
        for coin, info in bubbles.items():
            r = self.bubble_table.rowCount()
            self.bubble_table.insertRow(r)
            market = info["market_price"] / 10
            intrinsic = info["intrinsic_value"] / 10
            bubble_pct = info["bubble_percent"]
            sig = bubble_signals.get(coin, {})
            signal = sig.get("signal", "") if sig else ""
            self.bubble_table.setItem(r, 0, cell(coin))
            self.bubble_table.setItem(r, 1, ncell(market, "{:,.0f}"))
            self.bubble_table.setItem(r, 2, ncell(intrinsic, "{:,.0f}"))
            self.bubble_table.setItem(r, 3, ncell(bubble_pct, "{:+.1f}%", color_for(-bubble_pct)))
            self.bubble_table.setItem(r, 4, cell(signal, C["green"] if "BUY" in signal else C["red"] if "SELL" in signal else C["muted"]))
            if abs(bubble_pct) > abs(max_bubble):
                max_bubble = bubble_pct
                max_bubble_coin = coin
        if max_bubble_coin:
            self.t_bubble.set(f"{max_bubble_coin}: {max_bubble:+.1f}%", color_for(-max_bubble))
        arb = res.get("arbitrage", [])
        self.arb_table.setRowCount(0)
        for opp in arb[:10]:
            r = self.arb_table.rowCount()
            self.arb_table.insertRow(r)
            self.arb_table.setItem(r, 0, cell(opp["symbol"]))
            self.arb_table.setItem(r, 1, ncell(opp["diff_percent"], "{:+.2f}%", color_for(-opp["diff_percent"])))
            self.arb_table.setItem(r, 2, cell(opp["signal"], C["green"] if "BUY" in opp["signal"] else C["red"]))
            self.arb_table.setItem(r, 3, cell(opp.get("reason_fa", "")[:50]))
        if arb:
            best = arb[0]
            self.t_arb.set(f"{best['symbol']}: {best['diff_percent']:+.1f}%", C["yellow"])
        else:
            self.t_arb.set("فرصتی نیست", C["muted"])
        corr = res.get("correlation", {})
        impact = res.get("impact", {})
        seasonal = res.get("seasonal", {})
        html = f"""
        <div style='color:{C['text']}; font-size:13px; line-height:1.6'>
        <h3 style='color:{C['accent2']}; margin:5px 0'>📅 الگوی فصلی</h3>
        <p>تاریخ شمسی: {seasonal.get('jalali_date','')} - {seasonal.get('season','')}<br>
        تقاضا: {seasonal.get('gold_demand','')} - {seasonal.get('reason_fa','')}<br>
        اثر تاریخی: {seasonal.get('historical_effect','')}</p>
        <h3 style='color:{C['accent2']}; margin:10px 0 5px'>💵 تأثیر دلار</h3>
        <p>{impact.get('interpretation_fa','')}</p>
        <p>طلا: {impact.get('gold_18k_change',0):+.2f}% | دلار: {impact.get('usd_change',0):+.2f}% | انس: {impact.get('xau_change',0):+.2f}%</p>
        <h3 style='color:{C['accent2']}; margin:10px 0 5px'>🔗 همبستگی‌ها</h3>
        """
        for key, info in corr.items():
            if "error" in info:
                continue
            corr_val = info.get("overall_correlation", 0)
            html += f"<p>{info.get('pair','')}: {corr_val:.2f} ({info.get('strength','')}) - {info.get('interpretation_fa','')}</p>"
        html += "</div>"
        self.corr_text.setHtml(html)
        signals = res.get("signals", {})
        self.sig_table.setRowCount(0)
        for sym, sig_list in signals.items():
            for sig in sig_list[:3]:
                r = self.sig_table.rowCount()
                self.sig_table.insertRow(r)
                self.sig_table.setItem(r, 0, cell(sym))
                self.sig_table.setItem(r, 1, cell(sig.get("sid","")))
                side = sig.get("side",0)
                self.sig_table.setItem(r, 2, cell("🟢 خرید" if side>0 else "🔴 فروش", C["green"] if side>0 else C["red"]))
                self.sig_table.setItem(r, 3, ncell(sig.get("px",0), "{:,.0f}"))
                self.sig_table.setItem(r, 4, ncell(sig.get("score",0), "{:.0f}"))
                self.sig_table.setItem(r, 5, ncell(sig.get("wr",0), "{:.0f}%"))
                self.sig_table.setItem(r, 6, cell(sig.get("verdict","")))

    def stop(self):
        try:
            self.timer.stop()
        except Exception:
            pass
