import streamlit as st
nhập yfinance dưới dạng yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="AI MASTER STOCK BOT — MAX VIP FREE", page_icon="đŸ“Š", layout="wide")

# ===========================================================
# MAX VIP FREE V2 — chỉ cung cấp dữ liệu miễn phí, không có giao dịch qua môi giới/API
# ===========================================================

def sf(x, default=np.nan):
    thử:
        nếu x là None:
            trả về giá trị mặc định
        x = float(x)
        trả về giá trị mặc định nếu không phải np.isfinite(x) ngược lại là x
    ngoại trừ Ngoại lệ:
        trả về giá trị mặc định


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
    trả về 100 - 100 / (1 + rs)


def atr_series(hist, n=14):
    đóng = hist["Đóng"].astype(float)
    high = hist["High"].astype(float)
    low = hist["Low"].astype(float)
    tr = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()


def adx_series(hist, n=14):
    high = hist["High"].astype(float)
    low = hist["Low"].astype(float)
    đóng = hist["Đóng"].astype(float)
    lên = cao.diff()
    xuống = -low.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=hist.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=hist.index)
    tr = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/n, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1/n, adjustment=False).mean() / atr.replace(0, np.nan)
    trừ_di = 100 * trừ_dm.ewm(alpha=1/n, adjustment=False).mean() / atr.replace(0, np.nan)
    dx = 100 * (plus_di-minus_di).abs() / (plus_di+minus_di).replace(0, np.nan)
    trả về dx.ewm(alpha=1/n, adjustment=False).mean(), plus_di,trừ_di


def indicators(hist):
    đóng = hist["Đóng"].astype(float)
    thể tích = hist["Thể tích"].astype(float)
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()
    rsi = rsi_series(close)
    macd_fast = close.ewm(span=12, adjust=False).mean()
    macd_slow = close.ewm(span=26, adjust=False).mean()
    macd = macd_fast - macd_slow
    signal = macd.ewm(span=9, adjust=False).mean()
    atr = atr_series(hist)
    adx, plus_di,trừ_di = adx_series(hist)
    avg_vol = volume.rolling(20).mean()
    sma20_vol = avg_vol
    high20 = hist["High"].rolling(20).max()
    low20 = hist["Low"].rolling(20).min()
    giá = đóng.iloc[-1]

    # Độ dốc xu hướng được chuẩn hóa theo giá; hữu ích để tránh chỉ đưa ra kết quả 100/100 dựa trên thứ tự EMA.
    slope20 = (ema20.iloc[-1] - ema20.iloc[-6]) / price if len(close) > 6 else np.nan
    slope50 = (ema50.iloc[-1] - ema50.iloc[-11]) / price if len(close) > 11 else np.nan

    trở lại {
        "giá": giá cả,
        "ema20": ema20.iloc[-1], "ema50": ema50.iloc[-1], "ema200": ema200.iloc[-1],
        "rsi": rsi.iloc[-1], "macd": macd.iloc[-1], "signal": signal.iloc[-1],
        "macd_bull": macd.iloc[-1] > signal.iloc[-1],
        "atr": atr.iloc[-1], "atr_pct": atr.iloc[-1] / giá nếu giá khác np.nan,
        "rvol": volume.iloc[-1] / sma20_vol.iloc[-1] nếu sma20_vol.iloc[-1] ngược lại np.nan,
        "adx": adx.iloc[-1], "plus_di": plus_di.iloc[-1], "minus_di":trừ_di.iloc[-1],
        "slope20": slope20, "slope50": slope50,
        "return20": close.iloc[-1] / close.iloc[-21] - 1 nếu len(close) > 21 ngược lại np.nan,
        "return60": close.iloc[-1] / close.iloc[-61] - 1 if len(close) > 61 else np.nan,
        "range20_pos": (price-low20.iloc[-1])/(high20.iloc[-1]-low20.iloc[-1]) nếu high20.iloc[-1] > low20.iloc[-1] else .5,
    }


def technical_score(ind):
    # 8 tín hiệu tương đối độc lập, mỗi tín hiệu có sai số +/- 6 đến 10. Tránh được vấn đề tự động 100/100 cũ.
    s = 50
    s += 8 nếu ind["price"] > ind["ema20"] ngược lại -8
    s += 8 nếu ind["ema20"] > ind["ema50"] ngược lại là -8
    s += 8 nếu ind["ema50"] > ind["ema200"] ngược lại là -8
    s += 8 nếu ind["macd_bull"] ngược lại là -8
    rsi = ind["rsi"]
    nếu 52 <= rsi <= 68: s += 8
    elif 45 <= rsi < 52 or 68 < rsi <= 75: s += 3
    elif rsi < 30: s += 1
    ngược lại: s -= 6
    adx = ind["adx"]
    nếu adx >= 25: s += 8 if ind["plus_di"] > ind["minus_di"] else -8
    elif adx >= 18: s += 3 if ind["plus_di"] > ind["minus_di"] else -3
    nếu ind["slope20"] > 0: s += 5
    ngược lại: s -= 5
    nếu ind["rvol"] >= 1.2: s += 5 nếu ind["price"] > ind["ema20"] ngược lại -5
    kẹp hồi


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
    trả về v, kẹp(s)


def valuation_score(f):
    s = 50
    pe, peg = f["forward_pe"], f["peg"]
    nếu không phải np.isnan(pe) và pe > 0:
        nếu pe < 15: s ± 28
        elif pe < 20: s += 18
        elif pe < 30: s += 5
        elif pe > 50: s -= 25
        elif pe > 35: s -= 15
    nếu np.isnan(peg) không phải là np.isnan và peg > 0:
        nếu chốt < 1: s += 18
        elif peg < 1.5: s += 10
        elif peg > 3: s -= 15
    kẹp hồi


def market_regime():
    # Miễn phí: Thống nhất xu hướng SPY + QQQ + IWM.
    điểm số = []
    for sym in ["SPY", "QQQ", "IWM"]:
        thử:
            h = yf.Ticker(sym).history(period="1y", auto_adjust=False)
            nếu h.empty: tiếp tục
            c = h["Đóng"].astype(float)
            e50 = c.ewm(span=50, adjustment=False).mean().iloc[-1]
            e200 = c.ewm(span=200, adjustment=False).mean().iloc[-1]
            p = c.iloc[-1]
            x = 50 + (15 nếu p > e50, ngược lại là -15) + (20 nếu e50 > e200, ngược lại là -20) + (15 nếu p > e200, ngược lại là -15)
            scores.append(x)
        ngoại trừ Ngoại lệ:
            vượt qua
    Nếu không có điểm số: trả về "UNKNOWN", 50
    điểm số = kẹp(np.mean(điểm số))
    Nếu điểm số >= 65: trả về "RISK-ON", điểm số
    Nếu điểm số <= 35: trả về "RISK-OFF", điểm số
    trả về "TRUNG LẬP", điểm số


def momentum_score(ind):
    s = 50
    for r, strong in [(ind["return20"], .08), (ind["return60"], .15)]:
        nếu np.isnan(r): tiếp tục
        nếu r > mạnh: s += 18
        elif r > 0: s += 8
        elif r < -strong: s -= 18
        ngược lại: s -= 8
    nếu ind["slope20"] > 0: s += 6
    ngược lại: s -= 6
    kẹp hồi


def risk_score(ind):
    a = ind["atr_pct"]
    if np.isnan(a): return 50
    nếu a < 0.02: trả về 20
    nếu a < 0.04: trả về 35
    nếu a < 0.06: trả về 55
    nếu a < 0.08: trả về 70
    trả về 90


def master_score(tech, fund, mom, val, macro, risk, regime):
    # Yếu tố kỹ thuật/cơ bản có phần nặng hơn một chút, nhưng không có yếu tố nào chiếm ưu thế.
    raw = tech*.24 + fund*.24 + mom*.16 + val*.12 + macro*.14 + (100-risk)*.10
    if regime == "RISK-OFF": raw -= 7
    nếu regime == "RISK-ON": raw += 3
    master = clamp(raw)
    Nếu master >= 70: bias = "đŸŸ¢ LONG"
    elif master <= 40: bias = "đŸ”´ SHORT"
    ngược lại: bias = "đŸŸ¡ NEUTRAL"
    trả về máy chủ, độ lệch


def confidence(master, tech, fund, mom, val, macro, risk, regime):
    vals = np.array([tech, fund, mom, val, macro, 100-risk], dtype=float)
    độ phân tán = np.std(vals)
    thỏa thuận = 100 - min(100, độ phân tán * 1,7)
    hướng = abs(master - 50) * 1.0
    c = 42 + hướng*0.45 + thỏa thuận*0.22
    nếu regime == "RISK-OFF" và master > 55: c -= 8
    nếu regime == "RISK-ON" và master < 45: c -= 8
    kẹp trả về (c, 35, 94)


def setup(ind, bias):
    p, atr = ind["price"], ind["atr"]
    atr = atr nếu không np.isnan(atr) và atr > 0 thì p*.04
    nếu "LONG" trong bias:
        entry_low, entry_high = p-0.35*atr, p+0.10*atr
        dừng = p-1.50*atr
        rủi ro = p-dừng
        tp1, tp2 = p+1.50*risk, p+2.25*risk
    elif "SHORT" in bias:
        entry_low, entry_high = p-0.10*atr, p+0.35*atr
        dừng = p + 1,50 * atr
        rủi ro = dừng-p
        tp1, tp2 = p-1.50*risk, p-2.25*risk
    khác:
        entry_low, entry_high = p-0.20*atr, p+0.20*atr
        dừng = tp1 = tp2 = np.nan
    trả về entry_low, entry_high, stop, tp1, tp2


def backtest(hist, cost_bps=10, max_hold=10):
    # Kiểm thử ngược hàng ngày dựa trên sự kiện: tín hiệu khi đóng cửa -> vào lệnh khi mở cửa tiếp theo.
    # Điểm dừng/chốt lời dựa trên chỉ báo ATR. Nên thận trọng nếu cả hai điểm dừng đều được chạm trên cùng một nến: đặt điểm dừng trước.
    if len(hist) < 260: return None
    h = hist.copy()
    đóng = h["Đóng"].astype(float)
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
    adx, cộng, trừ = chuỗi adx(h)
    long_sig = (close > ema20) & (ema20 > ema50) & (ema50 > ema200) & (macd > signal) & (rsi > 52) & (plus > minus) & (adx > 18)
    short_sig = (close < ema20) & (ema20 < ema50) & (ema50 < ema200) & (macd < signal) & (rsi < 48) & (minus > plus) & (adx > 18)

    giao dịch = []
    i = 210
    trong khi i < len(h)-1:
        hướng = 1 nếu long_sig.iloc[i] else (-1 nếu short_sig.iloc[i] else 0)
        nếu hướng == 0 hoặc np.isnan(atr.iloc[i]):
            i ± 1; tiếp tục
        mục nhập_i = i + 1
        mục nhập = open_.iloc[entry_i] * (1 + cost_bps/10000 * hướng)
        a = atr.iloc[i]
        điểm dừng = điểm vào - hướng * 1,5*a
        mục tiêu = điểm vào + hướng * 2,25*a
        exit_price = close.iloc[min(entry_i+max_hold-1, len(h)-1)]
        exit_i = min(entry_i+max_hold-1, len(h)-1)
        lý do = "THỜI GIAN"
        for j in range(entry_i, exit_i+1):
            hit_stop = (low.iloc[j] <= stop) if direction == 1 else (high.iloc[j] >= stop)
            hit_target = (high.iloc[j] >= target) if direction == 1 else (low.iloc[j] <= target)
            nếu hit_stop và hit_target:
                exit_price, exit_i, reason = stop, j, "DỪNG LẠI (thận trọng)"
                phá vỡ
            nếu hit_stop:
                giá thoát, lối thoát i, lý do = dừng, j, "DỪNG"
                phá vỡ
            nếu trúng mục tiêu:
                giá thoát, thoát_i, lý do = mục tiêu, j, "TP"
                phá vỡ
        giá thoát *= (1 - chi phí mỗi điểm cơ sở/10000 * hướng)
        ret = direction * (exit_price/entry - 1)
        giao dịch.append(ret)
        i = exit_i + 1

    Nếu không có giao dịch: trả về None
    tr = pd.Series(trades, dtype=float)
    thắng = tr[tr > 0]
    tổn thất = tr[tr <= 0]
    eq = (1+tr).cumprod()
    dd = eq/eq.cummax()-1
    trở lại {
        "giao dịch": len(tr), "tỷ lệ thắng": float((tr>0).mean()),
        "hệ số lợi nhuận": float(tổng số trận thắng/tổng số trận thua) nếu len(số trận thua) ngược lại np.inf,
        "max_drawdown": float(abs(dd.min())), "total_return": float(eq.iloc[-1]-1),
        "avg_trade": float(tr.mean()),
    }


st.title("ĐŸ“Š AI MASTER STOCK BOT — MAX VIP FREE")
st.caption("Kỹ thuật + Cơ bản + Động lượng + Định giá + Vĩ mô + Rủi ro â€¢ V2 â€¢ Chá»‰ Chá»‰ phăn tách â€¢ Khăn tá»± Ä'áº·t lá»‡nh â€¢ Khôngng cá tráo API sau")

ticker = st.text_input("Nháúp mĂ£ cá»Ã phiáú¿u", "MU").upper().strip()

if st.button("đŸ”Ž PHĂ‚N TĂ CH MAX VIP", use_container_width=True):
    nếu không phải là mã chứng khoán:
        st.warning("Nháúp mĂ£ cá»Ã phiáº¿u trÆ°á»μc."); st.stop()
    thử:
        cổ phiếu = yf.Ticker(ticker)
        thông tin = cổ phiếu.info
        hist = stock.history(period="3y", auto_adjust=False)
        nếu hist.empty hoặc len(hist) < 260:
            st.error("Khăn Ä'á»§ dá»¯ liá»‡u lá»‹ch sá» cho mĂ£ nĂy."); st.stop()

        ind = indicators(hist)
        công nghệ = điểm kỹ thuật (ind)
        quỹ, cơ bản = cơ bản (thông tin)
        mẹ = điểm động lượng (ind)
        val = valuation_score(fund)
        chế độ, vĩ mô = chế độ thị trường()
        rủi ro = điểm rủi ro(ind)
        master, bias = master_score(tech, fundamental, mom, val, macro, risk, regime)
        conf = confidence(master, tech, fundamental, mom, val, macro, risk, regime)
        e1,e2,stop,tp1,tp2 = setup(ind,bias)

        st.subheader(f"{ticker} — {bias}")
        c = st.columns(4)
        c[0].metric("GiĂ¡", f"${ind['price']:.2f}")
        c[1].metric("MAX SCORE", f"{master}/100")
        c[2].metric("Confidence", f"{conf}%")
        c[3].metric("Market", regime)
        c = st.columns(6)
        for box, label, value in zip(c,["Technical","Fundamental","Momentum","Valuation","Macro","Risk"],[tech,fundamental,mom,val,macro,risk]):
            box.metric(label,f"{value}/100")

        if rủi ro >= 70: st.warning("âš ï¸ Rủi ro cao: ATR lá»***n, nĂn giá pá»‹ tháº¿ náº¿u giao dá»‹ch thá»±c tá¿.")
        if mode == "RISK-OFF": st.warning("âš ï¸ Thá»‹ trÆ°á» ng chung RISK-OFF â€” Æ°u tiĂn tĂn hiá»‡u că³ xăc nháon máù¡nh.")
        if conf < 60: st.info("âï¸ Tự tin chÆ°a cao – câ¡c nhăm măn hiá»‡u Ä'ang phĂn ká»³.")

        st.subheader("Thiết lập giao dịch")
        t=st.columns(5)
        t[0].metric("Vùng vào",f"${e1:.2f} – ${e2:.2f}")
        t[1].metric("Stop Loss",fmt(stop))
        t[2].metric("TP1",fmt(tp1))
        t[3].metric("TP2",fmt(tp2))
        t[4].metric("R/R","1 : 1.5 / 2.25" nếu "NEUTRAL" không thiên vị ngược lại "N/A")

        st.subheader("đŸ“ˆ Kỹ thuật")
        tech_df=pd.DataFrame([
            ["RSI",fmt(ind['rsi'])],["MACD",fmt(ind['macd'])],["EMA20",fmt(ind['ema20'])],["EMA50",fmt(ind['ema50'])],["EMA200",fmt(ind['ema200'])],
            ["ATR14",fmt(ind['atr'])],["ATR %",pct(ind['atr_pct'])],["ADX",fmt(ind['adx'])],["+DI",fmt(ind['plus_di'])],["-DI",fmt(ind['minus_di'])],
            ["RVOL",fmt(ind['rvol'])],["20D Return",pct(ind['return20'])],["60D Return",pct(ind['return60'])],["20D Range Position",pct(ind['range20_pos'])]
        ],columns=["Metric","Value"])
        st.dataframe(tech_df,use_container_width=True,hide_index=True)

        st.subheader("Chế độ thị trường")
        msg=f"Điểm thị trường {macro}/100"
        if regime=="RISK-ON": st.success(f"đŸŸ¢ RISK-ON — {msg}")
        elif regime=="RISK-OFF": st.error(f"đŸ”´ RISK-OFF — {msg}")
        else: st.info(f"đŸŸ¡ NEUTRAL — {msg}")

        st.subheader("đŸ ‚ Bull Case")
        bò đực=[]
        if ind['price']>ind['ema20']: bulls.append("Giăn trĂn EMA20")
        if ind['ema20']>ind['ema50']: bulls.append("EMA20 > EMA50")
        if ind['ema50']>ind['ema200']: bulls.append("EMA50 > EMA200")
        if ind['macd_bull']: bulls.append("MACD tăng giá")
        if 52<=ind['rsi']<=68: bulls.append("RSI khá» e, chÆ°a quăn")
        if ind['adx']>=25 and ind['plus_di']>ind['minus_di']: bulls.append("ADX xÃ¡c nhán xu hÆ°á>>>ng tÄƒng")
        if fundamental>=65: bulls.append("Fundamental tá»'t")
        if mom>=60: bulls.append("Momentum tĂch cá»±c")
        if not bulls: bulls=["ChÆ°a cĂ³ nhiá» u yáú¿u tá»' há»— trá»£."]
        for x in bulls: st.write(f"• {x}")

        st.subheader("đŸ » Trường hợp rủi ro / Gấu")
        gấu=[]
        if mode=="RISK-OFF": Bears.append("Thá»‹ trÆ°á» ng chung Ä'ang RISK-OFF")
        if Risk>=70: Bears.append("Biáº¿n Ä'á»™ng cao")
        if ind['return20']<0: bears.append("20D Return Ă¢m")
        if ind['return60']<0: bears.append("60D Return Ă¢m")
        if mom<45: bears.append("Momentum yáº¿u")
        if ind['adx']<18: Bears.append("Xu hÆ°á>>ng chÆ°a Ä'á»§ máº¡nh")
        if not Bear: Bears=["ChÆ°a phât hiá»‡n rá»§i ro Ä'á»‹nh lÆ°á»£ng lá»***n tá» « dá»¯ liá»‡u hiá»‡n cĂ³."]
        for x in bears: st.write(f"• {x}")

        st.subheader("ĐŸ'° Cơ bản")
        fdf=pd.DataFrame([
            ["Tăng trưởng doanh thu",pct(fund['revenue_growth'])],["Tăng trưởng EPS/Lợi nhuận",pct(fund['earnings_growth'])],["ROE",pct(fund['roe'])],
            ["Lợi nhuận ròng",pct(fund['profit_margin'])],["Lợi nhuận hoạt động",pct(fund['operating_margin'])],["Tỷ lệ nợ/vốn chủ sở hữu",fmt(fund['debt_equity'])],
            ["Tỷ lệ hiện tại",fmt(fund['current_ratio'])],["P/E dự phóng",fmt(fund['forward_pe'])],["P/E quá khứ",fmt(fund['trailing_pe'])],
            ["PEG",fmt(fund['peg'])],["Dòng tiền tự do",fmt(fund['free_cash_flow'])]
        ],columns=["Metric","Value"])
        st.dataframe(fdf,use_container_width=True,hide_index=True)

        st.subheader("đŸ§ª Backtest MAX V2")
        bt=backtest(hist)
        nếu bt:
            b=st.columns(5)
            b[0].metric("Giao dịch",bt['giao dịch']); b[1].metric("Tỷ lệ thắng",f"{bt['tỷ lệ thắng']*100:.1f}%"); b[2].metric("Hệ số lợi nhuận",fmt(bt['hệ số lợi nhuận'])); b[3].metric("Mức giảm tối đa",f"{bt['mức giảm tối đa']*100:.1f}%"); b[4].metric("Tổng lợi nhuận",f"{bt['tổng lợi nhuận']*100:.1f}%")
            st.caption("Backtest V2: vĂo lá»‡nh á»Ÿ Open phiĂn káú¿ tiáº¿p, cĂ³ ATR Stop/TP, tá»'i Ä'a 10 phián giá»¯ lá»‡nh vó chi phĂn giá£ Ä'á»‹nh 0,10%/lÆ°á»£t. Khong bao gá»“m thuáù¿/phí vay vĂng Ä'áº£m báº£o lá»£i nhuáùn tÆ°Æ¡ng lai.")
        else: st.info("Khăn Ä'á»§ tĂn hiá»‡u Ä'á»ƒ cháº¡y backtest.")

        st.subheader("ĐŸ§ MAX VIP Verdict")
        nếu "LONG" trong bias:
            if mode=="RỦI RO" hoặc rủi ro>=70: st.warning(f"đŸŸ¢ LONG nhÆ°ng câu cá tháºn tráo ng â€” MAX {master}/100 â€¢ Confidence {conf}%.")
            ngược lại: st.success(f"đŸŸ¢ LONG • MAX {master}/100 • Confidence {conf}%.")
        elif "SHORT" in bias: st.error(f"đŸ”´ SHORT • MAX {master}/100 • Confidence {conf}%.")
        else: st.info(f"đŸŸ¡ NEUTRAL — MAX {master}/100 • Confidence {conf}%.")
        st.info("Bot chá»‰ phăntách dá»¯ liá»‡u. Khănng tá»± mua, bănn hoáº·c Ä'áº·t lá»‡nh.")
    ngoại trừ Ngoại lệ là e:
        st.error(f"Lá»—i khi phăn dạy {ticker}: {e}")
