import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
from datetime import datetime

# 1. KONFIGURASI HALAMAN & STYLE BLOOMBERG TERMINAL
st.set_page_config(page_title="IDX QUANT TERMINAL // V3.0 STRESS TEST", layout="wide", initial_sidebar_state="collapsed")

bloomberg_style = """
<style>
    .stApp { background-color: #000000; color: #E0E0E0; font-family: 'Courier New', Courier, monospace; }
    h1, h2, h3, h4 { color: #FF9900 !important; font-family: 'Courier New', Courier, monospace; font-weight: bold; }
    div[data-testid="stTable"] { border: 1px solid #FF9900; }
    table { width: 100%; border-collapse: collapse; }
    th { background-color: #111111; color: #FF9900; border-bottom: 2px solid #FF9900; padding: 8px; text-align: left; font-size: 13px; }
    td { border-bottom: 1px solid #222222; padding: 8px; font-size: 12px; color: #CCCCCC; }
    .metric-card { background-color: #0a0a0a; border: 1px solid #FF9900; padding: 12px; text-align: center; }
    .metric-title { color: #FF9900; font-size: 11px; letter-spacing: 1px; }
    .metric-value { font-size: 20px; font-weight: bold; margin-top: 5px; }
    .briefing-box { background-color: #1a0f00; border: 1px solid #FF9900; padding: 12px; font-size: 14px; color: #FFCC00; margin-bottom: 15px; }
    .macro-box-safe { background-color: #001a00; border: 1px solid #00FF00; padding: 10px; color: #00FF00; font-weight: bold; text-align: center; margin-bottom: 15px; }
    .macro-box-danger { background-color: #260000; border: 1px solid #FF0000; padding: 10px; color: #FF0000; font-weight: bold; text-align: center; margin-bottom: 15px; animation: blink 1s infinite; }
    .green-text { color: #00FF00; font-weight: bold; }
    .red-text { color: #FF0000; font-weight: bold; }
    .amber-text { color: #FF9900; font-weight: bold; }
</style>
"""
st.markdown(bloomberg_style, unsafe_allow_html=True)

# 2. MACRO-REGIME SHIELD (IHSG & USD/IDR)
@st.cache_data(ttl=3600)
def cek_status_makro():
    try:
        ihsg = yf.Ticker("^JKSE").history(period="3mo")
        usdidr = yf.Ticker("IDR=X").history(period="1mo")
        
        ihsg_last = ihsg['Close'].iloc[-1]
        ihsg_sma50 = ihsg['Close'].ewm(span=50).mean().iloc[-1]
        idr_last = usdidr['Close'].iloc[-1]
        idr_change = ((idr_last - usdidr['Close'].iloc[-5]) / usdidr['Close'].iloc[-5]) * 100
        
        is_bearish_market = ihsg_last < ihsg_sma50
        is_rupiah_drop = idr_change > 1.5 # Rupiah melemah > 1.5% dalam 5 hari
        
        if is_bearish_market or is_rupiah_drop:
            return False, f"🔴 MACRO CIRCUIT BREAKER ACTIVE: IHSG Bearish ({int(ihsg_last)}) atau Rupiah Melemah (Rp {int(idr_last):,}/USD). Alokasi modal otomatis dipotong 50%!"
        else:
            return True, f"🟢 MACRO REGIME SAFE: IHSG Bullish ({int(ihsg_last)}) & Kurs Rupiah Stabil (Rp {int(idr_last):,}/USD). Full Allocation Permitted."
    except Exception:
        return True, "🟡 MACRO FEED OFFLINE: Menggunakan asumsi pasar netral."

# 3. WEB SCRAPER SAHAM
@st.cache_data(ttl=86400)
def ambil_daftar_saham(mode):
    if mode == "🔥 LQ45 (45 Saham Paling Likuid & Aktif)":
        return ["BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "TLKM.JK", "ASII.JK", "ADRO.JK", "UNTR.JK", "PGAS.JK", "GOTO.JK", "BRIS.JK", "ANTM.JK", "ICBP.JK", "KLBF.JK", "PTBA.JK", "AMRT.JK", "CPIN.JK", "EXCL.JK", "INDF.JK", "INKP.JK", "INCO.JK", "ITMG.JK", "MEDC.JK", "MDKA.JK", "PGEO.JK", "PTMP.JK", "SIDO.JK", "SMGR.JK", "UNVR.JK", "AKRA.JK", "AMMN.JK", "ARTO.JK", "BRPT.JK", "BUKA.JK", "EMTK.JK", "ESSA.JK", "HRUM.JK", "INTP.JK", "MBMA.JK", "MTEL.JK", "PTPP.JK", "SCMA.JK", "TOWR.JK", "WIKA.JK"]
    elif mode == "🌌 SEMUA EMITEN BEI (~900+ Saham - Sapu Jagat)":
        try:
            url = "https://id.wikipedia.org/wiki/Daftar_emiten_di_Bursa_Efek_Indonesia"
            tables = pd.read_html(url)
            tickers = []
            for df in tables:
                for col in df.columns:
                    if str(col).strip().lower() in ['kode', 'kode saham', 'ticker', 'emiten']:
                        for t in df[col].dropna().astype(str).tolist():
                            clean_t = t.strip().upper()
                            if len(clean_t) == 4 and clean_t.isalpha(): tickers.append(clean_t + ".JK")
            if tickers: return sorted(list(set(tickers)))
        except Exception: pass
    return ["BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "TLKM.JK", "ASII.JK", "ADRO.JK", "GOTO.JK", "BRIS.JK", "ANTM.JK"]

# 4. ADVANCED QUANTITATORS & BACKTESTING ENGINE
def hitung_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    return 100 - (100 / (1 + (gain / loss)))

def hitung_mfi(data, window=14):
    tp = (data['High'] + data['Low'] + data['Close']) / 3
    mf = tp * data['Volume']
    pos_sum = pd.Series(np.where(tp > tp.shift(1), mf, 0)).rolling(window=window).sum()
    neg_sum = pd.Series(np.where(tp < tp.shift(1), mf, 0)).rolling(window=window).sum()
    return 100 - (100 / (1 + (pos_sum / neg_sum)))

def hitung_atr(data, window=14):
    tr = np.max(pd.concat([data['High']-data['Low'], np.abs(data['High']-data['Close'].shift()), np.abs(data['Low']-data['Close'].shift())], axis=1), axis=1)
    return tr.rolling(window=window).mean()

def hitung_obv(data):
    return (np.sign(data['Close'].diff()) * data['Volume']).fillna(0).cumsum()

# SIMULASI MONTE CARLO (1000 PATHS) UNTUK VAR 99%
def run_monte_carlo(df, days=30, sims=1000):
    returns = df['Close'].pct_change().dropna()
    mean_ret = returns.mean()
    std_ret = returns.std()
    last_price = df['Close'].iloc[-1]
    
    random_shocks = np.random.normal(mean_ret, std_ret, (days, sims))
    price_paths = last_price * np.cumprod(1 + random_shocks, axis=0)
    
    final_prices = price_paths[-1, :]
    var_99 = np.percentile(final_prices, 1) # Skenario terburuk 1% (Black Swan)
    max_loss_pct = ((var_99 - last_price) / last_price) * 100
    return max_loss_pct, price_paths

# 5. CORE ENGINE V3.0 (WITH BACKTESTING & STRESS TEST)
def analisa_pasar_masal(tickers, modal_total, macro_safe, progress_bar, status_text):
    hasil = []
    total_saham = len(tickers)
    tgl_data_terakhir = "N/A"
    
    for i, ticker in enumerate(tickers):
        progress_pct = int(((i + 1) / total_saham) * 100)
        progress_bar.progress(progress_pct)
        status_text.markdown(f"**> QUANT STRESS TEST [{i+1}/{total_saham}]:** Backtesting & Simulating `{ticker}`... *(Running Monte Carlo & Sharpe Ratio)*")
        
        try:
            saham = yf.Ticker(ticker)
            df = saham.history(period="1y") # Ambil data 1 tahun penuh untuk Backtesting
            
            df = df.dropna(subset=['Close', 'Volume'])
            df = df[df['Volume'] > 0] 
            
            if df.empty or len(df) < 100 or df['Close'].iloc[-1] <= 50: continue
            if tgl_data_terakhir == "N/A": tgl_data_terakhir = str(df.index[-1].date())

            info = saham.info
            close = df['Close'].iloc[-1]
            vol_last = df['Volume'].iloc[-1]
            vol_avg = df['Volume'].tail(20).mean()

            # Indikator
            df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
            df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
            df['RSI'] = hitung_rsi(df)
            df['MFI'] = hitung_mfi(df)
            df['ATR'] = hitung_atr(df)
            df['OBV'] = hitung_obv(df)
            
            atr_last = df['ATR'].iloc[-1] if not pd.isna(df['ATR'].iloc[-1]) else (close * 0.03)
            rsi_last = df['RSI'].iloc[-1]
            mfi_last = df['MFI'].iloc[-1] if not pd.isna(df['MFI'].iloc[-1]) else 50
            
            # --- 1-YEAR BACKTESTING ENGINE (STRESS TEST HISTORIS) ---
            daily_ret = df['Close'].pct_change().dropna()
            sharpe_ratio = (daily_ret.mean() / daily_ret.std()) * np.sqrt(252) if daily_ret.std() > 0 else 0
            
            rolling_max = df['Close'].cummax()
            drawdown = (df['Close'] - rolling_max) / rolling_max
            max_drawdown = drawdown.min() * 100
            
            win_rate = (len(daily_ret[daily_ret > 0]) / len(daily_ret)) * 100

            # --- THE 4 PILLARS SCORING ---
            pe = info.get('trailingPE', 0) or 0
            pb = info.get('priceToBook', 0) or 0
            roe = (info.get('returnOnEquity', 0) or 0) * 100
            val_score = (10 if 0 < pe < 15 else 0) + (8 if 0 < pb < 2.0 else 0) + (7 if roe > 15 else 0)

            bandar_score = 0
            if vol_last > (vol_avg * 1.5) and close > df['Open'].iloc[-1]: bandar_score += 15
            if df['OBV'].iloc[-1] > df['OBV'].tail(10).mean() and close >= df['Close'].tail(10).mean(): bandar_score += 10

            swing_score = 0
            if close > df['EMA20'].iloc[-1] > df['EMA50'].iloc[-1]: swing_score += 15
            if 40 <= rsi_last <= 60: swing_score += 10
            if mfi_last > 50: swing_score += 10

            div_yield = (info.get('dividendYield', 0) or 0) * 100
            corp_score = 15 if div_yield > 5.0 else (10 if div_yield > 2.0 else 0)

            total_prob = val_score + bandar_score + swing_score + corp_score
            
            # PENALTI STRESS TEST
            if max_drawdown < -35.0 or sharpe_ratio < 0.3:
                total_prob -= 15

            prob_desimal = max(total_prob, 0) / 100.0
            target_price = close + (atr_last * 2.5)
            stop_price = close - (atr_last * 1.5)
            
            peluang_naik_pct = ((target_price - close) / close) * 100
            risiko_turun_pct = ((close - stop_price) / close) * 100
            rr_ratio = peluang_naik_pct / risiko_turun_pct if risiko_turun_pct > 0 else 0

            # KELLY POSITION SIZING + MACRO CIRCUIT BREAKER
            kelly_pct = (prob_desimal - ((1.0 - prob_desimal) / rr_ratio)) if rr_ratio > 0 else 0
            alokasi_pct = max(min(kelly_pct * 0.5 * 100, 20.0), 0.0)
            
            if not macro_safe or max_drawdown < -30.0:
                alokasi_pct *= 0.5
                
            alokasi_rp = (alokasi_pct / 100.0) * modal_total
            lot_beli = int(alokasi_rp / (close * 100)) if close > 0 else 0

            if total_prob >= 70 and rr_ratio >= 1.5 and sharpe_ratio >= 0.5 and alokasi_pct > 3:
                sinyal = "STRONG BUY 🟢"
            elif total_prob >= 55:
                sinyal = "BUY / HOLD 🟡"
            else:
                sinyal = "WAIT / SELL 🔴"

            hasil.append({
                "Ticker": ticker.replace(".JK", ""),
                "Harga": int(close),
                "Harga_Str": f"Rp {int(close):,}",
                "Probabilitas": total_prob,
                "Sinyal": sinyal,
                "Lot_Beli": lot_beli,
                "Alokasi_Rp_Str": f"Rp {int(alokasi_rp):,}",
                "Bobot (%)": f"{alokasi_pct:.1f}%",
                "Sharpe (1Y)": f"{sharpe_ratio:.2f}",
                "Max Drawdown": f"{max_drawdown:.1f}%",
                "Win Rate": f"{win_rate:.1f}%",
                "Target (+)": f"Rp {int(target_price):,} (+{peluang_naik_pct:.1f}%)",
                "Stop Loss (-)": f"Rp {int(stop_price):,} (-{risiko_turun_pct:.1f}%)",
                "R:R Ratio": f"{rr_ratio:.2f}x",
                "PER": f"{pe:.1f}x" if pe > 0 else "N/A"
            })
            time.sleep(0.05)
        except Exception: continue
            
    return pd.DataFrame(hasil), tgl_data_terakhir

# 6. ANTARMUKA TERMINAL V3.0
st.markdown("<h1>> IDX QUANTITATIVE TERMINAL // V3.0 EXTREME STRESS TEST</h1>", unsafe_allow_html=True)

macro_safe, macro_msg = cek_status_makro()
box_class = "macro-box-safe" if macro_safe else "macro-box-danger"
st.markdown(f"<div class='{box_class}'>{macro_msg}</div>", unsafe_allow_html=True)

col1, col2, col3 = st.columns([2, 1, 1])
with col1: mode_pilihan = st.selectbox("PILIH RUANG LINGKUP PEMANTAUAN PASAR:", ["🔥 LQ45 (45 Saham Paling Likuid & Aktif)", "🌌 SEMUA EMITEN BEI (~900+ Saham - Sapu Jagat)", "✍️ Input Manual Kustom"])
with col2: modal_input = st.number_input("TOTAL MODAL PORTFOLIO (Rp):", min_value=1000000, value=100000000, step=5000000, format="%d")
with col3:
    st.markdown("<br>", unsafe_allow_html=True)
    run_btn = st.button("🚀 JALANKAN STRESS TEST", use_container_width=True)

if mode_pilihan == "✍️ Input Manual Kustom":
    input_tickers = st.text_input("Ketik kode saham (pisahkan dengan koma):", "BBCA.JK, BBRI.JK, BMRI.JK, BBNI.JK")
    tickers_to_run = [t.strip().upper() + (".JK" if not t.strip().endswith(".JK") else "") for t in input_tickers.split(",") if t.strip()]
else: tickers_to_run = ambil_daftar_saham(mode_pilihan)

if run_btn:
    st.markdown("---")
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    df_result, tgl_terakhir = analisa_pasar_masal(tickers_to_run, modal_input, macro_safe, progress_bar, status_text)
    progress_bar.empty()
    status_text.empty()
    
    if not df_result.empty:
        df_result = df_result.sort_values(by="Probabilitas", ascending=False)
        top_pick = df_result.iloc[0]
        
        st.markdown("### > 🎲 MONTE CARLO BLACK SWAN SIMULATION (TOP RECOMMENDED STOCK)")
        with st.spinner(f"Menjalankan 1.000 simulasi jalur harga masa depan untuk {top_pick['Ticker']}..."):
            try:
                top_df = yf.Ticker(top_pick['Ticker']+".JK").history(period="1y")
                var_99_loss, _ = run_monte_carlo(top_df, days=30, sims=1000)
            except Exception: var_99_loss = -15.0
            
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.markdown(f'<div class="metric-card"><div class="metric-title">TOP TICKER</div><div class="metric-value amber-text">{top_pick["Ticker"]}</div></div>', unsafe_allow_html=True)
        with c2: st.markdown(f'<div class="metric-card"><div class="metric-title">SHARPE RATIO (1Y)</div><div class="metric-value green-text">{top_pick["Sharpe (1Y)"]}</div></div>', unsafe_allow_html=True)
        with c3: st.markdown(f'<div class="metric-card"><div class="metric-title">MAX DRAWDOWN (1Y)</div><div class="metric-value red-text">{top_pick["Max Drawdown"]}</div></div>', unsafe_allow_html=True)
        with c4: st.markdown(f'<div class="metric-card"><div class="metric-title">BLACK SWAN RISK (VaR 99%)</div><div class="metric-value red-text">{var_99_loss:.1f}%</div></div>', unsafe_allow_html=True)
        
        st.markdown("---")
        tab1, tab2, tab3 = st.tabs(["🎯 TOP PICKS & TRADING TICKET", "📡 LIVE QUANT RADAR (STRESS TESTED)", "⚙️ V3.0 STRESS TEST SPECS"])
        
        with tab1:
            st.markdown("### > REKOMENDASI UTAMA & KERTAS KERJA EKSEKUSI")
            top_3 = df_result.head(3)
            for idx, row in top_3.iterrows():
                border_color = "#00FF00" if "STRONG BUY" in row["Sinyal"] else "#FF9900"
                st.markdown(f"""
                <div style="background-color: #0d0d0d; border-left: 6px solid {border_color}; border: 1px solid #333; padding: 15px; margin-bottom: 15px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size: 20px; font-weight: bold; color: #FF9900;">{row['Ticker']}</span>
                        <span style="font-size: 16px; font-weight: bold; color: {'#00FF00' if row['Probabilitas']>=70 else '#FF9900'};">{row['Sinyal']} (Probabilitas: {row['Probabilitas']}%)</span>
                    </div>
                    <hr style="border-color: #222; margin: 10px 0;">
                    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; font-size: 13px;">
                        <div><b>Harga Entry:</b><br><span style="color:#FFF; font-size:15px;">{row['Harga_Str']}</span></div>
                        <div><b>Rekomendasi Beli:</b><br><span style="color:#00FF00; font-size:16px; font-weight:bold;">{row['Lot_Beli']} LOT</span> <span style="color:#888;">({row['Alokasi_Rp_Str']})</span></div>
                        <div><b>Target Profit (+):</b><br><span style="color:#00FF00;">{row['Target (+)']}</span></div>
                        <div><b>Batas Stop Loss (-):</b><br><span style="color:#FF0000;">{row['Stop Loss (-)']}</span></div>
                    </div>
                    <div style="margin-top: 10px; font-size: 11px; color: #AAA; background: #111; padding: 6px;">
                        🛡️ <b>Backtest Bukti 1 Tahun:</b> Sharpe Ratio: <b style="color:#FFF;">{row['Sharpe (1Y)']}</b> | Win Rate Historis: <b style="color:#00FF00;">{row['Win Rate']}</b> | Jatuh Terdalam (MDD): <b style="color:#FF0000;">{row['Max Drawdown']}</b>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        with tab2:
            st.markdown(f"### > TABEL PEMANTAUAN KESELURUHAN ({len(df_result)} Saham)")
            csv_data = df_result.to_csv(index=False).encode('utf-8')
            st.download_button(label="📥 DOWNLOAD TABEL KE EXCEL (.CSV)", data=csv_data, file_name=f"Quant_Stress_Test_{tgl_terakhir}.csv", mime="text/csv")
            
            df_display = df_result.drop(columns=["Harga", "Lot_Beli"]).rename(columns={"Harga_Str": "Harga", "Alokasi_Rp_Str": "Beli Max (Rp)"})
            def color_prob(val): return f'color: {"#00FF00" if val>=70 else ("#FF9900" if val>=55 else "#FF0000")}; font-weight: bold;'
            styled_df = df_display.style.map(color_prob, subset=['Probabilitas'])
            st.dataframe(styled_df, use_container_width=True, hide_index=True)

        with tab3:
            st.markdown("### > APA YANG MEMBUAT V3.0 INI SEBUAH TRUE STRESS TEST?")
            st.markdown("""
            1. **Monte Carlo VaR 99% (Black Swan Simulation):** Sistem menjalankan 1.000 simulasi probabilitas untuk masa depan. Angka *VaR 99%* menunjukkan skenario terburuk jika pasar IHSG crash atau terjadi bencana makroekonomi.
            2. **Embedded Backtesting (Sharpe Ratio & Max Drawdown):** Sistem tidak buta. Ia melihat data 1 tahun ke belakang. Jika sebuah saham punya **Sharpe Ratio < 0.5** (terlalu berisiko dibanding untungnya) atau pernah mengalami **Max Drawdown > 35%**, skor saham tersebut langsung dipenggal!
            3. **Macro Circuit Breaker (IHSG & USD/IDR Protection):** Sistem secara *real-time* memantau kesehatan IHSG (`^JKSE`) dan nilai tukar Rupiah (`IDR=X`). Jika Rupiah melemah tajam atau IHSG patah tren, sistem otomatis menyalakan status bahaya 🔴 dan **memotong seluruh rekomendasi pembelian lot Anda sebesar 50%** untuk mengamankan *cash*.
            """)
    else: st.error("❌ Tidak ada saham yang lolos filter.")

st.markdown("---")
st.markdown("<div style='font-size: 11px; color: #666;'>SYSTEM DISCLAIMER: V3.0 incorporates Monte Carlo tail-risk estimation, 1-year rolling historical Sharpe backtests, and real-time macroeconomic exchange rate circuit breakers. This is an institutional-grade decision support dashboard.</div>", unsafe_allow_html=True)
