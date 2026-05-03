import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import date, timedelta
import io

# ── PAGE CONFIG ──────────────────────────────────────────────
st.set_page_config(
    page_title="IMP Portfolio Analyser",
    page_icon="📊",
    layout="wide"
)

# ── STYLES ───────────────────────────────────────────────────
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
    .metric-card { background: #f8f9fa; border-radius: 8px; padding: 1rem; border-left: 4px solid #1F3864; }
    .stDataFrame { font-size: 13px; }
    div[data-testid="stMetric"] { background: #f8f9fa; padding: 0.8rem; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# ── HEADER ───────────────────────────────────────────────────
st.title("📊 IMP Model Portfolio — Performance Analyser")
st.caption("Fetches live NSE prices via Yahoo Finance · Compare any action date vs any comparison date · Supports multiple products")

st.divider()

# ── INSTRUCTIONS ─────────────────────────────────────────────
with st.expander("📋 How to use this tool", expanded=False):
    st.markdown("""
    1. **Paste your portfolio changes** in the text box below — one stock per line
    2. **Format:** `SCRIP | ACTION | DD-Mon-YY`  e.g. `TVSMOTOR | NEW | 29-Sep-25`
    3. **Set comparison date** — all prices will be fetched as of this date
    4. Click **Fetch & Analyse**
    5. Download results as Excel

    **Tips:**
    - Action must be `NEW` or `SOLD`
    - Ticker must match NSE symbol exactly (e.g. `M&M`, `IDFCFIRSTB`, `NATIONALUM`)
    - You can run multiple products one at a time — just paste different data
    - VMM (V-Mart) → use `VMART`
    """)

# ── SIDEBAR ──────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")
    comp_date = st.date_input(
        "Comparison Date",
        value=date(2026, 4, 17),
        min_value=date(2020, 1, 1),
        max_value=date.today(),
        help="All stocks will be compared against their price on this date"
    )
    product_name = st.text_input("Product Name (optional)", placeholder="e.g. IMP Alpha")
    st.divider()
    st.markdown("**About**")
    st.caption("Fetches NSE closing prices from Yahoo Finance (`SYMBOL.NS`). Prices are unadjusted closes. Corporate action handling coming soon.")

# ── DEFAULT DATA ─────────────────────────────────────────────
DEFAULT = """TVSMOTOR | NEW | 29-Sep-25
CANBK | NEW | 29-Sep-25
VOLTAS | NEW | 29-Sep-25
ACMESOLAR | NEW | 29-Sep-25
COFORGE | SOLD | 29-Sep-25
JKCEMENT | SOLD | 29-Sep-25
KAYNES | SOLD | 29-Sep-25
M&M | SOLD | 29-Sep-25
RUBICON | NEW | 02-Nov-25
IDFCFIRSTB | NEW | 02-Nov-25
ICICIBANK | SOLD | 02-Nov-25
NIVABUPA | SOLD | 02-Nov-25
HCLTECH | NEW | 28-Nov-25
POLYCAB | SOLD | 28-Nov-25
SBILIFE | NEW | 10-Dec-25
INDIGO | SOLD | 10-Dec-25
MOTHERSON | NEW | 04-Feb-26
TATASTEEL | NEW | 04-Feb-26
RADICO | SOLD | 04-Feb-26
VMART | SOLD | 04-Feb-26
KIRLOSENG | NEW | 01-Mar-26
NATIONALUM | NEW | 01-Mar-26
HAL | SOLD | 01-Mar-26
TIMETECHNO | SOLD | 01-Mar-26"""

# ── INPUT ────────────────────────────────────────────────────
st.subheader("📥 Paste Portfolio Changes")
raw_input = st.text_area(
    "One stock per line: SCRIP | ACTION | DD-Mon-YY",
    value=DEFAULT,
    height=280,
    help="Format: TVSMOTOR | NEW | 29-Sep-25"
)

fetch_btn = st.button("🚀 Fetch & Analyse", type="primary", use_container_width=True)

# ── PARSE INPUT ───────────────────────────────────────────────
def parse_input(raw):
    stocks = []
    errors = []
    for i, line in enumerate(raw.strip().splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 3:
            errors.append(f"Line {i}: Expected 3 columns separated by | — got: `{line}`")
            continue
        scrip, action, date_str = parts
        action = action.upper()
        if action not in ("NEW", "SOLD"):
            errors.append(f"Line {i}: Action must be NEW or SOLD — got `{action}`")
            continue
        try:
            action_date = pd.to_datetime(date_str, dayfirst=True).date()
        except:
            errors.append(f"Line {i}: Cannot parse date `{date_str}` — use DD-Mon-YY e.g. 29-Sep-25")
            continue
        stocks.append({"Scrip": scrip, "Action": action, "Action Date": action_date})
    return stocks, errors

# ── FETCH PRICE ───────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_price(ticker_ns, target_date):
    """Fetch closing price on or just before target_date. Returns (price, actual_date, error)."""
    start = target_date - timedelta(days=7)
    end   = target_date + timedelta(days=1)
    try:
        df = yf.download(ticker_ns, start=start, end=end, progress=False, auto_adjust=False)
        if df.empty:
            return None, None, "No data returned"
        # Flatten MultiIndex columns from yfinance >= 0.2.x
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        # Get close on or before target date
        df = df[df.index.date <= target_date]
        if df.empty:
            return None, None, f"No trading data on or before {target_date}"
        price = float(df["Close"].iloc[-1])
        actual_date = df.index[-1].date()
        return round(price, 2), actual_date, None
    except Exception as e:
        return None, None, str(e)

# ── VERDICT ───────────────────────────────────────────────────
def verdict(action, ret):
    if ret is None:
        return "—"
    if action == "NEW":
        if ret > 10:   return "✅ Outperformed"
        if ret > 0:    return "✅ In Profit"
        if ret > -5:   return "➡️ Roughly Flat"
        return "❌ Underperformed"
    else:
        if ret < -5:   return "✅ Exit Justified"
        if ret < 0:    return "✅ Mild Decline"
        if ret < 5:    return "➡️ Roughly Flat"
        return "⚠️ Missed Upside"

# ── MAIN LOGIC ───────────────────────────────────────────────
if fetch_btn:
    stocks, errors = parse_input(raw_input)

    if errors:
        for e in errors:
            st.error(e)
        st.stop()

    if not stocks:
        st.warning("No valid stocks found. Check your input format.")
        st.stop()

    st.divider()
    st.subheader(f"🔄 Fetching prices for {len(stocks)} stocks...")

    progress = st.progress(0)
    status   = st.empty()
    results  = []

    for i, s in enumerate(stocks):
        ticker_ns = s["Scrip"] + ".NS"
        scrip     = s["Scrip"]
        action    = s["Action"]
        act_date  = s["Action Date"]

        status.caption(f"Fetching {scrip} — action date price ({act_date})...")
        ap, ap_actual, ap_err = fetch_price(ticker_ns, act_date)

        status.caption(f"Fetching {scrip} — comparison date price ({comp_date})...")
        cp, cp_actual, cp_err = fetch_price(ticker_ns, comp_date)

        days = (comp_date - act_date).days
        chg = ret = ann = None
        if ap and cp:
            chg = round(cp - ap, 2)
            ret = round((cp - ap) / ap * 100, 2)
            ann = round(ret / days * 365, 2) if days > 0 else None

        results.append({
            "Scrip":              scrip,
            "Action":             action,
            "Action Date":        act_date,
            "Action Price (₹)":   ap,
            "Price Date (Action)":ap_actual,
            "Comp Price (₹)":     cp,
            "Price Date (Comp)":  cp_actual,
            "Change (₹)":         chg,
            "Return (%)":         ret,
            "Days":               days,
            "Ann. Return (%)":    ann,
            "Verdict":            verdict(action, ret),
            "Error":              " | ".join(filter(None, [ap_err, cp_err])) or None,
        })

        progress.progress((i + 1) / len(stocks))

    status.empty()
    progress.empty()

    df = pd.DataFrame(results)

    # ── SUMMARY METRICS ──────────────────────────────────────
    st.divider()
    title_str = f"📊 Results — {product_name}" if product_name else "📊 Results"
    st.subheader(title_str)
    st.caption(f"Comparison date: **{comp_date}**")

    adds  = df[df["Action"] == "NEW" ]["Return (%)"].dropna()
    exits = df[df["Action"] == "SOLD"]["Return (%)"].dropna()

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        avg_add = adds.mean()
        st.metric("Avg Return — Adds", f"{avg_add:+.1f}%" if not pd.isna(avg_add) else "—")
    with c2:
        avg_exit = exits.mean()
        st.metric("Avg Return — Exits", f"{avg_exit:+.1f}%" if not pd.isna(avg_exit) else "—")
    with c3:
        hit = (adds > 0).sum()
        st.metric("Adds in Profit", f"{hit}/{len(adds)}")
    with c4:
        just = (exits < 0).sum()
        st.metric("Exits Justified", f"{just}/{len(exits)}")
    with c5:
        if len(adds):
            best = df[df["Action"]=="NEW"].loc[df[df["Action"]=="NEW"]["Return (%)"].idxmax()]
            st.metric("Best Addition", best["Scrip"], f"{best['Return (%)']:+.1f}%")
    with c6:
        if len(exits):
            missed = df[df["Action"]=="SOLD"].loc[df[df["Action"]=="SOLD"]["Return (%)"].idxmax()]
            st.metric("Biggest Missed Upside", missed["Scrip"], f"{missed['Return (%)']:+.1f}%")

    # ── MAIN TABLE ───────────────────────────────────────────
    st.divider()
    st.subheader("📋 Stock-Level Detail")

    def colour_row(row):
        base = "background-color: #E2EFDA" if row["Action"] == "NEW" else "background-color: #FCE4D6"
        return [base] * len(row)

    def colour_return(val):
        if pd.isna(val) or val == "":  return ""
        if val > 0:   return "color: #1E7145; font-weight: bold"
        if val < 0:   return "color: #C00000; font-weight: bold"
        return ""

    display_df = df.drop(columns=["Error"], errors="ignore")
    styled = (
        display_df.style
        .apply(colour_row, axis=1)
        .map(colour_return, subset=["Return (%)", "Ann. Return (%)"])
        .format({
            "Action Price (₹)":  "₹{:,.2f}",
            "Comp Price (₹)":    "₹{:,.2f}",
            "Change (₹)":        "₹{:+,.2f}",
            "Return (%)":        "{:+.1f}%",
            "Ann. Return (%)":   "{:+.1f}%",
            "Days":              "{:.0f}",
        }, na_rep="—")
    )
    st.dataframe(styled, use_container_width=True, height=600)

    # ── ERRORS ───────────────────────────────────────────────
    errs = df[df["Error"].notna()]
    if not errs.empty:
        with st.expander(f"⚠️ {len(errs)} fetch error(s) — click to see"):
            for _, r in errs.iterrows():
                st.warning(f"**{r['Scrip']}**: {r['Error']} — enter price manually below if needed")

    # ── DATE BATCH SUMMARY ───────────────────────────────────
    st.divider()
    st.subheader("📅 Action Date Batch Summary")

    batch_rows = []
    for dt, grp in df.groupby("Action Date"):
        adds_g  = grp[grp["Action"]=="NEW"]["Return (%)"].dropna()
        exits_g = grp[grp["Action"]=="SOLD"]["Return (%)"].dropna()
        avg_a = adds_g.mean()  if len(adds_g)  else None
        avg_e = exits_g.mean() if len(exits_g) else None
        alpha = (avg_a - avg_e) if (avg_a is not None and avg_e is not None) else None
        batch_rows.append({
            "Action Date":       dt,
            "# Adds":            len(adds_g),
            "# Exits":           len(exits_g),
            "Avg Add Return":    f"{avg_a:+.1f}%" if avg_a is not None else "—",
            "Avg Exit Return":   f"{avg_e:+.1f}%" if avg_e is not None else "—",
            "Add Winners":       f"{(adds_g>0).sum()}/{len(adds_g)}" if len(adds_g) else "—",
            "Exits Justified":   f"{(exits_g<0).sum()}/{len(exits_g)}" if len(exits_g) else "—",
            "Net Alpha":         f"{alpha:+.1f}%" if alpha is not None else "—",
            "Rotation Verdict":  ("✅ Strong Alpha" if alpha and alpha > 5
                                  else "✅ Positive" if alpha and alpha > 0
                                  else "➡️ Neutral" if alpha and alpha > -5
                                  else "⚠️ Negative Alpha") if alpha is not None else "—",
        })

    batch_df = pd.DataFrame(batch_rows)
    st.dataframe(batch_df, use_container_width=True, hide_index=True)

    # ── MANUAL OVERRIDE ──────────────────────────────────────
    st.divider()
    st.subheader("✏️ Manual Price Override")
    st.caption("If any stock shows a fetch error or you want to use exact NSE closing prices, enter them here.")

    override_scrips = df["Scrip"].tolist()
    override_cols   = st.columns(3)
    overrides = {}
    for idx, scrip in enumerate(override_scrips):
        col = override_cols[idx % 3]
        with col:
            row = df[df["Scrip"]==scrip].iloc[0]
            with st.expander(f"{scrip} ({row['Action']} · {row['Action Date']})"):
                ap_ov = st.number_input(f"Action Price ₹", value=float(row["Action Price (₹)"]) if row["Action Price (₹)"] else 0.0, key=f"ap_{scrip}", step=0.5)
                cp_ov = st.number_input(f"Comp Price ₹",   value=float(row["Comp Price (₹)"]) if row["Comp Price (₹)"] else 0.0, key=f"cp_{scrip}", step=0.5)
                if ap_ov > 0 and cp_ov > 0:
                    overrides[scrip] = (ap_ov, cp_ov)

    if overrides:
        st.info(f"Overrides set for: {', '.join(overrides.keys())} — click **Fetch & Analyse** again to apply, or download current results.")

    # ── DOWNLOAD ─────────────────────────────────────────────
    st.divider()
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Stock Detail", index=False)
        batch_df.to_excel(writer, sheet_name="Batch Summary", index=False)

    fname = f"IMP_{product_name.replace(' ','_') if product_name else 'Portfolio'}_{comp_date}.xlsx"
    st.download_button(
        label="⬇️ Download Full Results as Excel",
        data=buf.getvalue(),
        file_name=fname,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        type="primary"
    )
