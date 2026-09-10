"""
Toman/Rial Conversion — تبدیل تومان و ریال
ابزار تبدیل ریال به تومان برای کاربران ایرانی

1 تومان = 10 ریال
TGJU قیمت‌ها را به ریال می‌دهد، ولی کاربران ایرانی به تومان فکر می‌کنند
"""

from typing import Union

def rial_to_toman(rial: Union[int, float]) -> float:
    """ریال به تومان"""
    return rial / 10

def toman_to_rial(toman: Union[int, float]) -> float:
    """تومان به ریال"""
    return toman * 10

def format_rial(rial: Union[int, float], with_toman: bool = True) -> str:
    """فرمت قیمت ریالی با نمایش تومان"""
    rial = float(rial)
    toman = rial_to_toman(rial)
    
    if with_toman:
        if rial >= 1_000_000_000:
            # میلیارد
            return f"{rial:,.0f} ریال ({toman/1_000_000_000:.2f} میلیارد تومان)"
        elif rial >= 1_000_000:
            return f"{rial:,.0f} ریال ({toman:,.0f} تومان)"
        else:
            return f"{rial:,.0f} ریال ({toman:,.0f} تومان)"
    else:
        return f"{rial:,.0f} ریال"

def format_toman(toman: Union[int, float], with_rial: bool = False) -> str:
    """فرمت قیمت تومانی"""
    toman = float(toman)
    rial = toman_to_rial(toman)
    
    if with_rial:
        return f"{toman:,.0f} تومان ({rial:,.0f} ریال)"
    else:
        return f"{toman:,.0f} تومان"

def parse_price(price_str: str) -> float:
    """
    پارس قیمت از رشته فارسی/انگلیسی
    مثل: "30,000,000 ریال" یا "3,000,000 تومان"
    برمی‌گرداند ریال
    """
    try:
        # Remove commas, spaces, and Persian digits conversion
        s = price_str.replace(",", "").replace("٬", "").replace("،", "")
        
        # Convert Persian digits to English
        persian_to_english = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
        s = s.translate(persian_to_english)
        
        # Extract number
        import re
        match = re.search(r"[\d.]+", s)
        if not match:
            return 0
        
        num = float(match.group())
        
        # Check if it's Toman
        if "تومان" in price_str or "toman" in price_str.lower():
            return toman_to_rial(num)
        else:
            # Assume Rial
            return num
    except Exception:
        return 0

def format_price_smart(price_rial: float, lang: str = "fa") -> str:
    """فرمت هوشمند قیمت بر اساس اندازه"""
    if lang == "fa":
        toman = rial_to_toman(price_rial)
        
        if toman >= 1_000_000_000:
            return f"{toman/1_000_000_000:.2f} میلیارد تومان"
        elif toman >= 1_000_000:
            return f"{toman/1_000_000:.2f} میلیون تومان"
        elif toman >= 1000:
            return f"{toman:,.0f} تومان"
        else:
            return f"{price_rial:,.0f} ریال"
    else:
        return f"{price_rial:,.0f} IRR ({rial_to_toman(price_rial):,.0f} Toman)"

if __name__ == "__main__":
    print(format_rial(300000000))  # 30M Rial = 3M Toman
    print(format_toman(3000000))
    print(format_price_smart(300000000, "fa"))
