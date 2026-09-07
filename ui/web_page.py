"""Web Analyzer page: paste a trading-site URL → structured analysis + live signals on detected instruments."""
import json
import numpy as np
import pandas as pd
from PyQt6 import QtCore, QtGui, QtWidgets

from core.webanalyzer import analyze_url, to_markdown, filter_levels, PageAnalysis
from core.data import UNIVERSE, TIMEFRAMES
from core.backtest import run_backtest
from core import indicators as ta
import strategies as S
from .theme import C, t, I18N
from .widgets import Card, StatTile, Badge, make_table, cell, ncell, Worker, color_for
from .pages import load_data, strat_name


T = {
    "en": dict(title="Web Analyzer", sub="Paste any trading website / article / chart URL. I fetch it, understand what it talks about, "
               "extract instruments, indicators, rules, price levels, red flags — then run my strategies on the detected instruments.",
               url="URL", analyze="Analyze", analyzing="Fetching & analyzing…", overview="Overview", instruments="Instruments detected",
               concepts="Concepts & indicators mentioned", caps="What this site offers for trading", rules="Trading rules extracted from the page",
               prices="Price levels mentioned", flags="Red flags", sentiment="Page sentiment", trust="Trust score", words="Words",
               live="Live analysis of detected instruments (my strategies)", tf="Timeframe", export="Export report (.md)",
               open_chart="Double-click a row to open it on the chart", none="Nothing detected", matched="Matching built-in strategies",
               links="Related links on the page", headings="Page outline", bull="Bullish", bear="Bearish", neutral="Neutral",
               verdict_good="Looks like an educational / analysis page", verdict_warn="Caution: marketing / signal-selling patterns detected",
               verdict_bad="High risk: scam-like promises detected", price_now="Price now", level_dist="Nearest level",
               strat="Strategy", side="Side", fresh="Fresh", wr="WR", pf="PF", rr="R:R", regime="Regime", trend="Trend"),
    "fa": dict(title="تحلیل‌گر وب", sub="آدرس هر سایت / مقاله / چارت تریدینگ را بده. صفحه را می‌گیرم، می‌فهمم درباره چیست، نمادها، اندیکاتورها، "
               "قوانین، سطوح قیمتی و پرچم‌های قرمز را استخراج می‌کنم — بعد استراتژی‌هایم را روی نمادهای پیداشده اجرا می‌کنم.",
               url="آدرس", analyze="تحلیل کن", analyzing="در حال دریافت و تحلیل…", overview="نمای کلی", instruments="نمادهای شناسایی‌شده",
               concepts="مفاهیم و اندیکاتورهای ذکرشده", caps="این سایت برای ترید چه امکاناتی دارد", rules="قوانین معاملاتی استخراج‌شده از صفحه",
               prices="سطوح قیمتی ذکرشده", flags="پرچم‌های قرمز", sentiment="احساسات صفحه", trust="امتیاز اعتماد", words="کلمات",
               live="تحلیل زنده نمادهای پیداشده (استراتژی‌های من)", tf="تایم‌فریم", export="خروجی گزارش (.md)",
               open_chart="برای باز کردن روی چارت، دابل‌کلیک کن", none="چیزی پیدا نشد", matched="استراتژی‌های داخلی مرتبط",
               links="لینک‌های مرتبط در صفحه", headings="ساختار صفحه", bull="صعودی", bear="نزولی", neutral="خنثی",
               verdict_good="به نظر صفحه آموزشی / تحلیلی است", verdict_warn="احتیاط: الگوهای بازاریابی / فروش سیگنال دیده شد",
               verdict_bad="ریسک بالا: وعده‌های کلاهبرداری‌مانند دیده شد", price_now="قیمت فعلی", level_dist="نزدیک‌ترین سطح",
               strat="استراتژی", side="جهت", fresh="تازگی", wr="وین‌ریت", pf="PF", rr="R:R", regime="رژیم", trend="روند"),
}


def tt(k):
    return T.get(I18N.lang, T["en"]).get(k, k)


class WebAnalyzerPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(10)
        title = QtWidgets.QLabel("🌐  " + tt("title"))
        title.setObjectName("title")
        sub = QtWidgets.QLabel(tt("sub"))
        sub.setObjectName("subtitle")
        sub.setWordWrap(True)
        v.addWidget(title)
        v.addWidget(sub)
        bar = QtWidgets.QHBoxLayout()
        self.url = QtWidgets.QLineEdit()
        self.url.setPlaceholderText("https://www.tradingview.com/symbols/BTCUSDT/   ·   https://www.quantifiedstrategies.com/...   ·   any article")
        self.url.setMinimumHeight(36)
        self.tf = QtWidgets.QComboBox()
        self.tf.addItems(TIMEFRAMES)
        self.tf.setCurrentText("4h")
        self.btn = QtWidgets.QPushButton(tt("analyze"))
        self.btn.setObjectName("primary")
        self.btn.setMinimumHeight(36)
        self.exp = QtWidgets.QPushButton(tt("export"))
        bar.addWidget(QtWidgets.QLabel(tt("url")))
        bar.addWidget(self.url, 1)
        bar.addWidget(QtWidgets.QLabel(tt("tf")))
        bar.addWidget(self.tf)
        bar.addWidget(self.btn)
        bar.addWidget(self.exp)
        v.addLayout(bar)
        self.prog = QtWidgets.QProgressBar()
        self.prog.setRange(0, 0)
        self.prog.hide()
        v.addWidget(self.prog)

        tiles = QtWidgets.QHBoxLayout()
        self.t_trust = StatTile(tt("trust"))
        self.t_words = StatTile(tt("words"))
        self.t_sent = StatTile(tt("sentiment"))
        self.t_inst = StatTile(tt("instruments"))
        self.t_conc = StatTile(tt("concepts"))
        for x in (self.t_trust, self.t_words, self.t_sent, self.t_inst, self.t_conc):
            tiles.addWidget(x)
        v.addLayout(tiles)

        self.tabs = QtWidgets.QTabWidget()
        self.report = QtWidgets.QTextBrowser()
        self.report.setOpenExternalLinks(True)
        self.report.setStyleSheet(f"QTextBrowser{{background:{C['panel']}; border:1px solid {C['border']}; border-radius:8px; padding:14px; font-size:13.5px;}}")
        self.tabs.addTab(self.report, tt("overview"))
        self.live_tbl = make_table([t("symbol"), tt("price_now"), tt("trend"), tt("regime"), "RSI", tt("strat"), tt("side"), tt("fresh"), t("stop"), t("target"), tt("rr"), tt("wr"), tt("pf")])
        self.live_tbl.itemDoubleClicked.connect(self._open)
        lw = QtWidgets.QWidget()
        lv = QtWidgets.QVBoxLayout(lw)
        lv.setContentsMargins(0, 6, 0, 0)
        hint = QtWidgets.QLabel(tt("open_chart"))
        hint.setObjectName("subtitle")
        lv.addWidget(hint)
        lv.addWidget(self.live_tbl, 1)
        self.tabs.addTab(lw, tt("live"))
        self.rules_tbl = make_table(["#", tt("rules")])
        self.rules_tbl.setWordWrap(True)
        self.tabs.addTab(self.rules_tbl, tt("rules"))
        self.raw = QtWidgets.QPlainTextEdit()
        self.raw.setReadOnly(True)
        self.raw.setStyleSheet(f"font-family: Consolas, monospace; font-size: 12px; background:{C['panel']};")
        self.tabs.addTab(self.raw, "Text")
        v.addWidget(self.tabs, 1)

        self.btn.clicked.connect(self.analyze)
        self.url.returnPressed.connect(self.analyze)
        self.exp.clicked.connect(self.export)
        self.pa = None
        self.live_rows = []

    # ------------------------------------------------------------------ run
    def analyze(self):
        url = self.url.text().strip()
        if not url:
            return
        tf = self.tf.currentText()
        self.btn.setEnabled(False)
        self.btn.setText(tt("analyzing"))
        self.prog.show()

        def work():
            pa = analyze_url(url)
            live = []
            names = [n for n, _ in pa.instruments[:6]]
            for name in names:
                try:
                    df, ok = load_data(name, tf)
                except Exception:
                    continue
                if not ok or len(df) < 250:
                    continue
                c = df.close
                px = float(c.iloc[-1])
                e50, e200 = ta.ema(c, 50).iloc[-1], ta.ema(c, 200).iloc[-1]
                adx = ta.adx(df)[0].iloc[-1]
                rsi = ta.rsi(c).iloc[-1]
                trend = "bull" if px > e50 > e200 else ("bear" if px < e50 < e200 else "range")
                # best fresh signal among strategies (recent 5 bars, PF>=1)
                best = None
                for cls in S.ALL_STRATEGIES:
                    try:
                        res = cls().run(df)
                    except Exception:
                        continue
                    sig = res.signal.values
                    idx = np.where(sig[-5:] != 0)[0]
                    if not len(idx):
                        continue
                    i = len(df) - 5 + idx[-1]
                    st = run_backtest(df, res).stats
                    if st["trades"] < 10 or st["profit_factor"] < 1.0:
                        continue
                    sl = res.stop.values[i] if res.stop is not None else np.nan
                    tp = res.target.values[i] if res.target is not None else np.nan
                    p0 = df.close.values[i]
                    rr = abs(tp - p0) / abs(p0 - sl) if sl == sl and tp == tp and p0 != sl else 0
                    score = st["profit_factor"] * 10 + st["win_rate"] / 10 + rr * 3 - (len(df) - 1 - i)
                    if best is None or score > best["score"]:
                        best = dict(cls=cls, side=int(sig[i]), ago=len(df) - 1 - i, sl=sl, tp=tp, rr=rr, wr=st["win_rate"], pf=st["profit_factor"], score=score)
                live.append(dict(name=name, px=px, trend=trend, adx=adx, rsi=rsi, best=best))
            filter_levels(pa, {r['name']: r['px'] for r in live})
            return pa, live

        self.w = Worker(work)
        self.w.done.connect(lambda r: self._show(*r))
        self.w.error.connect(lambda e: (self._reset(), QtWidgets.QMessageBox.warning(self, "Error", e)))
        self.w.start()

    def _reset(self):
        self.btn.setEnabled(True)
        self.btn.setText(tt("analyze"))
        self.prog.hide()

    # ------------------------------------------------------------------ render
    def _show(self, pa: PageAnalysis, live):
        self._reset()
        self.pa = pa
        self.live_rows = live
        fa = I18N.lang == "fa"
        d = "rtl" if fa else "ltr"
        tr = pa.trust_score
        self.t_trust.set(f"{tr}/100", C["green"] if tr >= 80 else (C["yellow"] if tr >= 50 else C["red"]))
        self.t_words.set(f"{pa.word_count:,}")
        sc = pa.sentiment.get("score", 0)
        self.t_sent.set(tt("bull") if sc > 0.15 else (tt("bear") if sc < -0.15 else tt("neutral")), C["green"] if sc > 0.15 else (C["red"] if sc < -0.15 else C["yellow"]))
        self.t_inst.set(len(pa.instruments))
        self.t_conc.set(len(pa.concepts))
        verdict = tt("verdict_bad") if tr < 50 else (tt("verdict_warn") if tr < 80 else tt("verdict_good"))
        vcol = C["red"] if tr < 50 else (C["yellow"] if tr < 80 else C["green"])
        li = lambda xs: "".join(f"<li style='margin:3px 0'>{x}</li>" for x in xs)
        chip = lambda txt, col=C["accent"]: f"<span style='color:{col};font-weight:600'>&nbsp;▪ {txt}&nbsp;</span>"
        inst_html = " &nbsp; ".join(chip(f"{n} ×{c}", C["accent2"]) for n, c in pa.instruments) or tt("none")
        conc_html = "".join(
            f"<tr><td style='padding:4px 10px 4px 0'><b>{c}</b> <span style='color:{C['muted']}'>×{n}</span></td>"
            f"<td style='color:{C['muted']}'>{', '.join(strat_name(S.REGISTRY[s]) for s in sids if s in S.REGISTRY) or '—'}</td></tr>"
            for c, n, sids in pa.concepts[:20])
        caps_html = "<table cellpadding='4'><tr>" + "".join(
            (f"<td style='background:{C['panel2']};color:{C['text']}'><b>{c}</b> <span style='color:{C['muted']}'>×{n}</span></td>" + ("</tr><tr>" if (i + 1) % 4 == 0 else ""))
            for i, (c, n) in enumerate(pa.capabilities)) + "</tr></table>" if pa.capabilities else tt("none")
        flags_html = li(f"<b style='color:{C['red']}'>{f}</b><br><span style='color:{C['muted']};font-size:12px'>{ex}</span>" for f, ex in pa.red_flags) or f"<li style='color:{C['green']}'>✔ {tt('none')}</li>"
        prices_html = li(f"<b>{n}</b>: {', '.join(f'{v:,.6g}' for v in lv)}" for n, lv in pa.prices) or f"<li>{tt('none')}</li>"
        heads = li(h for h in pa.headings[:15]) or f"<li>{tt('none')}</li>"
        links = li(f"<a style='color:{C['accent2']}' href='{h}'>{x}</a>" for x, h in pa.links[:15]) or f"<li>{tt('none')}</li>"
        err = f"<p style='color:{C['yellow']}'>⚠ {pa.error}</p>" if pa.error else ""
        html = f"""<div dir='{d}'>
        <h2 style='margin:0;color:white'>{pa.title or pa.domain}</h2>
        <div style='color:{C['muted']}'>{pa.url}</div>{err}
        <p><i>{pa.description}</i></p>
        <p style='background:{vcol}22;border-left:4px solid {vcol};padding:8px 12px;border-radius:6px'><b style='color:{vcol}'>{verdict}</b></p>
        <h3 style='color:{C['accent2']}'>{tt('instruments')}</h3><p>{inst_html}</p>
        <h3 style='color:{C['accent2']}'>{tt('concepts')}</h3>
        <table><tr><th align='left' style='color:{C['muted']}'>{tt('concepts')}</th><th align='left' style='color:{C['muted']}'>{tt('matched')}</th></tr>{conc_html}</table>
        <h3 style='color:{C['accent2']}'>{tt('caps')}</h3><p>{caps_html}</p>
        <h3 style='color:{C['accent2']}'>{tt('prices')}</h3><ul>{prices_html}</ul>
        <h3 style='color:{C['accent2']}'>{tt('sentiment')}</h3>
        <p>{tt('bull')}: <b style='color:{C['green']}'>{pa.sentiment.get('bull', 0)}</b> · {tt('bear')}: <b style='color:{C['red']}'>{pa.sentiment.get('bear', 0)}</b> · score <b>{sc:+.2f}</b>
        &nbsp;·&nbsp; {tt('tf')}: {', '.join(pa.timeframes) or '—'}</p>
        <h3 style='color:{C['red']}'>🚩 {tt('flags')}</h3><ul>{flags_html}</ul>
        <h3 style='color:{C['accent2']}'>{tt('headings')}</h3><ul>{heads}</ul>
        <h3 style='color:{C['accent2']}'>{tt('links')}</h3><ul>{links}</ul>
        </div>"""
        self.report.setHtml(html)
        # rules
        self.rules_tbl.setSortingEnabled(False)
        self.rules_tbl.setRowCount(0)
        for i, r in enumerate(pa.rules, 1):
            row = self.rules_tbl.rowCount()
            self.rules_tbl.insertRow(row)
            self.rules_tbl.setItem(row, 0, cell(i))
            self.rules_tbl.setItem(row, 1, cell(r))
        self.rules_tbl.resizeRowsToContents()
        self.raw.setPlainText(pa.text_preview + ("\n…" if pa.word_count > 250 else ""))
        # live table
        self.live_tbl.setSortingEnabled(False)
        self.live_tbl.setRowCount(0)
        for r in live:
            row = self.live_tbl.rowCount()
            self.live_tbl.insertRow(row)
            it = cell(r["name"])
            it.setData(QtCore.Qt.ItemDataRole.UserRole, (r["name"], r["best"]["cls"].id if r["best"] else None))
            self.live_tbl.setItem(row, 0, it)
            self.live_tbl.setItem(row, 1, ncell(r["px"], "{:,.6g}"))
            tcol = {"bull": C["green"], "bear": C["red"], "range": C["yellow"]}[r["trend"]]
            self.live_tbl.setItem(row, 2, cell({"bull": t("bull"), "bear": t("bear"), "range": t("range")}[r["trend"]], tcol))
            self.live_tbl.setItem(row, 3, cell(f"{t('trending') if r['adx'] > 25 else t('range')} (ADX {r['adx']:.0f})"))
            self.live_tbl.setItem(row, 4, ncell(r["rsi"], "{:.0f}", C["red"] if r["rsi"] > 70 else (C["green"] if r["rsi"] < 30 else None)))
            b = r["best"]
            if b:
                self.live_tbl.setItem(row, 5, cell(strat_name(b["cls"])))
                self.live_tbl.setItem(row, 6, cell(t("long") if b["side"] == 1 else t("short"), C["green"] if b["side"] == 1 else C["red"]))
                self.live_tbl.setItem(row, 7, ncell(b["ago"], "{:.0f} " + t("bars_ago")))
                self.live_tbl.setItem(row, 8, ncell(b["sl"], "{:,.6g}", C["red"]))
                self.live_tbl.setItem(row, 9, ncell(b["tp"], "{:,.6g}", C["green"]))
                self.live_tbl.setItem(row, 10, ncell(b["rr"], "1:{:.1f}"))
                self.live_tbl.setItem(row, 11, ncell(b["wr"], "{:.0f}%"))
                self.live_tbl.setItem(row, 12, ncell(b["pf"], "{:.2f}", color_for(b["pf"] - 1)))
            else:
                self.live_tbl.setItem(row, 5, cell(t("no_signal"), C["muted"]))
        self.live_tbl.setSortingEnabled(True)
        if live:
            self.tabs.setCurrentIndex(0)

    def _open(self, item):
        d = self.live_tbl.item(item.row(), 0).data(QtCore.Qt.ItemDataRole.UserRole)
        if d:
            self.window().open_chart(d[0], self.tf.currentText(), d[1])

    def export(self):
        if not self.pa:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, tt("export"), "web_analysis.md", "Markdown (*.md)")
        if path:
            md = to_markdown(self.pa, I18N.lang)
            if self.live_rows:
                md += "\n## Live analysis\n"
                for r in self.live_rows:
                    b = r["best"]
                    md += f"- **{r['name']}** {r['px']:,.6g} · trend {r['trend']} · ADX {r['adx']:.0f} · RSI {r['rsi']:.0f}"
                    if b:
                        md += f" → {b['cls'].name_en}: {'LONG' if b['side'] == 1 else 'SHORT'} ({b['ago']} bars ago) SL {b['sl']:,.6g} TP {b['tp']:,.6g} R:R 1:{b['rr']:.1f} WR {b['wr']:.0f}% PF {b['pf']:.2f}"
                    md += "\n"
            open(path, "w", encoding="utf-8").write(md)
