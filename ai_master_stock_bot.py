
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="AI Master Stock Bot", page_icon="📊", layout="centered")

st.title("📊 AI MASTER STOCK BOT")
st.caption("Phân tích Fundamental + Technical • Không tự đặt lệnh")

ticker = st.text_input("Nhập mã cổ phiếu", "MU").upper().strip()

if st.button("🔍 PHÂN TÍCH", use_container_width=True):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="1y", auto_adjust=False)

        if hist.empty:
            st.error("Không lấy được dữ liệu cho mã này.")
            st.stop()

        price = float(hist["Close"].iloc[-1])

        # ---------------- TECHNICAL ----------------
        close = hist["Close"]
        ema20 = close.ewm(span=20, adjust=False).mean().iloc[-1]
        ema50 = close.ewm(span=50, adjust=False).mean().iloc[-1]
        ema200 = close.ewm(span=200, adjust=False).mean().iloc[-1]

        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = (100 - (100 / (1 + rs))).iloc[-1]

        macd_fast = close.ewm(span=12, adjust=False).mean()
        macd_slow = close.ewm(span=26, adjust=False).mean()
        macd = macd_fast - macd_slow
        signal = macd.ewm(span=9, adjust=False).mean()
        macd_bull = macd.iloc[-1] > signal.iloc[-1]

        tech_score = 50
        tech_score += 10 if price > ema20 else -10
        tech_score += 10 if ema20 > ema50 else -10
        tech_score += 10 if ema50 > ema200 else -10
        tech_score += 10 if macd_bull else -10
        tech_score += 10 if 50 < rsi < 70 else (-5 if rsi >= 70 else 0)
        tech_score = int(np.clip(tech_score, 0, 100))

        # ---------------- FUNDAMENTAL ----------------
        revenue_growth = info.get("revenueGrowth")
        earnings_growth = info.get("earningsGrowth")
        roe = info.get("returnOnEquity")
        profit_margin = info.get("profitMargins")
        operating_margin = info.get("operatingMargins")
        debt_equity = info.get("debtToEquity")
        current_ratio = info.get("currentRatio")
        forward_pe = info.get("forwardPE")
        trailing_pe = info.get("trailingPE")
        peg = info.get("pegRatio")
        free_cash_flow = info.get("freeCashflow")
        piotroski = info.get("piotroskiScore")

        fund_score = 50
        if revenue_growth is not None: fund_score += 10 if revenue_growth > 0.10 else (-5 if revenue_growth < 0 else 0)
        if earnings_growth is not None: fund_score += 10 if earnings_growth > 0.10 else (-5 if earnings_growth < 0 else 0)
        if roe is not None: fund_score += 10 if roe > 0.15 else 0
        if profit_margin is not None: fund_score += 5 if profit_margin > 0.10 else 0
        if free_cash_flow is not None: fund_score += 10 if free_cash_flow > 0 else -10
        if debt_equity is not None: fund_score += 5 if debt_equity < 100 else -5
        if current_ratio is not None: fund_score += 5 if current_ratio > 1.2 else 0
        if forward_pe is not None: fund_score += 5 if 0 < forward_pe < 25 else (-5 if forward_pe > 50 else 0)
        fund_score = int(np.clip(fund_score, 0, 100))

        master = int(round((fund_score + tech_score) / 2))

        if master >= 75:
            bias = "🟢 LONG"
        elif master <= 40:
            bias = "🔴 SHORT"
        else:
            bias = "🟡 NEUTRAL"

        valuation = "N/A"
        if forward_pe is not None:
            if forward_pe < 20:
                valuation = "🟢 CHEAP"
            elif forward_pe > 35:
                valuation = "🔴 EXPENSIVE"
            else:
                valuation = "🟡 FAIR"

        st.subheader(f"{ticker} — {bias}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Giá", f"{price:.2f}")
        c2.metric("Fundamental", f"{fund_score}/100")
        c3.metric("Technical", f"{tech_score}/100")

        st.metric("🔥 MASTER SCORE", f"{master}/100")
        st.write(f"**Valuation:** {valuation}")

        st.divider()
        st.subheader("📈 Technical")
        st.write(f"EMA20: {ema20:.2f}  |  EMA50: {ema50:.2f}  |  EMA200: {ema200:.2f}")
        st.write(f"RSI(14): {rsi:.1f}  |  MACD: {'BULLISH' if macd_bull else 'BEARISH'}")

        st.subheader("💰 Fundamental")
        rows = {
            "Revenue growth": revenue_growth,
            "EPS/Earnings growth": earnings_growth,
            "ROE": roe,
            "Net margin": profit_margin,
            "Operating margin": operating_margin,
            "Debt/Equity": debt_equity,
            "Current ratio": current_ratio,
            "Forward P/E": forward_pe,
            "Trailing P/E": trailing_pe,
            "PEG": peg,
            "Free cash flow": free_cash_flow,
            "Piotroski": piotroski,
        }
        df = pd.DataFrame(
            [(k, "N/A" if v is None else v) for k, v in rows.items()],
            columns=["Metric", "Value"]
        )
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.info("Bot chỉ phân tích. Không tự vào lệnh, không tự mua/bán.")

    except Exception as e:
        st.error(f"Lỗi: {e}")

st.caption("V1 • Có thể mở rộng thêm news, earnings, valuation, risk và Telegram.")
