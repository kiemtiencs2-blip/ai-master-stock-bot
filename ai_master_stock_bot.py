import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(
    page_title="AI MASTER STOCK BOT MAX VIP FREE",
    page_icon="đŸ“",
    layout="wide"
)

def safe_float(x, default=np.nan):
    try:
        if x is None:
            return default
        x = float(x)
        if np.isnan(x) or np.isfinite(x) is False:
            return default
        return x
    except Exception:
        return default

def fmt(x, decimals=2):
    x = safe_float(x)
    return "N/A" if np.isnan(x) else f"{x:.{decimals}f}"

def pct(x):
    x = safe_float(x)
    return "N/A" if np.isnan(x) else f"{x * 100:.1f}%"

def clamp(x, low=0, high=100):
    return int(np.clip(round(x), low, high))

def calculate_indicators(hist):
    close = hist["Close"].astype(float)
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    macd_fast = close.ewm(span=12, adjust=False).mean()
    macd_slow = close.ewm(span=26, adjust=False).mean()
    macd = macd_fast - macd_slow
    signal = macd.ewm(span=9, adjust=False).mean()

    high = hist["High"].astype(float)
    low = hist["Low"].astype(float)
    tr = pd.concat(
        [high - low, abs(high - close.shift()), abs(low - close.shift())],
        axis=1
    ).max(axis=1)
    atr14 = tr.rolling(14).mean()

    volume = hist["Volume"].astype(float)
    avg_volume = volume.rolling(20).mean()

    return {
        "price": close.iloc[-1],
        "ema20": ema20.iloc[-1],
        "ema50": ema50.iloc[-1],
        "ema200": ema200.iloc[-1],
        "rsi": rsi.iloc[-1],
        "macd": macd.iloc[-1],
        "signal": signal.iloc[-1],
        "macd_bull": macd.iloc[-1] > signal.iloc[-1],
        "atr": atr14.iloc[-1],
        "rvol": volume.iloc[-1] / avg_volume.iloc[-1] if avg_volume.iloc[-1] else np.nan,
        "return20": close.iloc[-1] / close.iloc[-21] - 1 if len(close) > 21 else np.nan,
        "return60": close.iloc[-1] / close.iloc[-61] - 1 if len(close) > 61 else np.nan,
    }

def technical_score(ind):
    score = 50
    score += 10 if ind["price"] > ind["ema20"] else -10
    score += 10 if ind["ema20"] > ind["ema50"] else -10
    score += 10 if ind["ema50"] > ind["ema200"] else -10
    score += 10 if ind["macd_bull"] else -10

    rsi = ind["rsi"]
    if 50 <= rsi < 70:
        score += 10
    elif rsi < 30:
        score += 5

    return clamp(score)

def get_fundamentals(info):
    vals = {
        "revenue_growth": safe_float(info.get("revenueGrowth")),
        "earnings_growth": safe_float(info.get("earningsGrowth")),
        "roe": safe_float(info.get("returnOnEquity")),
        "profit_margin": safe_float(info.get("profitMargins")),
        "operating_margin": safe_float(info.get("operatingMargins")),
        "debt_equity": safe_float(info.get("debtToEquity")),
        "current_ratio": safe_float(info.get("currentRatio")),
        "forward_pe": safe_float(info.get("forwardPE")),
        "trailing_pe": safe_float(info.get("trailingPE")),
        "peg": safe_float(info.get("pegRatio")),
        "free_cash_flow": safe_float(info.get("freeCashflow")),
    }

    score = 50
    if not np.isnan(vals["revenue_growth"]):
        score += 10 if vals["revenue_growth"] > .10 else (-5 if vals["revenue_growth"] < 0 else 0)
    if not np.isnan(vals["earnings_growth"]):
        score += 10 if vals["earnings_growth"] > .10 else (-5 if vals["earnings_growth"] < 0 else 0)
    if not np.isnan(vals["roe"]) and vals["roe"] > .15:
        score += 10
    if not np.isnan(vals["profit_margin"]) and vals["profit_margin"] > .10:
        score += 5
    if not np.isnan(vals["operating_margin"]) and vals["operating_margin"] > .10:
        score += 5
    if not np.isnan(vals["free_cash_flow"]) and vals["free_cash_flow"] > 0:
        score += 10
    if not np.isnan(vals["debt_equity"]):
        score += 5 if vals["debt_equity"] < 100 else -5
    if not np.isnan(vals["current_ratio"]) and vals["current_ratio"] > 1.2:
        score += 5
    if not np.isnan(vals["forward_pe"]):
        if 0 < vals["forward_pe"] < 25:
            score += 5
        elif vals["forward_pe"] > 50:
            score -= 5

    vals["score"] = clamp(score)
    return vals

def market_regime():
    try:
        spy = yf.Ticker("SPY").history(period="1y", auto_adjust=False)
        if spy.empty:
            return "UNKNOWN", 50

        close = spy["Close"].astype(float)
        ema50 = close.ewm(span=50, adjust=False).mean().iloc[-1]
        ema200 = close.ewm(span=200, adjust=False).mean().iloc[-1]
        price = close.iloc[-1]

        score = 50
        score += 15 if price > ema50 else -15
        score += 20 if ema50 > ema200 else -20
        score += 15 if price > ema200 else -15
        score = clamp(score)

        if score >= 65:
            return "RISK-ON", score
        if score <= 35:
            return "RISK-OFF", score
        return "NEUTRAL", score
    except Exception:
        return "UNKNOWN", 50

def momentum_score(ind):
    score = 50
    for r in (ind["return20"], ind["return60"]):
        if np.isnan(r):
            continue
        if r > .10:
            score += 20
        elif r > 0:
            score += 10
        elif r < -.10:
            score -= 20
        else:
            score -= 10
    return clamp(score)

def valuation_score(fund):
    score = 50
    pe, peg = fund["forward_pe"], fund["peg"]
    if not np.isnan(pe):
        if 0 < pe < 15:
            score += 30
        elif pe < 20:
            score += 20
        elif pe < 30:
            score += 5
        elif pe > 50:
            score -= 25
        elif pe > 35:
            score -= 15
    if not np.isnan(peg):
        if 0 < peg < 1:
            score += 20
        elif peg < 1.5:
            score += 10
        elif peg > 3:
            score -= 15
    return clamp(score)

def risk_score(ind):
    price, atr = ind["price"], ind["atr"]
    if np.isnan(atr) or price <= 0:
        return 50
    atr_pct = atr / price
    if atr_pct < .02:
        return 20
    if atr_pct < .04:
        return 40
    if atr_pct < .06:
        return 60
    if atr_pct < .10:
        return 80
    return 95

def calculate_master(technical, fundamental, momentum, valuation, macro, risk, regime):
    raw = (
        technical * .25 +
        fundamental * .25 +
        momentum * .15 +
        valuation * .10 +
        macro * .15 +
        (100 - risk) * .10
    )
    if regime == "RISK-OFF":
        raw -= 5
    master = clamp(raw)

    if master >= 70:
        bias = "đŸŸ¢ LONG"
    elif master <= 40:
        bias = "đŸ”´ SHORT"
    else:
        bias = "đŸŸ¡ NEUTRAL"
    return master, bias

def confidence_score(master, technical, fundamental, momentum, macro, risk, regime):
    components = [technical, fundamental, momentum, macro, 100 - risk]
    dispersion = np.std(components)
    confidence = 50 + abs(master - 50) * .55
    if dispersion < 15:
        confidence += 10
    elif dispersion > 30:
        confidence -= 10
    if regime == "RISK-OFF" and master >= 50:
        confidence -= 8
    return clamp(confidence, 35, 92)

def trade_setup(ind, bias):
    price, atr = ind["price"], ind["atr"]
    if np.isnan(atr):
        atr = price * .04

    if "LONG" in bias:
        entry_low = price - atr * .50
        entry_high = price + atr * .15
        stop = price - atr * 1.50
        risk = price - stop
        tp1 = price + risk * 1.50
        tp2 = price + risk * 2.00
    elif "SHORT" in bias:
        entry_low = price - atr * .15
        entry_high = price + atr * .50
        stop = price + atr * 1.50
        risk = stop - price
        tp1 = price - risk * 1.50
        tp2 = price - risk * 2.00
    else:
        entry_low = price - atr * .25
        entry_high = price + atr * .25
        stop = tp1 = tp2 = np.nan

    return entry_low, entry_high, stop, tp1, tp2

def backtest(hist):
    close = hist["Close"].astype(float)
    if len(close) < 220:
        return None

    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)

    macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    signal = macd.ewm(span=9, adjust=False).mean()

    long_sig = (close > ema20) & (ema20 > ema50) & (ema50 > ema200) & (macd > signal) & (rsi > 50)
    short_sig = (close < ema20) & (ema20 < ema50) & (ema50 < ema200) & (macd < signal) & (rsi < 50)

    future_return = close.shift(-5) / close - 1
    trades = []

    for i in range(len(close) - 5):
        if long_sig.iloc[i]:
            trades.append(future_return.iloc[i])
        elif short_sig.iloc[i]:
            trades.append(-future_return.iloc[i])

    trades = pd.Series(trades).dropna()
    if trades.empty:
        return None

    wins = trades[trades > 0]
    losses = trades[trades <= 0]
    gross_profit = wins.sum()
    gross_loss = abs(losses.sum())

    equity = (1 + trades).cumprod()
    drawdown = equity / equity.cummax() - 1

    return {
        "trades": len(trades),
        "win_rate": len(wins) / len(trades),
        "profit_factor": gross_profit / gross_loss if gross_loss > 0 else np.inf,
        "max_drawdown": abs(drawdown.min())
    }

st.title("đŸ“ AI MASTER STOCK BOT â€” MAX VIP FREE")
st.caption("Technical + Fundamental + Momentum + Valuation + Macro + Risk â€¢ KhĂ´ng tá»± Ä‘áº·t lá»‡nh â€¢ KhĂ´ng cáº§n API tráº£ phĂ­")

ticker = st.text_input("Nháº­p mĂ£ cá»• phiáº¿u", "MU").upper().strip()

if st.button("đŸ” PHĂ‚N TĂCH MAX VIP", use_container_width=True):
    if not ticker:
        st.warning("Nháº­p mĂ£ cá»• phiáº¿u trÆ°á»›c.")
        st.stop()

    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="2y", auto_adjust=False)

        if hist.empty or len(hist) < 100:
            st.error("KhĂ´ng Ä‘á»§ dá»¯ liá»‡u cho mĂ£ nĂ y.")
            st.stop()

        ind = calculate_indicators(hist)
        tech = technical_score(ind)
        fund = get_fundamentals(info)
        fundamental = fund["score"]
        momentum = momentum_score(ind)
        valuation = valuation_score(fund)
        regime, regime_score = market_regime()
        macro = regime_score
        risk = risk_score(ind)

        master, bias = calculate_master(
            tech, fundamental, momentum, valuation, macro, risk, regime
        )
        confidence = confidence_score(
            master, tech, fundamental, momentum, macro, risk, regime
        )

        entry_low, entry_high, stop, tp1, tp2 = trade_setup(ind, bias)

        st.subheader(f"{ticker} â€” {bias}")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("GiĂ¡", f"${ind['price']:.2f}")
        c2.metric("MAX SCORE", f"{master}/100")
        c3.metric("Confidence", f"{confidence}%")
        c4.metric("Market", regime)

        cols = st.columns(6)
        cols[0].metric("Technical", f"{tech}/100")
        cols[1].metric("Fundamental", f"{fundamental}/100")
        cols[2].metric("Momentum", f"{momentum}/100")
        cols[3].metric("Valuation", f"{valuation}/100")
        cols[4].metric("Macro", f"{macro}/100")
        cols[5].metric("Risk", f"{risk}/100")

        if regime == "RISK-OFF":
            st.warning("â ï¸ THá» TRÆ¯á»œNG ÄANG RISK-OFF â€” tĂ­n hiá»‡u LONG cáº§n tháº­n trá»ng.")
        if macro < 40:
            st.warning("â ï¸ Macro tháº¥p â€” bá»‘i cáº£nh thá»‹ trÆ°á»ng khĂ´ng thuáº­n lá»£i.")
        if risk >= 70:
            st.error("đŸ”´ Risk cao â€” biáº¿n Ä‘á»™ng lá»›n.")
        if confidence < 60:
            st.info("â„¹ï¸ Confidence chÆ°a cao â€” nĂªn chá» thĂªm xĂ¡c nháº­n.")

        st.subheader("đŸ¯ Trade Setup")
        t1, t2, t3, t4, t5 = st.columns(5)
        t1.metric("Entry zone", f"${entry_low:.2f} â€“ ${entry_high:.2f}")
        t2.metric("Stop Loss", fmt(stop))
        t3.metric("TP1", fmt(tp1))
        t4.metric("TP2", fmt(tp2))
        t5.metric("R/R", "1 : 1.5 / 2.0" if "NEUTRAL" not in bias else "N/A")

        st.subheader("đŸ“ˆ Technical")
        technical_df = pd.DataFrame([
            ["RSI", fmt(ind["rsi"])],
            ["MACD", fmt(ind["macd"])],
            ["EMA20", fmt(ind["ema20"])],
            ["EMA50", fmt(ind["ema50"])],
            ["EMA200", fmt(ind["ema200"])],
            ["ATR14", fmt(ind["atr"])],
            ["RVOL", fmt(ind["rvol"])],
            ["20D Return", pct(ind["return20"])],
            ["60D Return", pct(ind["return60"])],
        ], columns=["Metric", "Value"])
        st.dataframe(technical_df, use_container_width=True, hide_index=True)

        st.subheader("đŸŒ Market Regime")
        if regime == "RISK-ON":
            st.success(f"đŸŸ¢ RISK-ON â€” Market Score {regime_score}/100")
        elif regime == "RISK-OFF":
            st.error(f"đŸ”´ RISK-OFF â€” Market Score {regime_score}/100")
        else:
            st.info(f"đŸŸ¡ NEUTRAL â€” Market Score {regime_score}/100")

        st.subheader("đŸ‚ Bull Case")
        bull_points = []
        if ind["price"] > ind["ema20"]: bull_points.append("GiĂ¡ trĂªn EMA20")
        if ind["ema20"] > ind["ema50"]: bull_points.append("EMA20 > EMA50")
        if ind["ema50"] > ind["ema200"]: bull_points.append("EMA50 > EMA200")
        if ind["macd_bull"]: bull_points.append("MACD bullish")
        if 50 <= ind["rsi"] < 70: bull_points.append("RSI khá»e, chÆ°a quĂ¡ nĂ³ng")
        if fundamental >= 65: bull_points.append("Fundamental tá»‘t")
        if momentum >= 60: bull_points.append("Momentum tĂ­ch cá»±c")
        if not bull_points: bull_points.append("ChÆ°a cĂ³ nhiá»u yáº¿u tá»‘ há»— trá»£.")
        for x in bull_points: st.write(f"â€¢ {x}")

        st.subheader("đŸ» Bear / Risk Case")
        bear_points = []
        if regime == "RISK-OFF": bear_points.append("Thá»‹ trÆ°á»ng chung Ä‘ang RISK-OFF")
        if macro < 40: bear_points.append("Macro Score tháº¥p")
        if risk >= 70: bear_points.append("Biáº¿n Ä‘á»™ng cao")
        if not np.isnan(ind["return20"]) and ind["return20"] < 0: bear_points.append("20D Return Ă¢m")
        if not np.isnan(ind["return60"]) and ind["return60"] < 0: bear_points.append("60D Return Ă¢m")
        if momentum < 45: bear_points.append("Momentum yáº¿u")
        if not bear_points: bear_points.append("ChÆ°a phĂ¡t hiá»‡n rá»§i ro Ä‘á»‹nh lÆ°á»£ng lá»›n tá»« dá»¯ liá»‡u hiá»‡n cĂ³.")
        for x in bear_points: st.write(f"â€¢ {x}")

        st.subheader("đŸ’° Fundamental")
        fundamental_df = pd.DataFrame([
            ["Revenue growth", pct(fund["revenue_growth"])],
            ["EPS/Earnings growth", pct(fund["earnings_growth"])],
            ["ROE", pct(fund["roe"])],
            ["Net margin", pct(fund["profit_margin"])],
            ["Operating margin", pct(fund["operating_margin"])],
            ["Debt/Equity", fmt(fund["debt_equity"])],
            ["Current ratio", fmt(fund["current_ratio"])],
            ["Forward P/E", fmt(fund["forward_pe"])],
            ["Trailing P/E", fmt(fund["trailing_pe"])],
            ["PEG", fmt(fund["peg"])],
            ["Free cash flow", fmt(fund["free_cash_flow"])],
        ], columns=["Metric", "Value"])
        st.dataframe(fundamental_df, use_container_width=True, hide_index=True)

        st.subheader("đŸ§ª Backtest nhanh")
        result = backtest(hist)
        if result:
            b1, b2, b3, b4 = st.columns(4)
            b1.metric("Trades", result["trades"])
            b2.metric("Win rate", f"{result['win_rate'] * 100:.1f}%")
            b3.metric("Profit factor", fmt(result["profit_factor"]))
            b4.metric("Max drawdown", f"{result['max_drawdown'] * 100:.1f}%")
            st.caption("Backtest 5 ngĂ y, chÆ°a bao gá»“m phĂ­, spread, slippage vĂ  thuáº¿. Káº¿t quáº£ quĂ¡ khá»© khĂ´ng Ä‘áº£m báº£o lá»£i nhuáº­n tÆ°Æ¡ng lai.")
        else:
            st.info("KhĂ´ng Ä‘á»§ dá»¯ liá»‡u Ä‘á»ƒ cháº¡y backtest.")

        st.subheader("đŸ§  MAX VIP Verdict")
        if "LONG" in bias:
            if regime == "RISK-OFF" or macro < 40:
                st.warning(f"đŸŸ¢ LONG nhÆ°ng rá»§i ro cao â€” MAX {master}/100 â€¢ Confidence {confidence}%.")
            else:
                st.success(f"đŸŸ¢ LONG â€” MAX {master}/100 â€¢ Confidence {confidence}%.")
        elif "SHORT" in bias:
            st.error(f"đŸ”´ SHORT â€” MAX {master}/100 â€¢ Confidence {confidence}%.")
        else:
            st.info(f"đŸŸ¡ NEUTRAL â€” MAX {master}/100 â€¢ Confidence {confidence}%.")

        st.info("Bot chá»‰ phĂ¢n tĂ­ch dá»¯ liá»‡u. KhĂ´ng tá»± mua, bĂ¡n hoáº·c Ä‘áº·t lá»‡nh.")

    except Exception as e:
        st.error(f"Lá»—i khi phĂ¢n tĂ­ch {ticker}: {e}")
