# 🚀 ProTrader پیشرفته - قابلیت‌های جدید

## خلاصه تغییرات (چی برنامه رو قوی‌تر می‌کنه)

این نسخه برنامه شما را **پیشرفته و قوی‌تر** می‌کند بدون اینکه چیزی حذف شود. تمام تغییرات additive هستند.

---

## 1. 🛡️ سیستم ضدفیلتر - حتی اگه فیلتر وصل نبود به چارتا وصل میشه

### مشکل قبلی:
- با فیلتر، چارت‌ها خالی می‌موند
- `api.binance.com` ارور 451 می‌داد (فیلتر جغرافیایی)
- Yahoo Finance ارور 429 (rate limit)

### راه‌حل جدید (`core/resilient.py`):
- **DNS-over-HTTPS**: از Cloudflare 1.1.1.1 و Google 8.8.8.8 برای دور زدن DNS hijacking
- **چند میزبان**: برای هر API چندین آدرس جایگزین
  - Binance: `data-api.binance.vision`, `api.binance.com`, `api1`, `api2`, `api3`
  - Yahoo: `query1`, `query2` + API مستقیم
  - TGJU: `api.tgju.org`, `www.tgju.org`, `call1`, `call2`
- **تشخیص خودکار پروکسی**: 
  - V2Ray پورت‌های 10808, 10809
  - Clash پورت 7890, 7891
  - Sing-box, سیستم پروکسی ویندوز
  - متغیرهای محیطی HTTP_PROXY
- **User-Agent چرخشی**: هر درخواست UA متفاوت
- **Retry هوشمند**: exponential backoff + jitter
- **حتی بدون فیلترشکن هم کار می‌کنه**: چون mirror ها رو امتحان می‌کنه

### استفاده:
```python
from core.resilient import session
r = session().get("https://api.binance.com/...")
# خودکار پروکسی رو پیدا می‌کنه و با DoH وصل میشه
```

---

## 2. 🇮🇷 طلای ایران - سیگنال‌دهی و چارتا

### نمادهای جدید (11 نماد):

| فارسی | انگلیسی | Ticker | توضیح |
|-------|---------|--------|-------|
| طلای 18 عیار / 750 | Gold 18K | IR-GOLD-18K | پرکاربردترین طلای ایران |
| طلای 24 عیار | Gold 24K | IR-GOLD-24K | طلای خالص |
| مثقال طلا | Mesghal | IR-MESGHAL | 4.608 گرم 18 عیار |
| انس طلا | Ounce | IR-OUNCE | XAU/USD |
| سکه امامی | Emami Coin | IR-SEKEH-EMAMI | سکه طرح جدید |
| سکه بهار آزادی | Bahar Azadi | IR-SEKEH-BAHAR | طرح قدیم |
| نیم سکه | Half Coin | IR-NIM | 4.066 گرم |
| ربع سکه | Quarter Coin | IR-ROB | 2.032 گرم |
| سکه گرمی | Gram Coin | IR-GERAMI | 1.01 گرم |
| دلار آزاد | USD/IRR Free | IR-USD | دلار بازار آزاد |
| یورو آزاد | EUR Free | IR-EUR | یورو بازار آزاد |

### منابع قیمت:
1. **TGJU.org API** (اصلی): `https://api.tgju.org/v1/market/indicator/summary-table-data`
2. **Alanchand.com** (جایگزین)
3. **Synthetic Fallback**: اگر TGJU فیلتر بود، از `XAU/USD * USD/IRR` محاسبه می‌کنه

### قابلیت‌ها:
- **چارت**: تمام تایم‌فریم‌ها (1m تا 1mo) - برای intraday از synthetic استفاده می‌کنه
- **سیگنال**: تمام 100+ استراتژی روی طلای ایران کار می‌کنن
- **بک‌تست**: PF, WR, تعداد معاملات برای هر نماد
- **لایو**: قیمت هر 30 ثانیه آپدیت
- **واحد**: ریال (با نمایش تومان هم)

### استفاده در UI:
1. از لیست نمادها، دسته **"Iran Gold"** رو انتخاب کن
2. مثلاً "طلای 18 عیار / 750"
3. تایم‌فریم رو انتخاب کن (مثلاً 1h)
4. استراتژی رو انتخاب کن
5. Run بزن - سیگنال‌ها با قیمت ریال میاد

### فایل‌ها:
- `core/iran_gold.py`: دریافت قیمت و OHLCV
- `core/iran_gold_signals.py`: سیگنال‌دهی مخصوص
- `core/data.py`: اضافه شدن به UNIVERSE

---

## 3. 🔄 تحلیل پس‌زمینه - حتی اگه ران نشده بود

### مشکل قبلی:
- برنامه بسته می‌شد، تحلیل متوقف می‌شد
- باید هر بار دستی ران می‌کردی
- با بستن پنجره، همه چیز متوقف می‌شد

### راه‌حل جدید (`core/persistence.py`):

#### Auto-Start (اجرای خودکار):
- **ویندوز**:
  - Registry: `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run`
  - Task Scheduler: تسک `ProTraderBackground` با trigger onlogon
  - Startup Folder: `ProTrader.lnk` یا `.bat`
- **لینوکس**:
  - `~/.config/autostart/protrader.desktop`
  - systemd user service: `~/.config/systemd/user/protrader.service`
- **مک**:
  - LaunchAgent: `~/Library/LaunchAgents/com.protrader.background.plist`

#### Background Service:
- **Minimize to Tray**: به جای بسته شدن، میره تو سینی سیستم
- **تحلیل ادامه داره**: حتی وقتی UI بسته است
- **تا تسک منیجر**: فقط وقتی از Task Manager ببندی متوقف میشه
- **Self-healing**: اگه کرش کنه، خودکار ری‌استارت

#### حالت‌ها:
1. **عادی**: `python main.py` - UI + background
2. **پس‌زمینه**: `python main.py --background` - فقط تحلیل، بدون UI (برای سرور)
3. **Tray**: بستن پنجره = رفتن به tray

#### تنظیمات (Settings):
- ✅ Auto-start on boot
- ✅ Minimize to tray instead of exit
- ✅ Background analysis 24/7

### استفاده:
- اولین بار ران کن: خودکار auto-start فعال میشه
- برنامه رو ببند: میره تو tray، تحلیل ادامه داره
- برای خروج کامل: راست کلیک روی آیکون tray -> Exit Completely
- یا از Task Manager پروسه ProTrader رو ببند

---

## 4. 🧬 خودپیشرفت - خودشو پیشرفت بده

### فایل: `core/auto_evolution.py`

#### چی کار می‌کنه:
1. **تحلیل عملکرد** (هر 1 ساعت):
   - Forward test records رو بررسی می‌کنه
   - استراتژی‌های در حال افت (decaying) رو پیدا می‌کنه: PF قدیم >1.2 و جدید <0.9
   - استراتژی‌های در حال رشد (improving) رو پیدا می‌کنه

2. **بازآموزی ML** (روزانه):
   - مدل meta-label رو با داده‌های جدید retrain می‌کنه
   - اگه `core/ml.py` تابع `train_meta` داشته باشه

3. **تکامل Playbook** (هر 3 روز):
   - Playbook قدیمی (>3 روز) رو آپدیت می‌کنه
   - استراتژی‌های ضعیف رو حذف، قوی‌ها رو تقویت

4. **بهینه‌سازی پارامتر** (هر 6 ساعت):
   - استاپ‌لاس‌های خیلی تنگ رو شناسایی (stop-out سپس برگشت)
   - پیشنهاد widen کردن

5. **خودتأملی** (هر 12 ساعت):
   - خلاصه روزانه: چند استراتژی در حال افت/رشد
   - ذخیره در `evolution_state.json`

#### نسل (Generation):
- هر بار تکامل، generation +1
- در Settings -> Evolution Log ببین
- در tray هم نمایش داده میشه

#### لاگ:
- `data/evolution.log`: تمام کارهای انجام شده
- `data/evolution_state.json`: وضعیت فعلی
- `data/evolution_performance.json`: تحلیل decaying/improving

---

## 5. 📊 بهبودهای دیگر (چی برنامه رو قوی‌تر می‌کنه)

### a) لایه داده قوی‌تر:
- Cache هوشمند با hash keys
- TTL 30 ثانیه برای live، 1 ساعت برای history
- Synthetic fallback برای تمام نمادها

### b) پرفورمنس:
- اولویت پایین برای threadهای پس‌زمینه (Windows BELOW_NORMAL, Unix nice 10)
- Cooperative yielding وقتی UI مشغوله
- GC freeze بعد از startup
- Switch interval 0.001 برای UI روان‌تر

### c) قابلیت اطمینان:
- Crash handler با faulthandler -> `crash.log`
- Uncaught exception logging
- Thread excepthook
- Self-healing loops

### d) امنیت و حریم خصوصی:
- بدون نیاز به API key (همه public)
- ذخیره محلی (بدون cloud)
- پشتیبانی پروکسی برای حریم خصوصی
- DoH برای حریم خصوصی DNS

### e) UI بهبود یافته:
- System tray با قیمت زنده طلای ایران
- نشانگر سلامت شبکه (وضعیت ضدفیلتر)
- نمایش PID پس‌زمینه
- صفحه Settings با toggleهای persistence
- نمایش لاگ evolution
- منوی tray: Show, قیمت طلا, وضعیت شبکه, Exit

### f) Maintenance بهبود یافته:
- هر 15 دقیقه: forward test + Iran Gold + resilient check
- هر 30 دقیقه: آپدیت cache طلای ایران
- هر 30 دقیقه: بررسی سلامت resilient
- هر 1 ساعت: بررسی سریع evolution
- هر 6 ساعت: health autofix
- هر 7 روز: بازسازی کامل playbook

---

## نصب و استفاده برای کاربران ایرانی

### نصب:
```bash
git clone https://github.com/capZX545/pro_trader.git
cd pro_trader
pip install -r requirements.txt
python main.py
```

### بار اول:
- برنامه خودکار auto-start رو فعال می‌کنه
- از شما می‌پرسه آیا می‌خوای در پس‌زمینه فعال باشه

### طلای ایران:
1. دسته "Iran Gold" رو از لیست نمادها انتخاب کن
2. مثلاً "طلای 18 عیار / 750"
3. تمام استراتژی‌ها کار می‌کنن
4. چارت با قیمت ریال

### ضدفیلتر:
- اگه V2Ray/Clash داری، خودکار تشخیص میده
- اگه نداری، با DoH و mirrorها سعی می‌کنه
- حتی بدون فیلترشکن هم کار می‌کنه

### پس‌زمینه:
- برنامه رو ببند: میره تو tray
- تحلیل ادامه داره
- برای خروج کامل: راست کلیک tray -> Exit Completely

### خودپیشرفت:
- Settings -> Evolution Log
- هر روز generation بالاتر میره

---

## فایل‌های جدید

| فایل | توضیح |
|------|-------|
| `core/resilient.py` | لایه ضدفیلتر |
| `core/iran_gold.py` | طلای ایران |
| `core/iran_gold_signals.py` | سیگنال طلای ایران |
| `core/persistence.py` | سرویس پس‌زمینه و auto-start |
| `core/auto_evolution.py` | موتور خودپیشرفت |
| `core/advanced_features.py` | مستندات و status همه قابلیت‌ها |

## فایل‌های تغییر یافته (بدون حذف)

| فایل | تغییر |
|------|-------|
| `core/data.py` | اضافه شدن Iran Gold به UNIVERSE + resilient |
| `core/sources.py` | استفاده از resilient session |
| `core/maintenance.py` | تسک‌های جدید Iran Gold, resilient, evolution |
| `main.py` | پشتیبانی --background + راه‌اندازی سرویس‌ها |
| `ui/main_window.py` | tray با قیمت طلا + minimize to tray |
| `ui/pages.py` | Settings پیشرفته با persistence |
| `requirements.txt` | بدون وابستگی جدید |

---

## تست

```bash
python -m core.resilient
python -m core.iran_gold
python -m core.persistence
python -m core.advanced_features
python main.py --background  # حالت headless
```

---

## نکات امنیتی

- **توکن گیت‌هاب**: بعد از push، توکن رو revoke کن (Settings -> Developer settings -> Personal access tokens)
- توکن‌های قبلی که فرستادی رو حتماً حذف کن
- برنامه هیچ توکنی رو ذخیره نمی‌کنه

---

## نسخه

- **v2.5 Advanced** - 2026-09-10
- Backward compatible
- تمام قابلیت‌های قبلی + جدید
- هیچ چیزی حذف نشده

---

## پشتیبانی

- Issues: https://github.com/capZX545/pro_trader/issues
- تمام کدها مستند و فارسی/انگلیسی

**موفق باشی! 🚀🇮🇷**
