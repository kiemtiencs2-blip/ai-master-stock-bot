
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

st.set_page_config(page_title="AI MASTER STOCK BOT MAX VIP", page_icon="đŸ‘‘", layout="wide")

# ---------- Helpers ----------
def fmt_num(x, decimals=2):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "N/A"
    try:
        return f"{x:,.{decimals}f}"
    except Exception:
        return "N/A"

def pct(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "N/A"
    return f"{x:.1f}%"

@st.cache_data(ttl=900, show_spinner=False)
def load_data(symbol):
    t = yf.Ticker(symbol)
    hist = t.history(period="2y", interval="1d", auto_adjust=False)
    info = {}
    try:
        info = t.info or {}
    except Exception:
        pass
    news = []
    try:
        news = t.news or []
    except Exception:
        pass
    return hist, info, news

def indicators(df):
    x = df.copy()
    close = x["Close"]
    high = x["High"]
    low = x["Low"]
    volume = x["Volume"]

    x["EMA20"] = close.ewm(span=20, adjust=False).mean()
    x["EMA50"] = close.ewm(span=50, adjust=False).mean()
    x["EMA200"] = close.ewm(span=200, adjust=False).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    x["RSI"] = 100 - (100 / (1 + rs))

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    x["MACD"] = ema12 - ema26
    x["MACD_signal"] = x["MACD"].ewm(span=9, adjust=False).mean()
    x["MACD_hist"] = x["MACD"] - x["MACD_signal"]

    x["BB_mid"] = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    x["BB_upper"] = x["BB_mid"] + 2 * bb_std
    x["BB_lower"] = x["BB_mid"] - 2 * bb_std

    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    x["ATR14"] = tr.rolling(14).mean()

    x["VolMA20"] = volume.rolling(20).mean()
    x["RVOL"] = volume / x["VolMA20"]

    x["Return20"] = close.pct_change(20) * 100
    x["Return60"] = close.pct_change(60) * 100
    x["52w_high"] = close.rolling(252).max()
    x["52w_low"] = close.rolling(252).min()

    return x.dropna()

def technical_score(d):
    r = d.iloc[-1]
    score = 50
    reasons = []
    if r.Close > r.EMA20:
        score += 8; reasons.append("GiĂ¡ trĂªn EMA20")
    else:
        score -= 8
    if r.EMA20 > r.EMA50:
        score += 8; reasons.append("EMA20 > EMA50")
    else:
        score -= 8
    if r.EMA50 > r.EMA200:
        score += 8; reasons.append("EMA50 > EMA200")
    else:
        score -= 8
    if r.MACD > r.MACD_signal:
        score += 8; reasons.append("MACD bullish")
    else:
        score -= 8
    if 50 <= r.RSI <= 68:
        score += 7; reasons.append("RSI khá»e, chÆ°a quĂ¡ nĂ³ng")
    elif r.RSI > 75:
        score -= 7; reasons.append("RSI quĂ¡ cao")
    elif r.RSI < 35:
        score -= 4; reasons.append("RSI yáº¿u/quĂ¡ bĂ¡n")
    if r.RVOL >= 1.2:
        score += 6; reasons.append("Volume trĂªn trung bĂ¬nh")
    if r.Return20 > 0:
        score += 3
    else:
        score -= 3
    return int(np.clip(score, 0, 100)), reasons

def momentum_score(d):
    r = d.iloc[-1]
    s = 50
    if r.Return20 > 5: s += 12
    elif r.Return20 > 0: s += 6
    else: s -= 8
    if r.Return60 > 10: s += 12
    elif r.Return60 > 0: s += 6
    else: s -= 8
    if r.RVOL > 1.2: s += 8
    return int(np.clip(s, 0, 100))

def fundamental_score(info):
    # Only score metrics that are actually available; missing data never counts as positive.
    s = 50
    positives, negatives = [], []
    def val(key):
        v = info.get(key)
        return v if isinstance(v, (int, float)) and np.isfinite(v) else None

    rev = val("revenueGrowth")
    earn = val("earningsGrowth")
    roe = val("returnOnEquity")
    margin = val("profitMargins")
    debt = val("debtToEquity")
    pe = val("forwardPE") or val("trailingPE")
    fcf = val("freeCashflow")

    if rev is not None:
        if rev > .15: s += 10; positives.append("TÄƒng trÆ°á»Ÿng doanh thu tá»‘t")
        elif rev < 0: s -= 8; negatives.append("Doanh thu suy giáº£m")
    if earn is not None:
        if earn > .15: s += 10; positives.append("TÄƒng trÆ°á»Ÿng lá»£i nhuáº­n tá»‘t")
        elif earn < 0: s -= 8; negatives.append("Lá»£i nhuáº­n suy giáº£m")
    if roe is not None:
        if roe > .15: s += 7; positives.append("ROE tá»‘t")
        elif roe < .05: s -= 5
    if margin is not None:
        if margin > .15: s += 6; positives.append("BiĂªn lá»£i nhuáº­n tá»‘t")
        elif margin < 0: s -= 7
    if debt is not None:
        if debt < 100: s += 5
        elif debt > 200: s -= 7; negatives.append("ÄĂ²n báº©y cao")
    if pe is not None:
        if 0 < pe < 25: s += 6
        elif pe > 50: s -= 5; negatives.append("Äá»‹nh giĂ¡ P/E cao")
    if fcf is not None and fcf > 0:
        s += 4; positives.append("FCF dÆ°Æ¡ng")

    return int(np.clip(s, 0, 100)), positives, negatives

def valuation_score(info):
    s = 50
    pe = info.get("forwardPE") or info.get("trailingPE")
    peg = info.get("pegRatio")
    ps = info.get("priceToSalesTrailing12Months")
    if isinstance(pe, (int,float)) and np.isfinite(pe):
        if 0 < pe < 20: s += 15
        elif pe > 45: s -= 12
    if isinstance(peg, (int,float)) and np.isfinite(peg):
        if 0 < peg < 1.5: s += 15
        elif peg > 3: s -= 12
    if isinstance(ps, (int,float)) and np.isfinite(ps):
        if ps < 5: s += 8
        elif ps > 15: s -= 8
    return int(np.clip(s, 0, 100))

def risk_score(d, info):
    r = d.iloc[-1]
    # Higher score = safer.
    s = 70
    if r.ATR14 / r.Close > .05: s -= 18
    elif r.ATR14 / r.Close > .03: s -= 8
    if r.RVOL > 3: s -= 5
    debt = info.get("debtToEquity")
    if isinstance(debt, (int,float)) and np.isfinite(debt) and debt > 200: s -= 12
    return int(np.clip(s, 0, 100))

def market_regime():
    result = {}
    for sym in ["SPY", "QQQ"]:
        try:
            h = yf.Ticker(sym).history(period="8mo", interval="1d")
            if len(h) > 50:
                c = h["Close"]
                result[sym] = bool(c.iloc[-1] > c.rolling(50).mean().iloc[-1])
        except Exception:
            pass
    if result.get("SPY") and result.get("QQQ"):
        return "RISK-ON đŸŸ¢"
    if result.get("SPY") is False and result.get("QQQ") is False:
        return "RISK-OFF đŸ”´"
    return "MIXED đŸŸ¡"

def backtest(d):
    # Simple, transparent strategy: long when close > EMA20 > EMA50 and MACD bullish.
    x = d.copy()
    x["signal"] = (
        (x["Close"] > x["EMA20"]) &
        (x["EMA20"] > x["EMA50"]) &
        (x["MACD"] > x["MACD_signal"])
    )
    x["ret"] = x["Close"].pct_change().shift(-1)
    trades = x.loc[x["signal"], "ret"].dropna()
    if len(trades) == 0:
        return None
    wins = (trades > 0).sum()
    winrate = wins / len(trades) * 100
    gross_profit = trades[trades > 0].sum()
    gross_loss = abs(trades[trades < 0].sum())
    pf = gross_profit / gross_loss if gross_loss else np.inf
    equity = (1 + trades.fillna(0)).cumprod()
    peak = equity.cummax()
    dd = equity / peak - 1
    return {
        "trades": len(trades),
        "winrate": winrate,
        "profit_factor": pf,
        "max_drawdown": abs(dd.min()) * 100,
    }

# ---------- UI ----------
st.title("đŸ‘‘ AI MASTER STOCK BOT â€” MAX VIP FREE")
st.caption("PhĂ¢n tĂ­ch Ä‘á»‹nh lÆ°á»£ng miá»…n phĂ­ Â· KhĂ´ng API tráº£ phĂ­ Â· KhĂ´ng tá»± Ä‘áº·t lá»‡nh")

symbol = st.text_input("Nháº­p mĂ£ cá»• phiáº¿u", "MU").strip().upper()
analyze = st.button("đŸ” PHĂ‚N TĂCH MAX VIP", use_container_width=True)

if analyze:
    if not symbol:
        st.error("HĂ£y nháº­p mĂ£ cá»• phiáº¿u.")
        st.stop()

    with st.spinner("Äang láº¥y dá»¯ liá»‡u miá»…n phĂ­ vĂ  tĂ­nh toĂ¡n..."):
        hist, info, news = load_data(symbol)

    if hist.empty or len(hist) < 220:
        st.error("KhĂ´ng Ä‘á»§ dá»¯ liá»‡u lá»‹ch sá»­ cho mĂ£ nĂ y.")
        st.stop()

    d = indicators(hist)
    tscore, reasons = technical_score(d)
    mscore = momentum_score(d)
    fscore, positives, negatives = fundamental_score(info)
    vscore = valuation_score(info)
    rscore = risk_score(d, info)

    regime = market_regime()
    macro_score = 75 if "RISK-ON" in regime else 35 if "RISK-OFF" in regime else 55

    # Weighted score. Risk is inverted: higher safety = higher contribution.
    master = (
        tscore * .30 +
        fscore * .20 +
        mscore * .15 +
        vscore * .15 +
        macro_score * .10 +
        rscore * .10
    )
    master = int(round(np.clip(master, 0, 100)))

    if master >= 82:
        signal = "đŸŸ¢ STRONG LONG"
    elif master >= 68:
        signal = "đŸŸ¢ LONG"
    elif master >= 45:
        signal = "đŸŸ¡ NEUTRAL"
    elif master >= 30:
        signal = "đŸ”´ SHORT"
    else:
        signal = "đŸ”´ STRONG SHORT"

    confidence = int(np.clip(50 + abs(master - 50) * 0.85, 50, 92))

    r = d.iloc[-1]
    price = float(r.Close)
    atr = float(r.ATR14)
    entry_low = price - atr * .5
    entry_high = price + atr * .25

    if "LONG" in signal:
        sl = price - 1.5 * atr
        tp1 = price + 1.5 * atr
        tp2 = price + 3.0 * atr
        rr = (tp2 - price) / max(price - sl, 1e-9)
    elif "SHORT" in signal:
        sl = price + 1.5 * atr
        tp1 = price - 1.5 * atr
        tp2 = price - 3.0 * atr
        rr = (price - tp2) / max(sl - price, 1e-9)
    else:
        sl = tp1 = tp2 = np.nan
        rr = np.nan

    st.subheader(f"{symbol} â€” {signal}")
    a, b, c = st.columns(3)
    a.metric("GiĂ¡", f"${price:,.2f}")
    b.metric("MAX SCORE", f"{master}/100")
    c.metric("Confidence", f"{confidence}%")

    st.divider()
    cols = st.columns(6)
    for col, name, value in zip(
        cols,
        ["Technical","Fundamental","Momentum","Valuation","Macro","Risk"],
        [tscore,fscore,mscore,vscore,macro_score,rscore]
    ):
        col.metric(name, f"{value}/100")

    st.subheader("đŸ¯ Trade Setup")
    if not np.isnan(sl):
        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("Entry zone", f"${entry_low:,.2f}â€“${entry_high:,.2f}")
        c2.metric("Stop Loss", f"${sl:,.2f}")
        c3.metric("TP1", f"${tp1:,.2f}")
        c4.metric("TP2", f"${tp2:,.2f}")
        c5.metric("R/R", f"1 : {rr:.1f}")
    else:
        st.info("TĂ­n hiá»‡u NEUTRAL: chÆ°a cĂ³ setup Long/Short Ä‘á»§ rĂµ.")

    st.subheader("đŸ“ Technical")
    st.dataframe(
        pd.DataFrame({
            "Metric": ["RSI","MACD","EMA20","EMA50","EMA200","ATR14","RVOL","20D Return","60D Return"],
            "Value": [
                f"{r.RSI:.1f}", f"{r.MACD:.3f}", f"${r.EMA20:,.2f}",
                f"${r.EMA50:,.2f}", f"${r.EMA200:,.2f}", f"${r.ATR14:,.2f}",
                f"{r.RVOL:.2f}x", f"{r.Return20:.1f}%", f"{r.Return60:.1f}%"
            ]
        }),
        hide_index=True, use_container_width=True
    )

    st.subheader("đŸŒ Market Regime")
    st.write(regime)

    st.subheader("đŸ‚ Bull Case")
    for x in reasons + positives:
        st.write("â€¢ " + x)
    if not reasons and not positives:
        st.write("â€¢ ChÆ°a cĂ³ Ä‘á»§ dá»¯ liá»‡u tĂ­ch cá»±c.")

    st.subheader("đŸ» Bear / Risk Case")
    for x in negatives:
        st.write("â€¢ " + x)
    if r.RSI > 70:
        st.write("â€¢ RSI cao: rá»§i ro mua Ä‘uá»•i.")
    if r.ATR14 / price > .04:
        st.write("â€¢ Biáº¿n Ä‘á»™ng cao theo ATR.")
    if not negatives and r.RSI <= 70:
        st.write("â€¢ ChÆ°a phĂ¡t hiá»‡n rá»§i ro Ä‘á»‹nh lÆ°á»£ng ná»•i báº­t tá»« dá»¯ liá»‡u cĂ³ sáºµn.")

    st.subheader("đŸ§ª Backtest nhanh")
    bt = backtest(d)
    if bt:
        q1,q2,q3,q4 = st.columns(4)
        q1.metric("Trades", bt["trades"])
        q2.metric("Win rate", f"{bt['winrate']:.1f}%")
        q3.metric("Profit factor", f"{bt['profit_factor']:.2f}" if np.isfinite(bt["profit_factor"]) else "âˆ")
        q4.metric("Max drawdown", f"{bt['max_drawdown']:.1f}%")
        st.caption("Backtest Ä‘Æ¡n giáº£n, khĂ´ng bao gá»“m phĂ­ giao dá»‹ch, trÆ°á»£t giĂ¡ hoáº·c thuáº¿. KhĂ´ng dĂ¹ng káº¿t quáº£ lá»‹ch sá»­ nhÆ° cam káº¿t lá»£i nhuáº­n tÆ°Æ¡ng lai.")
    else:
        st.info("KhĂ´ng Ä‘á»§ tĂ­n hiá»‡u Ä‘á»ƒ backtest.")

    st.subheader("đŸ“° News")
    if news:
        shown = 0
        for item in news[:8]:
            content = item.get("content", item)
            title = content.get("title") if isinstance(content, dict) else None
            link = content.get("canonicalUrl", {}).get("url") if isinstance(content, dict) and isinstance(content.get("canonicalUrl"), dict) else None
            if title:
                shown += 1
                if link:
                    st.markdown(f"- [{title}]({link})")
                else:
                    st.write("- " + title)
        if shown == 0:
            st.caption("Nguá»“n tin khĂ´ng tráº£ vá» tiĂªu Ä‘á» theo Ä‘á»‹nh dáº¡ng hiá»‡n táº¡i.")
    else:
        st.caption("KhĂ´ng láº¥y Ä‘Æ°á»£c news tá»« nguá»“n miá»…n phĂ­ á»Ÿ thá»i Ä‘iá»ƒm nĂ y.")

    st.warning("ÄĂ¢y lĂ  cĂ´ng cá»¥ nghiĂªn cá»©u, khĂ´ng pháº£i lá»i khuyĂªn Ä‘áº§u tÆ°. Dá»¯ liá»‡u miá»…n phĂ­ cĂ³ thá»ƒ cháº­m, thiáº¿u hoáº·c bá»‹ giá»›i háº¡n bá»Ÿi nhĂ  cung cáº¥p.")
else:
    st.info("Nháº­p mĂ£ cá»• phiáº¿u rá»“i báº¥m **đŸ” PHĂ‚N TĂCH MAX VIP**.")
