"""
Jalali Calendar Support — تقویم شمسی
پشتیبانی از تاریخ شمسی برای کاربران ایرانی

Features:
- Convert Gregorian to Jalali and vice versa
- Persian month names
- Trading calendar for Iran (holidays, weekends)
- Seasonal patterns for gold (e.g., قبل عید، محرم)
"""

from datetime import datetime, date, timedelta
from typing import Tuple, Optional

# Try to use jdatetime if available, otherwise fallback to simple algorithm
try:
    import jdatetime
    HAS_JDATETIME = True
except ImportError:
    HAS_JDATETIME = False

PERSIAN_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"
]

PERSIAN_MONTHS_EN = [
    "Farvardin", "Ordibehesht", "Khordad", "Tir", "Mordad", "Shahrivar",
    "Mehr", "Aban", "Azar", "Dey", "Bahman", "Esfand"
]

PERSIAN_WEEKDAYS = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]
PERSIAN_WEEKDAYS_EN = ["Shanbeh", "Yekshanbeh", "Doshanbeh", "Seshanbeh", "Chaharshanbeh", "Panjshanbeh", "Jomeh"]

def gregorian_to_jalali(gy: int, gm: int, gd: int) -> Tuple[int, int, int]:
    """Convert Gregorian to Jalali"""
    if HAS_JDATETIME:
        try:
            jd = jdatetime.date.fromgregorian(day=gd, month=gm, year=gy)
            return jd.year, jd.month, jd.day
        except Exception:
            pass
    
    # Fallback algorithm (approximate)
    # This is a simplified version, for accurate conversion install jdatetime
    # Using formula from https://github.com/jalaali/jalaali-js
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    
    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621
    
    gy2 = gm > 2
    days = (365 * gy) + ((gy + 3) // 4) - ((gy + 99) // 100) + ((gy + 399) // 400) - 80 + gd + g_d_m[gm - 1] + gy2
    
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    
    if days < 186:
        jm = 1 + (days // 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + ((days - 186) // 30)
        jd = 1 + ((days - 186) % 30)
    
    return jy, jm, jd

def jalali_to_gregorian(jy: int, jm: int, jd: int) -> Tuple[int, int, int]:
    """Convert Jalali to Gregorian"""
    if HAS_JDATETIME:
        try:
            gd = jdatetime.date(jy, jm, jd).togregorian()
            return gd.year, gd.month, gd.day
        except Exception:
            pass
    
    # Fallback
    jy += 1595
    days = -355668 + (365 * jy) + ((jy // 33) * 8) + (((jy % 33) + 3) // 4) + jd
    
    if jm < 7:
        days += (jm - 1) * 31
    else:
        days += ((jm - 7) * 30) + 186
    
    gy = 400 * (days // 146097)
    days %= 146097
    
    if days > 36524:
        gy += 100 * ((days - 1) // 36524)
        days = (days - 1) % 36524
        if days >= 365:
            days += 1
    
    gy += 4 * (days // 1461)
    days %= 1461
    
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    
    gd = days + 1
    sal_a = [0, 31, 28 if (gy % 4 != 0 or gy % 100 == 0) or (gy % 400 != 0) else 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    
    gm = 0
    while gm < 13 and gd > sal_a[gm]:
        gd -= sal_a[gm]
        gm += 1
    
    return gy, gm, gd

def now_jalali() -> Tuple[int, int, int]:
    """Get current Jalali date"""
    now = datetime.now()
    return gregorian_to_jalali(now.year, now.month, now.day)

def format_jalali(jy: int, jm: int, jd: int, lang: str = "fa", with_weekday: bool = False) -> str:
    """Format Jalali date"""
    if lang == "fa":
        month_name = PERSIAN_MONTHS[jm - 1] if 1 <= jm <= 12 else str(jm)
        s = f"{jd} {month_name} {jy}"
        if with_weekday:
            # Calculate weekday (approximate)
            try:
                gy, gm, gd = jalali_to_gregorian(jy, jm, jd)
                wd = datetime(gy, gm, gd).weekday()
                # Convert to Persian weekday (Saturday = 0)
                persian_wd = (wd + 2) % 7
                s = f"{PERSIAN_WEEKDAYS[persian_wd]}، {s}"
            except Exception:
                pass
        return s
    else:
        month_name = PERSIAN_MONTHS_EN[jm - 1] if 1 <= jm <= 12 else str(jm)
        return f"{jd} {month_name} {jy}"

def is_iran_holiday(jy: int, jm: int, jd: int) -> bool:
    """Check if Jalali date is Iran holiday (simplified)"""
    # Friday is weekend in Iran
    try:
        gy, gm, gd = jalali_to_gregorian(jy, jm, jd)
        dt = datetime(gy, gm, gd)
        # Friday = 4 in Python weekday (Monday=0)
        if dt.weekday() == 4:
            return True
        
        # Some fixed holidays (simplified)
        holidays = [
            (1, 1), (1, 2), (1, 3), (1, 4),  # Nowruz
            (1, 12),  # Islamic Republic Day
            (1, 13),  # Nature Day
            (3, 14),  # Khordad 14
            (3, 15),  # Khordad 15
            (11, 22),  # Bahman 22
        ]
        if (jm, jd) in holidays:
            return True
    except Exception:
        pass
    return False

def get_seasonal_pattern() -> dict:
    """الگوی فصلی طلا در ایران"""
    jy, jm, jd = now_jalali()
    
    patterns = {
        "season": "",
        "season_en": "",
        "gold_demand": "normal",  # low, normal, high, very_high
        "reason_fa": "",
        "reason_en": "",
        "historical_effect": "",
    }
    
    if jm in [10, 11, 12, 1]:  # دی، بهمن، اسفند، فروردین - قبل عید
        patterns.update({
            "season": "قبل عید و عید نوروز",
            "season_en": "Before Nowruz",
            "gold_demand": "very_high",
            "reason_fa": "تقاضای طلا برای عید نوروز و هدیه",
            "reason_en": "High gold demand for Nowruz gifts",
            "historical_effect": "قیمت معمولاً افزایشی",
        })
    elif jm in [2, 3]:  # اردیبهشت، خرداد - بعد عید
        patterns.update({
            "season": "بعد از عید",
            "season_en": "After Nowruz",
            "gold_demand": "low",
            "reason_fa": "کاهش تقاضا بعد از عید",
            "reason_en": "Low demand after Nowruz",
            "historical_effect": "قیمت معمولاً کاهشی یا رنج",
        })
    elif jm in [6, 7]:  # مهر، آبان - محرم و صفر
        patterns.update({
            "season": "محرم و صفر",
            "season_en": "Muharram & Safar",
            "gold_demand": "low",
            "reason_fa": "کاهش خرید طلا در ماه‌های محرم و صفر",
            "reason_en": "Low demand in Muharram & Safar",
            "historical_effect": "قیمت معمولاً کاهشی",
        })
    elif jm in [4, 5]:  # تیر، مرداد - تابستان و عروسی‌ها
        patterns.update({
            "season": "فصل عروسی",
            "season_en": "Wedding Season",
            "gold_demand": "high",
            "reason_fa": "تقاضای طلا برای مراسم عروسی",
            "reason_en": "High demand for weddings",
            "historical_effect": "قیمت معمولاً افزایشی",
        })
    else:
        patterns.update({
            "season": "عادی",
            "season_en": "Normal",
            "gold_demand": "normal",
            "reason_fa": "تقاضای عادی",
            "reason_en": "Normal demand",
            "historical_effect": "روند عادی بازار",
        })
    
    patterns["jalali_date"] = format_jalali(jy, jm, jd, "fa")
    patterns["jalali_date_en"] = format_jalali(jy, jm, jd, "en")
    patterns["month"] = jm
    patterns["is_holiday"] = is_iran_holiday(jy, jm, jd)
    
    return patterns

def to_jalali_string(dt: datetime, lang: str = "fa") -> str:
    """Convert datetime to Jalali string"""
    jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
    return format_jalali(jy, jm, jd, lang)

if __name__ == "__main__":
    jy, jm, jd = now_jalali()
    print(f"امروز: {format_jalali(jy, jm, jd, 'fa', True)}")
    print(f"Today: {format_jalali(jy, jm, jd, 'en')}")
    print(f"Seasonal: {get_seasonal_pattern()}")
