import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

st.set_page_config(page_title="AI MASTER STOCK BOT MAX VIP", page_icon="\U0001f451", layout="wide")

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
        score += 8; reasons.append("Gi\u00e1 tr\u00ean EMA20")
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
        score += 7; reasons.append("RSI kh\u1ecfe, ch\u01b0a qu\u00e1 n\u00f3ng")
    elif r.RSI > 75:
        score -= 7; reasons.append("RSI qu\u00e1 cao")
    elif r.RSI < 35:
        score -= 4; reasons.append("RSI y\u1ebfu/qu\u00e1 b\u00e1n")
    if r.RVOL >= 1.2:
        score += 6; reasons.append("Volume tr\u00ean trung b\u00ecnh")
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
        if rev > .15: s += 10; positives.append("T\u0103ng tr\u01b0\u1edfng doanh thu t\u1ed1t")
        elif rev < 0: s -= 8; negatives.append("Doanh thu suy gi\u1ea3m")
    if earn is not None:
        if earn > .15: s += 10; positives.append("T\u0103ng tr\u01b0\u1edfng l\u1ee3i nhu\u1eadn t\u1ed1t")
        elif earn < 0: s -= 8; negatives.append("L\u1ee3i nhu\u1eadn suy gi\u1ea3m")
    if roe is not None:
        if roe > .15: s += 7; positives.append("ROE t\u1ed1t")
        elif roe < .05: s -= 5
    if margin is not None:
        if margin > .15: s += 6; positives.append("Bi\u00ean l\u1ee3i nhu\u1eadn t\u1ed1t")
        elif margin < 0: s -= 7
    if debt is not None:
        if debt < 100: s += 5
        elif debt > 200: s -= 7; negatives.append("\u0110\u00f2n b\u1ea9y cao")
    if pe is not None:
        if 0 < pe < 25: s += 6
        elif pe > 50: s -= 5; negatives.append("\u0110\u1ecbnh gi\u00e1 P/E cao")
    if fcf is not None and fcf > 0:
        s += 4; positives.append("FCF d\u01b0\u01a1ng")

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
        return "RISK-ON \U0001f7e2"
    if result.get("SPY") is False and result.get("QQQ") is False:
        return "RISK-OFF \U0001f534"
    return "MIXED \U0001f7e1"

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
st.title("\U0001f451 AI MASTER STOCK BOT \u2014 MAX VIP FREE")
st.caption("Ph\u00e2n t\u00edch \u0111\u1ecbnh l\u01b0\u1ee3ng mi\u1ec5n ph\u00ed \u00b7 Kh\u00f4ng API tr\u1ea3 ph\u00ed \u00b7 Kh\u00f4ng t\u1ef1 \u0111\u1eb7t l\u1ec7nh")

symbol = st.text_input("Nh\u1eadp m\u00e3 c\u1ed5 phi\u1ebfu", "MU").strip().upper()
analyze = st.button("\U0001f50d PH\u00c2N T\u00cdCH MAX VIP", use_container_width=True)

if analyze:
    if not symbol:
        st.error("H\u00e3y nh\u1eadp m\u00e3 c\u1ed5 phi\u1ebfu.")
        st.stop()

    with st.spinner("\u0110ang l\u1ea5y d\u1eef li\u1ec7u mi\u1ec5n ph\u00ed v\u00e0 t\u00ednh to\u00e1n..."):
        hist, info, news = load_data(symbol)

    if hist.empty or len(hist) < 220:
        st.error("Kh\u00f4ng \u0111\u1ee7 d\u1eef li\u1ec7u l\u1ecbch s\u1eed cho m\u00e3 n\u00e0y.")
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
        signal = "\U0001f7e2 STRONG LONG"
    elif master >= 68:
        signal = "\U0001f7e2 LONG"
    elif master >= 45:
        signal = "\U0001f7e1 NEUTRAL"
    elif master >= 30:
        signal = "\U0001f534 SHORT"
    else:
        signal = "\U0001f534 STRONG SHORT"

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

    st.subheader(f"{symbol} \u2014 {signal}")
    a, b, c = st.columns(3)
    a.metric("Gi\u00e1", f"${price:,.2f}")
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

    st.subheader("\U0001f3af Trade Setup")
    if not np.isnan(sl):
        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("Entry zone", f"${entry_low:,.2f}\u2013${entry_high:,.2f}")
        c2.metric("Stop Loss", f"${sl:,.2f}")
        c3.metric("TP1", f"${tp1:,.2f}")
        c4.metric("TP2", f"${tp2:,.2f}")
        c5.metric("R/R", f"1 : {rr:.1f}")
    else:
        st.info("T\u00edn hi\u1ec7u NEUTRAL: ch\u01b0a c\u00f3 setup Long/Short \u0111\u1ee7 r\u00f5.")

    st.subheader("\U0001f4ca Technical")
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

    st.subheader("\U0001f30e Market Regime")
    st.write(regime)

    st.subheader("\U0001f402 Bull Case")
    for x in reasons + positives:
        st.write("\u2022 " + x)
    if not reasons and not positives:
        st.write("\u2022 Ch\u01b0a c\u00f3 \u0111\u1ee7 d\u1eef li\u1ec7u t\u00edch c\u1ef1c.")

    st.subheader("\U0001f43b Bear / Risk Case")
    for x in negatives:
        st.write("\u2022 " + x)
    if r.RSI > 70:
        st.write("\u2022 RSI cao: r\u1ee7i ro mua \u0111u\u1ed5i.")
    if r.ATR14 / price > .04:
        st.write("\u2022 Bi\u1ebfn \u0111\u1ed9ng cao theo ATR.")
    if not negatives and r.RSI <= 70:
        st.write("\u2022 Ch\u01b0a ph\u00e1t hi\u1ec7n r\u1ee7i ro \u0111\u1ecbnh l\u01b0\u1ee3ng n\u1ed5i b\u1eadt t\u1eeb d\u1eef li\u1ec7u c\u00f3 s\u1eb5n.")

    st.subheader("\U0001f9ea Backtest nhanh")
    bt = backtest(d)
    if bt:
        q1,q2,q3,q4 = st.columns(4)
        q1.metric("Trades", bt["trades"])
        q2.metric("Win rate", f"{bt['winrate']:.1f}%")
        q3.metric("Profit factor", f"{bt['profit_factor']:.2f}" if np.isfinite(bt["profit_factor"]) else "\u221e")
        q4.metric("Max drawdown", f"{bt['max_drawdown']:.1f}%")
        st.caption("Backtest \u0111\u01a1n gi\u1ea3n, kh\u00f4ng bao g\u1ed3m ph\u00ed giao d\u1ecbch, tr\u01b0\u1ee3t gi\u00e1 ho\u1eb7c thu\u1ebf. Kh\u00f4ng d\u00f9ng k\u1ebft qu\u1ea3 l\u1ecbch s\u1eed nh\u01b0 cam k\u1ebft l\u1ee3i nhu\u1eadn t\u01b0\u01a1ng lai.")
    else:
        st.info("Kh\u00f4ng \u0111\u1ee7 t\u00edn hi\u1ec7u \u0111\u1ec3 backtest.")

    st.subheader("\U0001f4f0 News")
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
            st.caption("Ngu\u1ed3n tin kh\u00f4ng tr\u1ea3 v\u1ec1 ti\u00eau \u0111\u1ec1 theo \u0111\u1ecbnh d\u1ea1ng hi\u1ec7n t\u1ea1i.")
    else:
        st.caption("Kh\u00f4ng l\u1ea5y \u0111\u01b0\u1ee3c news t\u1eeb ngu\u1ed3n mi\u1ec5n ph\u00ed \u1edf th\u1eddi \u0111i\u1ec3m n\u00e0y.")

    st.warning("\u0110\u00e2y l\u00e0 c\u00f4ng c\u1ee5 nghi\u00ean c\u1ee9u, kh\u00f4ng ph\u1ea3i l\u1eddi khuy\u00ean \u0111\u1ea7u t\u01b0. D\u1eef li\u1ec7u mi\u1ec5n ph\u00ed c\u00f3 th\u1ec3 ch\u1eadm, thi\u1ebfu ho\u1eb7c b\u1ecb gi\u1edbi h\u1ea1n b\u1edfi nh\u00e0 cung c\u1ea5p.")
else:
    st.info("Nh\u1eadp m\u00e3 c\u1ed5 phi\u1ebfu r\u1ed3i b\u1ea5m **\U0001f50d PH\u00c2N T\u00cdCH MAX VIP**.")
