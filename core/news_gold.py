"""
News Gold — اخبار طلای ایران
اسکرپ اخبار طلا و تحلیل احساسات
"""

import time
import threading
from typing import Dict, List, Optional
from core.resilient import session
from core.paths import data as data_path
import os
import json

NEWS_CACHE = data_path("gold_news.json")

def fetch_tgju_news(limit: int = 20) -> List[Dict]:
    """دریافت اخبار طلا از TGJU"""
    news = []
    try:
        sess = session()
        # TGJU news page
        urls = [
            "https://www.tgju.org/news",
            "https://api.tgju.org/v1/market/news",
        ]
        
        for url in urls:
            try:
                r = sess.get(url, timeout=10, headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": "https://www.tgju.org/",
                })
                if r.status_code == 200:
                    # Try JSON
                    try:
                        j = r.json()
                        if isinstance(j, list):
                            for item in j[:limit]:
                                news.append({
                                    "title": item.get("title", ""),
                                    "summary": item.get("summary", "")[:200],
                                    "time": item.get("time", time.time()),
                                    "source": "TGJU",
                                    "url": item.get("url", ""),
                                })
                        elif isinstance(j, dict) and "data" in j:
                            for item in j["data"][:limit]:
                                news.append({
                                    "title": item.get("title", ""),
                                    "summary": item.get("summary", "")[:200],
                                    "time": item.get("time", time.time()),
                                    "source": "TGJU",
                                    "url": item.get("url", ""),
                                })
                    except Exception:
                        # HTML parsing fallback
                        text = r.text
                        import re
                        # Simple title extraction
                        titles = re.findall(r'<a[^>]*class="[^"]*news[^"]*"[^>]*>([^<]+)</a>', text, re.IGNORECASE)
                        for title in titles[:limit]:
                            news.append({
                                "title": title.strip(),
                                "summary": "",
                                "time": time.time(),
                                "source": "TGJU",
                                "url": "",
                            })
                    
                    if news:
                        break
            except Exception:
                continue
    except Exception as e:
        print(f"[news_gold] fetch failed: {e}")
    
    # Fallback synthetic news based on market conditions
    if not news:
        try:
            from core import iran_gold
            from core.bubble import get_all_bubbles
            from core.correlation import get_dollar_impact_on_gold
            
            prices = iran_gold.get_all_live_prices()
            bubbles = get_all_bubbles()
            impact = get_dollar_impact_on_gold()
            
            # Generate news based on actual market data
            if impact.get("usd_change", 0) > 2:
                news.append({
                    "title": f"دلار آزاد {impact['usd_change']:+.1f}% رشد کرد - فشار بر طلای ایران",
                    "title_en": f"USD/IRR up {impact['usd_change']:+.1f}% - pressure on Iran Gold",
                    "summary": "افزایش دلار معمولاً باعث افزایش طلای ایران می‌شود",
                    "time": time.time(),
                    "source": "Analysis",
                    "sentiment": "bullish",
                })
            
            for coin, info in bubbles.items():
                if abs(info["bubble_percent"]) > 10:
                    news.append({
                        "title": f"حباب {coin} به {info['bubble_percent']:+.1f}% رسید",
                        "title_en": f"{coin} bubble {info['bubble_percent']:+.1f}%",
                        "summary": f"قیمت بازار {info['market_price']/10:,.0f} تومان، ذاتی {info['intrinsic_value']/10:,.0f} تومان",
                        "time": time.time(),
                        "source": "Bubble Analysis",
                        "sentiment": "bearish" if info["bubble_percent"] > 0 else "bullish",
                    })
        except Exception:
            pass
    
    # Save cache
    try:
        os.makedirs(os.path.dirname(NEWS_CACHE), exist_ok=True)
        json.dump(news, open(NEWS_CACHE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    except Exception:
        pass
    
    return news[:limit]

def analyze_sentiment(news_list: List[Dict]) -> Dict:
    """تحلیل احساسات اخبار طلا (ساده)"""
    # Keywords for sentiment
    bullish_keywords = ["رشد", "افزایش", "صعود", "خرید", "فرصت", "مثبت", "بالا", "گران", "تقاضا", "عید", "عروسی"]
    bearish_keywords = ["افت", "کاهش", "نزول", "فروش", "ریسک", "حباب", "ارزان", "عرضه", "محرم"]
    
    bullish_count = 0
    bearish_count = 0
    
    for news in news_list:
        title = news.get("title", "") + " " + news.get("summary", "")
        for kw in bullish_keywords:
            if kw in title:
                bullish_count += 1
        for kw in bearish_keywords:
            if kw in title:
                bearish_count += 1
    
    total = bullish_count + bearish_count
    if total == 0:
        sentiment = "neutral"
        score = 0
    else:
        score = (bullish_count - bearish_count) / total
        if score > 0.3:
            sentiment = "bullish"
        elif score < -0.3:
            sentiment = "bearish"
        else:
            sentiment = "neutral"
    
    return {
        "sentiment": sentiment,
        "score": score,
        "bullish_count": bullish_count,
        "bearish_count": bearish_count,
        "total_news": len(news_list),
        "interpretation_fa": (
            f"احساسات {'صعودی' if sentiment=='bullish' else 'نزولی' if sentiment=='bearish' else 'خنثی'} "
            f"({bullish_count} صعودی vs {bearish_count} نزولی)"
        ),
    }

def get_gold_news_with_sentiment(limit: int = 20) -> Dict:
    news = fetch_tgju_news(limit)
    sentiment = analyze_sentiment(news)
    
    return {
        "news": news,
        "sentiment": sentiment,
        "timestamp": time.time(),
    }

if __name__ == "__main__":
    result = get_gold_news_with_sentiment()
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
