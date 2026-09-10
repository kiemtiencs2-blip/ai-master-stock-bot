import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="AI MASTER STOCK BOT â€” MAX VIP FREE", page_icon="đŸ“", layout="wide")

# ============================================================
# MAX VIP FREE V2 â€” free data only, no broker/API trading
# ============================================================

def sf(x, default=np.nan):
    try:
        if x is None:
            return default
        x = float(x)
        return default if not np.isfinite(x) else x
    except Exception:
        return default


def fmt(x, d=2):
    x = sf(x)
    return "N/A" if np.isnan(x) else f"{x:.{d}f}"


def pct(x):
    x = sf(x)
    return "N/A" if np.isnan(x) else f"{x * 100:.1f}%"


def clamp(x, lo=0, hi=100):
    return int(np.clip(round(sf(x, 50)), lo, hi))


def rsi_series(close, n=14):
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def atr_series(hist, n=14):
    close = hist["Close"].astype(float)
    high = hist["High"].astype(float)
    low = hist["Low"].astype(float)
    tr = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()


def adx_series(hist, n=14):
    high = hist["High"].astype(float)
    low = hist["Low"].astype(float)
    close = hist["Close"].astype(float)
    up = high.diff()
    down = -low.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=hist.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=hist.index)
    tr = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/n, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1/n, adjust=False).mean() / atr.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1/n, adjust=False).mean() / atr.replace(0, np.nan)
    dx = 100 * (plus_di-minus_di).abs() / (plus_di+minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1/n, adjust=False).mean(), plus_di, minus_di


def indicators(hist):
    close = hist["Close"].astype(float)
    volume = hist["Volume"].astype(float)
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()
    rsi = rsi_series(close)
    macd_fast = close.ewm(span=12, adjust=False).mean()
    macd_slow = close.ewm(span=26, adjust=False).mean()
    macd = macd_fast - macd_slow
    signal = macd.ewm(span=9, adjust=False).mean()
    atr = atr_series(hist)
    adx, plus_di, minus_di = adx_series(hist)
    avg_vol = volume.rolling(20).mean()
    sma20_vol = avg_vol
    high20 = hist["High"].rolling(20).max()
    low20 = hist["Low"].rolling(20).min()
    price = close.iloc[-1]

    # Trend slope normalized by price; useful to avoid giving 100/100 only from EMA ordering.
    slope20 = (ema20.iloc[-1] - ema20.iloc[-6]) / price if len(close) > 6 else np.nan
    slope50 = (ema50.iloc[-1] - ema50.iloc[-11]) / price if len(close) > 11 else np.nan

    return {
        "price": price,
        "ema20": ema20.iloc[-1], "ema50": ema50.iloc[-1], "ema200": ema200.iloc[-1],
        "rsi": rsi.iloc[-1], "macd": macd.iloc[-1], "signal": signal.iloc[-1],
        "macd_bull": macd.iloc[-1] > signal.iloc[-1],
        "atr": atr.iloc[-1], "atr_pct": atr.iloc[-1] / price if price else np.nan,
        "rvol": volume.iloc[-1] / sma20_vol.iloc[-1] if sma20_vol.iloc[-1] else np.nan,
        "adx": adx.iloc[-1], "plus_di": plus_di.iloc[-1], "minus_di": minus_di.iloc[-1],
        "slope20": slope20, "slope50": slope50,
        "return20": close.iloc[-1] / close.iloc[-21] - 1 if len(close) > 21 else np.nan,
        "return60": close.iloc[-1] / close.iloc[-61] - 1 if len(close) > 61 else np.nan,
        "range20_pos": (price-low20.iloc[-1])/(high20.iloc[-1]-low20.iloc[-1]) if high20.iloc[-1] > low20.iloc[-1] else .5,
    }


def technical_score(ind):
    # 8 independent-ish signals, each +/- 6 to 10. Avoids the old automatic 100/100 problem.
    s = 50
    s += 8 if ind["price"] > ind["ema20"] else -8
    s += 8 if ind["ema20"] > ind["ema50"] else -8
    s += 8 if ind["ema50"] > ind["ema200"] else -8
    s += 8 if ind["macd_bull"] else -8
    rsi = ind["rsi"]
    if 52 <= rsi <= 68: s += 8
    elif 45 <= rsi < 52 or 68 < rsi <= 75: s += 3
    elif rsi < 30: s += 1
    else: s -= 6
    adx = ind["adx"]
    if adx >= 25: s += 8 if ind["plus_di"] > ind["minus_di"] else -8
    elif adx >= 18: s += 3 if ind["plus_di"] > ind["minus_di"] else -3
    if ind["slope20"] > 0: s += 5
    else: s -= 5
    if ind["rvol"] >= 1.2: s += 5 if ind["price"] > ind["ema20"] else -5
    return clamp(s)


def fundamentals(info):
    v = {
        "revenue_growth": sf(info.get("revenueGrowth")),
        "earnings_growth": sf(info.get("earningsGrowth")),
        "roe": sf(info.get("returnOnEquity")),
        "profit_margin": sf(info.get("profitMargins")),
        "operating_margin": sf(info.get("operatingMargins")),
        "debt_equity": sf(info.get("debtToEquity")),
        "current_ratio": sf(info.get("currentRatio")),
        "forward_pe": sf(info.get("forwardPE")),
        "trailing_pe": sf(info.get("trailingPE")),
        "peg": sf(info.get("pegRatio")),
        "free_cash_flow": sf(info.get("freeCashflow")),
    }
    s = 50
    if not np.isnan(v["revenue_growth"]): s += 10 if v["revenue_growth"] > .10 else (4 if v["revenue_growth"] > 0 else -8)
    if not np.isnan(v["earnings_growth"]): s += 10 if v["earnings_growth"] > .10 else (4 if v["earnings_growth"] > 0 else -8)
    if not np.isnan(v["roe"]): s += 8 if v["roe"] > .15 else (3 if v["roe"] > 0 else -5)
    if not np.isnan(v["profit_margin"]): s += 5 if v["profit_margin"] > .10 else (2 if v["profit_margin"] > 0 else -5)
    if not np.isnan(v["operating_margin"]): s += 5 if v["operating_margin"] > .10 else (2 if v["operating_margin"] > 0 else -5)
    if not np.isnan(v["free_cash_flow"]): s += 8 if v["free_cash_flow"] > 0 else -8
    if not np.isnan(v["debt_equity"]): s += 5 if v["debt_equity"] < 100 else -7
    if not np.isnan(v["current_ratio"]): s += 5 if v["current_ratio"] > 1.2 else (-4 if v["current_ratio"] < 1 else 0)
    return v, clamp(s)


def valuation_score(f):
    s = 50
    pe, peg = f["forward_pe"], f["peg"]
    if not np.isnan(pe) and pe > 0:
        if pe < 15: s += 28
        elif pe < 20: s += 18
        elif pe < 30: s += 5
        elif pe > 50: s -= 25
        elif pe > 35: s -= 15
    if not np.isnan(peg) and peg > 0:
        if peg < 1: s += 18
        elif peg < 1.5: s += 10
        elif peg > 3: s -= 15
    return clamp(s)


def market_regime():
    # Free: SPY + QQQ + IWM trend agreement.
    scores = []
    for sym in ["SPY", "QQQ", "IWM"]:
        try:
            h = yf.Ticker(sym).history(period="1y", auto_adjust=False)
            if h.empty: continue
            c = h["Close"].astype(float)
            e50 = c.ewm(span=50, adjust=False).mean().iloc[-1]
            e200 = c.ewm(span=200, adjust=False).mean().iloc[-1]
            p = c.iloc[-1]
            x = 50 + (15 if p > e50 else -15) + (20 if e50 > e200 else -20) + (15 if p > e200 else -15)
            scores.append(x)
        except Exception:
            pass
    if not scores: return "UNKNOWN", 50
    score = clamp(np.mean(scores))
    if score >= 65: return "RISK-ON", score
    if score <= 35: return "RISK-OFF", score
    return "NEUTRAL", score


def momentum_score(ind):
    s = 50
    for r, strong in [(ind["return20"], .08), (ind["return60"], .15)]:
        if np.isnan(r): continue
        if r > strong: s += 18
        elif r > 0: s += 8
        elif r < -strong: s -= 18
        else: s -= 8
    if ind["slope20"] > 0: s += 6
    else: s -= 6
    return clamp(s)


def risk_score(ind):
    a = ind["atr_pct"]
    if np.isnan(a): return 50
    if a < .02: return 20
    if a < .04: return 35
    if a < .06: return 55
    if a < .08: return 70
    return 90


def master_score(tech, fund, mom, val, macro, risk, regime):
    # Slightly heavier technical/fundamental, but no single component dominates.
    raw = tech*.24 + fund*.24 + mom*.16 + val*.12 + macro*.14 + (100-risk)*.10
    if regime == "RISK-OFF": raw -= 7
    if regime == "RISK-ON": raw += 3
    master = clamp(raw)
    if master >= 70: bias = "đŸŸ¢ LONG"
    elif master <= 40: bias = "đŸ”´ SHORT"
    else: bias = "đŸŸ¡ NEUTRAL"
    return master, bias


def confidence(master, tech, fund, mom, val, macro, risk, regime):
    vals = np.array([tech, fund, mom, val, macro, 100-risk], dtype=float)
    dispersion = np.std(vals)
    agreement = 100 - min(100, dispersion * 1.7)
    directional = abs(master - 50) * 1.0
    c = 42 + directional*.45 + agreement*.22
    if regime == "RISK-OFF" and master > 55: c -= 8
    if regime == "RISK-ON" and master < 45: c -= 8
    return clamp(c, 35, 94)


def setup(ind, bias):
    p, atr = ind["price"], ind["atr"]
    atr = atr if not np.isnan(atr) and atr > 0 else p*.04
    if "LONG" in bias:
        entry_low, entry_high = p-0.35*atr, p+0.10*atr
        stop = p-1.50*atr
        risk = p-stop
        tp1, tp2 = p+1.50*risk, p+2.25*risk
    elif "SHORT" in bias:
        entry_low, entry_high = p-0.10*atr, p+0.35*atr
        stop = p+1.50*atr
        risk = stop-p
        tp1, tp2 = p-1.50*risk, p-2.25*risk
    else:
        entry_low, entry_high = p-0.20*atr, p+0.20*atr
        stop = tp1 = tp2 = np.nan
    return entry_low, entry_high, stop, tp1, tp2


def backtest(hist, cost_bps=10, max_hold=10):
    # Event-driven daily backtest: signal at close -> entry next open.
    # Stop/TP are ATR based. Conservative if both are touched on same candle: stop first.
    if len(hist) < 260: return None
    h = hist.copy()
    close = h["Close"].astype(float)
    open_ = h["Open"].astype(float)
    high = h["High"].astype(float)
    low = h["Low"].astype(float)
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()
    rsi = rsi_series(close)
    macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    signal = macd.ewm(span=9, adjust=False).mean()
    atr = atr_series(h)
    adx, plus, minus = adx_series(h)
    long_sig = (close > ema20) & (ema20 > ema50) & (ema50 > ema200) & (macd > signal) & (rsi > 52) & (plus > minus) & (adx > 18)
    short_sig = (close < ema20) & (ema20 < ema50) & (ema50 < ema200) & (macd < signal) & (rsi < 48) & (minus > plus) & (adx > 18)

    trades = []
    i = 210
    while i < len(h)-1:
        direction = 1 if long_sig.iloc[i] else (-1 if short_sig.iloc[i] else 0)
        if direction == 0 or np.isnan(atr.iloc[i]):
            i += 1; continue
        entry_i = i + 1
        entry = open_.iloc[entry_i] * (1 + cost_bps/10000 * direction)
        a = atr.iloc[i]
        stop = entry - direction * 1.5*a
        target = entry + direction * 2.25*a
        exit_price = close.iloc[min(entry_i+max_hold-1, len(h)-1)]
        exit_i = min(entry_i+max_hold-1, len(h)-1)
        reason = "TIME"
        for j in range(entry_i, exit_i+1):
            hit_stop = (low.iloc[j] <= stop) if direction == 1 else (high.iloc[j] >= stop)
            hit_target = (high.iloc[j] >= target) if direction == 1 else (low.iloc[j] <= target)
            if hit_stop and hit_target:
                exit_price, exit_i, reason = stop, j, "STOP (conservative)"
                break
            if hit_stop:
                exit_price, exit_i, reason = stop, j, "STOP"
                break
            if hit_target:
                exit_price, exit_i, reason = target, j, "TP"
                break
        exit_price *= (1 - cost_bps/10000 * direction)
        ret = direction * (exit_price/entry - 1)
        trades.append(ret)
        i = exit_i + 1

    if not trades: return None
    tr = pd.Series(trades, dtype=float)
    wins = tr[tr > 0]
    losses = tr[tr <= 0]
    eq = (1+tr).cumprod()
    dd = eq/eq.cummax()-1
    return {
        "trades": len(tr), "win_rate": float((tr>0).mean()),
        "profit_factor": float(wins.sum()/abs(losses.sum())) if len(losses) else np.inf,
        "max_drawdown": float(abs(dd.min())), "total_return": float(eq.iloc[-1]-1),
        "avg_trade": float(tr.mean()),
    }


st.title("đŸ“ AI MASTER STOCK BOT â€” MAX VIP FREE")
st.caption("Technical + Fundamental + Momentum + Valuation + Macro + Risk â€¢ V2 â€¢ Chá»‰ phĂ¢n tĂ­ch â€¢ KhĂ´ng tá»± Ä‘áº·t lá»‡nh â€¢ KhĂ´ng cáº§n API tráº£ phĂ­")

ticker = st.text_input("Nháº­p mĂ£ cá»• phiáº¿u", "MU").upper().strip()

if st.button("đŸ” PHĂ‚N TĂCH MAX VIP", use_container_width=True):
    if not ticker:
        st.warning("Nháº­p mĂ£ cá»• phiáº¿u trÆ°á»›c."); st.stop()
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="3y", auto_adjust=False)
        if hist.empty or len(hist) < 260:
            st.error("KhĂ´ng Ä‘á»§ dá»¯ liá»‡u lá»‹ch sá»­ cho mĂ£ nĂ y."); st.stop()

        ind = indicators(hist)
        tech = technical_score(ind)
        fund, fundamental = fundamentals(info)
        mom = momentum_score(ind)
        val = valuation_score(fund)
        regime, macro = market_regime()
        risk = risk_score(ind)
        master, bias = master_score(tech, fundamental, mom, val, macro, risk, regime)
        conf = confidence(master, tech, fundamental, mom, val, macro, risk, regime)
        e1,e2,stop,tp1,tp2 = setup(ind,bias)

        st.subheader(f"{ticker} â€” {bias}")
        c = st.columns(4)
        c[0].metric("GiĂ¡", f"${ind['price']:.2f}")
        c[1].metric("MAX SCORE", f"{master}/100")
        c[2].metric("Confidence", f"{conf}%")
        c[3].metric("Market", regime)
        c = st.columns(6)
        for box, label, value in zip(c,["Technical","Fundamental","Momentum","Valuation","Macro","Risk"],[tech,fundamental,mom,val,macro,risk]):
            box.metric(label,f"{value}/100")

        if risk >= 70: st.warning("â ï¸ Risk cao: ATR lá»›n, nĂªn giáº£m vá»‹ tháº¿ náº¿u giao dá»‹ch thá»±c táº¿.")
        if regime == "RISK-OFF": st.warning("â ï¸ Thá»‹ trÆ°á»ng chung RISK-OFF â€” Æ°u tiĂªn tĂ­n hiá»‡u cĂ³ xĂ¡c nháº­n máº¡nh.")
        if conf < 60: st.info("â„¹ï¸ Confidence chÆ°a cao â€” cĂ¡c nhĂ³m tĂ­n hiá»‡u Ä‘ang phĂ¢n ká»³.")

        st.subheader("đŸ¯ Trade Setup")
        t=st.columns(5)
        t[0].metric("Entry zone",f"${e1:.2f} â€“ ${e2:.2f}")
        t[1].metric("Stop Loss",fmt(stop))
        t[2].metric("TP1",fmt(tp1))
        t[3].metric("TP2",fmt(tp2))
        t[4].metric("R/R","1 : 1.5 / 2.25" if "NEUTRAL" not in bias else "N/A")

        st.subheader("đŸ“ˆ Technical")
        tech_df=pd.DataFrame([
            ["RSI",fmt(ind['rsi'])],["MACD",fmt(ind['macd'])],["EMA20",fmt(ind['ema20'])],["EMA50",fmt(ind['ema50'])],["EMA200",fmt(ind['ema200'])],
            ["ATR14",fmt(ind['atr'])],["ATR %",pct(ind['atr_pct'])],["ADX",fmt(ind['adx'])],["+DI",fmt(ind['plus_di'])],["-DI",fmt(ind['minus_di'])],
            ["RVOL",fmt(ind['rvol'])],["20D Return",pct(ind['return20'])],["60D Return",pct(ind['return60'])],["20D Range Position",pct(ind['range20_pos'])]
        ],columns=["Metric","Value"])
        st.dataframe(tech_df,use_container_width=True,hide_index=True)

        st.subheader("đŸŒ Market Regime")
        msg=f"Market Score {macro}/100"
        if regime=="RISK-ON": st.success(f"đŸŸ¢ RISK-ON â€” {msg}")
        elif regime=="RISK-OFF": st.error(f"đŸ”´ RISK-OFF â€” {msg}")
        else: st.info(f"đŸŸ¡ NEUTRAL â€” {msg}")

        st.subheader("đŸ‚ Bull Case")
        bulls=[]
        if ind['price']>ind['ema20']: bulls.append("GiĂ¡ trĂªn EMA20")
        if ind['ema20']>ind['ema50']: bulls.append("EMA20 > EMA50")
        if ind['ema50']>ind['ema200']: bulls.append("EMA50 > EMA200")
        if ind['macd_bull']: bulls.append("MACD bullish")
        if 52<=ind['rsi']<=68: bulls.append("RSI khá»e, chÆ°a quĂ¡ nĂ³ng")
        if ind['adx']>=25 and ind['plus_di']>ind['minus_di']: bulls.append("ADX xĂ¡c nháº­n xu hÆ°á»›ng tÄƒng")
        if fundamental>=65: bulls.append("Fundamental tá»‘t")
        if mom>=60: bulls.append("Momentum tĂ­ch cá»±c")
        if not bulls: bulls=["ChÆ°a cĂ³ nhiá»u yáº¿u tá»‘ há»— trá»£."]
        for x in bulls: st.write(f"â€¢ {x}")

        st.subheader("đŸ» Bear / Risk Case")
        bears=[]
        if regime=="RISK-OFF": bears.append("Thá»‹ trÆ°á»ng chung Ä‘ang RISK-OFF")
        if risk>=70: bears.append("Biáº¿n Ä‘á»™ng cao")
        if ind['return20']<0: bears.append("20D Return Ă¢m")
        if ind['return60']<0: bears.append("60D Return Ă¢m")
        if mom<45: bears.append("Momentum yáº¿u")
        if ind['adx']<18: bears.append("Xu hÆ°á»›ng chÆ°a Ä‘á»§ máº¡nh")
        if not bears: bears=["ChÆ°a phĂ¡t hiá»‡n rá»§i ro Ä‘á»‹nh lÆ°á»£ng lá»›n tá»« dá»¯ liá»‡u hiá»‡n cĂ³."]
        for x in bears: st.write(f"â€¢ {x}")

        st.subheader("đŸ’° Fundamental")
        fdf=pd.DataFrame([
            ["Revenue growth",pct(fund['revenue_growth'])],["EPS/Earnings growth",pct(fund['earnings_growth'])],["ROE",pct(fund['roe'])],
            ["Net margin",pct(fund['profit_margin'])],["Operating margin",pct(fund['operating_margin'])],["Debt/Equity",fmt(fund['debt_equity'])],
            ["Current ratio",fmt(fund['current_ratio'])],["Forward P/E",fmt(fund['forward_pe'])],["Trailing P/E",fmt(fund['trailing_pe'])],
            ["PEG",fmt(fund['peg'])],["Free cash flow",fmt(fund['free_cash_flow'])]
        ],columns=["Metric","Value"])
        st.dataframe(fdf,use_container_width=True,hide_index=True)

        st.subheader("đŸ§ª Backtest MAX V2")
        bt=backtest(hist)
        if bt:
            b=st.columns(5)
            b[0].metric("Trades",bt['trades']); b[1].metric("Win rate",f"{bt['win_rate']*100:.1f}%"); b[2].metric("Profit factor",fmt(bt['profit_factor'])); b[3].metric("Max drawdown",f"{bt['max_drawdown']*100:.1f}%"); b[4].metric("Total return",f"{bt['total_return']*100:.1f}%")
            st.caption("Backtest V2: vĂ o lá»‡nh á»Ÿ Open phiĂªn káº¿ tiáº¿p, cĂ³ ATR Stop/TP, tá»‘i Ä‘a 10 phiĂªn giá»¯ lá»‡nh vĂ  chi phĂ­ giáº£ Ä‘á»‹nh 0,10%/lÆ°á»£t. KhĂ´ng bao gá»“m thuáº¿/borrow fee vĂ  khĂ´ng Ä‘áº£m báº£o lá»£i nhuáº­n tÆ°Æ¡ng lai.")
        else: st.info("KhĂ´ng Ä‘á»§ tĂ­n hiá»‡u Ä‘á»ƒ cháº¡y backtest.")

        st.subheader("đŸ§  MAX VIP Verdict")
        if "LONG" in bias:
            if regime=="RISK-OFF" or risk>=70: st.warning(f"đŸŸ¢ LONG nhÆ°ng cáº§n tháº­n trá»ng â€” MAX {master}/100 â€¢ Confidence {conf}%.")
            else: st.success(f"đŸŸ¢ LONG â€” MAX {master}/100 â€¢ Confidence {conf}%.")
        elif "SHORT" in bias: st.error(f"đŸ”´ SHORT â€” MAX {master}/100 â€¢ Confidence {conf}%.")
        else: st.info(f"đŸŸ¡ NEUTRAL â€” MAX {master}/100 â€¢ Confidence {conf}%.")
        st.info("Bot chá»‰ phĂ¢n tĂ­ch dá»¯ liá»‡u. KhĂ´ng tá»± mua, bĂ¡n hoáº·c Ä‘áº·t lá»‡nh.")
    except Exception as e:
        st.error(f"Lá»—i khi phĂ¢n tĂ­ch {ticker}: {e}")
