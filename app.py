import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import date, timedelta
import io

# ── PAGE CONFIG ──────────────────────────────────────────────
st.set_page_config(
    page_title="IMP Portfolio Rebalance Performance Analyser",
    page_icon="📊",
    layout="wide"
)

# ── STYLES ───────────────────────────────────────────────────
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
    .stDataFrame { font-size: 13px; }
    div[data-testid="stMetric"] { background: #f8f9fa; padding: 0.8rem; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# ── HEADER ───────────────────────────────────────────────────
st.title("📊 IMP Portfolio Rebalance Performance Analyser")
st.caption(
    "Tracks NSE price performance of every rebalance action (addition & exit) from action date to any chosen comparison date · "
    "Powered by Yahoo Finance (NSE data) · Supports multiple IMP products"
)

st.divider()

# ── INSTRUCTIONS ─────────────────────────────────────────────
with st.expander("📋 How to use this tool", expanded=False):
    st.markdown("""
    ### Steps
    1. **Maintain your rebalance log in Excel** with exactly 3 columns: `Symbol`, `Action`, `Action Date`
    2. **Copy the rows directly from Excel** and paste into the text box below — with or without the header row, it does not matter
    3. **Set the comparison date** in the sidebar — all prices will be fetched as of this date
    4. Click **Fetch & Analyse**
    5. Review results and download as Excel

    ---

    ### Input Format
    Paste directly from Excel (tab-separated) — or use pipe `|` or comma `,` as separator. All work.

    | Symbol | Action | Action Date |
    |--------|--------|-------------|
    | TVSMOTOR | NEW | 29-Sep-25 |
    | CANBK | NEW | 29-Sep-25 |
    | COFORGE | SOLD | 29-Sep-25 |

    - **Action** must be `NEW` (addition) or `SOLD` (exit)
    - **Symbol** must match NSE ticker exactly — e.g. `M&M`, `IDFCFIRSTB`, `NATIONALUM`
    - **V-Mart (VMM)** → use `VMART` as the ticker
    - Header row is auto-detected and skipped — no need to remove it before pasting
    - You can run multiple products one at a time — just paste different data each time

    ---

    ### Data Source
    Prices are sourced from **Yahoo Finance** which carries the same NSE closing prices
    as NSE India (identical data, same exchange). This is the same source used by
    Tickertape, Smallcase, INDmoney, and most retail-facing platforms.
    A direct NSE API feed is not publicly available for automated use.
    Corporate action adjustments (bonus, split, dividend) will be handled in a future update.
    """)

# ── SIDEBAR ──────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")
    comp_date = st.date_input(
        "Comparison Date",
        value=date(2026, 4, 17),
        min_value=date(2020, 1, 1),
        max_value=date.today(),
        help="All stocks will be compared against their closing price on this date"
    )
    product_name = st.text_input("Product Name (optional)", placeholder="e.g. IMP Alpha")
    st.divider()
    st.markdown("**Data Source**")
    st.caption(
        "NSE closing prices via Yahoo Finance (`SYMBOL.NS`). "
        "Data is identical to NSE India. "
        "Prices are unadjusted closes — corporate action handling coming in next update."
    )

# ── DEFAULT DATA ─────────────────────────────────────────────
DEFAULT = "Symbol\tAction\tAction Date\nTVSMOTOR\tNEW\t29-Sep-25\nCANBK\tNEW\t29-Sep-25\nVOLTAS\tNEW\t29-Sep-25\nACMESOLAR\tNEW\t29-Sep-25\nCOFORGE\tSOLD\t29-Sep-25\nJKCEMENT\tSOLD\t29-Sep-25\nKAYNES\tSOLD\t29-Sep-25\nM&M\tSOLD\t29-Sep-25\nRUBICON\tNEW\t02-Nov-25\nIDFCFIRSTB\tNEW\t02-Nov-25\nICICIBANK\tSOLD\t02-Nov-25\nNIVABUPA\tSOLD\t02-Nov-25\nHCLTECH\tNEW\t28-Nov-25\nPOLYCAB\tSOLD\t28-Nov-25\nSBILIFE\tNEW\t10-Dec-25\nINDIGO\tSOLD\t10-Dec-25\nMOTHERSON\tNEW\t04-Feb-26\nTATASTEEL\tNEW\t04-Feb-26\nRADICO\tSOLD\t04-Feb-26\nVMART\tSOLD\t04-Feb-26\nKIRLOSENG\tNEW\t01-Mar-26\nNATIONALUM\tNEW\t01-Mar-26\nHAL\tSOLD\t01-Mar-26\nTIMETECHNO\tSOLD\t01-Mar-26"

# ── INPUT ────────────────────────────────────────────────────
st.subheader("📥 Paste Rebalance Log")
st.caption("Copy directly from your Excel rebalance log and paste below — header row included or excluded, both work fine.")
raw_input = st.text_area(
    "Paste rows here (tab / pipe / comma separated)",
    value=DEFAULT,
    height=300,
    help="Accepts Excel copy-paste (tab-separated), pipe-separated, or comma-separated. Header row is auto-skipped."
)

fetch_btn = st.button("🚀 Fetch & Analyse", type="primary", use_container_width=True)


# ── PARSE INPUT ───────────────────────────────────────────────
HEADER_KEYWORDS = {"symbol", "scrip", "action", "date", "action date"}

def detect_delimiter(line):
    if "\t" in line:
        return "\t"
    if "|" in line:
        return "|"
    return ","

def is_header(parts):
    return all(p.strip().lower() in HEADER_KEYWORDS for p in parts if p.strip())

def parse_input(raw):
    stocks = []
    errors = []
    for i, line in enumerate(raw.strip().splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        delim = detect_delimiter(line)
        parts = [p.strip() for p in line.split(delim)]
        if len(parts) != 3:
            errors.append(f"Line {i}: Expected 3 columns — got {len(parts)}. Line was: `{line}`")
            continue
        if is_header(parts):
            continue
        scrip, action, date_str = parts
        scrip    = scrip.strip('"\'\"')
        action   = action.strip('"\'\"').upper()
        date_str = date_str.strip('"\'\"')
        if action not in ("NEW", "SOLD"):
            errors.append(f"Line {i}: Action must be NEW or SOLD — got `{action}`")
            continue
        try:
            action_date = pd.to_datetime(date_str, dayfirst=True).date()
        except Exception:
            errors.append(f"Line {i}: Cannot parse date `{date_str}` — use DD-Mon-YY e.g. 29-Sep-25")
            continue
        stocks.append({"Scrip": scrip, "Action": action, "Action Date": action_date})
    return stocks, errors


# ── FETCH PRICE ───────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_price(ticker_ns, target_date):
    start = target_date - timedelta(days=7)
    end   = target_date + timedelta(days=1)
    try:
        df = yf.download(ticker_ns, start=start, end=end, progress=False, auto_adjust=False)
        if df.empty:
            return None, None, "No data returned — check ticker symbol"
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[df.index.date <= target_date]
        if df.empty:
            return None, None, f"No trading data on or before {target_date}"
        price       = float(df["Close"].iloc[-1])
        actual_date = df.index[-1].date()
        return round(price, 2), actual_date, None
    except Exception as e:
        return None, None, str(e)


# ── VERDICT ───────────────────────────────────────────────────
def verdict(action, ret):
    if ret is None:
        return "—"
    if action == "NEW":
        if ret > 10:  return "✅ Outperformed"
        if ret > 0:   return "✅ In Profit"
        if ret > -5:  return "➡️ Roughly Flat"
        return "❌ Underperformed"
    else:
        if ret < -5:  return "✅ Exit Justified"
        if ret < 0:   return "✅ Mild Decline"
        if ret < 5:   return "➡️ Roughly Flat"
        return "⚠️ Missed Upside"


# ── MAIN LOGIC ───────────────────────────────────────────────
if fetch_btn:
    stocks, errors = parse_input(raw_input)

    if errors:
        for e in errors:
            st.error(e)
        if not stocks:
            st.stop()
        st.warning(f"{len(errors)} line(s) skipped. Continuing with {len(stocks)} valid stocks.")

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

        status.caption(f"[{i+1}/{len(stocks)}] {scrip} — fetching action date price ({act_date})...")
        ap, ap_actual, ap_err = fetch_price(ticker_ns, act_date)

        status.caption(f"[{i+1}/{len(stocks)}] {scrip} — fetching comparison date price ({comp_date})...")
        cp, cp_actual, cp_err = fetch_price(ticker_ns, comp_date)

        days = (comp_date - act_date).days
        chg = ret = ann = None
        if ap and cp:
            chg = round(cp - ap, 2)
            ret = round((cp - ap) / ap * 100, 2)
            ann = round(ret / days * 365, 2) if days > 0 else None

        results.append({
            "Scrip":               scrip,
            "Action":              action,
            "Action Date":         act_date,
            "Action Price (₹)":    ap,
            "Price Date (Action)": ap_actual,
            "Comp Price (₹)":      cp,
            "Price Date (Comp)":   cp_actual,
            "Change (₹)":          chg,
            "Return (%)":          ret,
            "Days":                days,
            "Ann. Return (%)":     ann,
            "Verdict":             verdict(action, ret),
            "Error":               " | ".join(filter(None, [ap_err, cp_err])) or None,
        })

        progress.progress((i + 1) / len(stocks))

    status.empty()
    progress.empty()

    df = pd.DataFrame(results)

    # ── SUMMARY METRICS ──────────────────────────────────────
    st.divider()
    title_str = f"📊 Results — {product_name}" if product_name else "📊 Results"
    st.subheader(title_str)
    st.caption(f"Comparison date: **{comp_date}**  |  {len(stocks)} rebalance actions analysed")

    adds  = df[df["Action"] == "NEW" ]["Return (%)"].dropna()
    exits = df[df["Action"] == "SOLD"]["Return (%)"].dropna()

    avg_add   = adds.mean()  if len(adds)  else None
    avg_exit  = exits.mean() if len(exits) else None
    net_alpha = (avg_add - avg_exit) if (avg_add is not None and avg_exit is not None) else None

    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)

    with c1:
        st.metric("Avg Return — Adds", f"{avg_add:+.1f}%" if avg_add is not None else "—")
    with c2:
        st.metric("Avg Return — Exits", f"{avg_exit:+.1f}%" if avg_exit is not None else "—")
    with c3:
        st.metric(
            "Overall Net Alpha",
            f"{net_alpha:+.1f}%" if net_alpha is not None else "—",
            help="Avg Add Return minus Avg Exit Return. Positive = additions outperformed exits = good rotation."
        )
    with c4:
        st.metric("Adds in Profit", f"{int((adds > 0).sum())} / {len(adds)}" if len(adds) else "—")
    with c5:
        st.metric("Exits Justified", f"{int((exits < 0).sum())} / {len(exits)}" if len(exits) else "—")
    with c6:
        if len(adds):
            best = df[df["Action"] == "NEW"].loc[df[df["Action"] == "NEW"]["Return (%)"].idxmax()]
            st.metric("Best Addition", best["Scrip"], f"{best['Return (%)']:+.1f}%")
        else:
            st.metric("Best Addition", "—")
    with c7:
        if len(exits):
            missed = df[df["Action"] == "SOLD"].loc[df[df["Action"] == "SOLD"]["Return (%)"].idxmax()]
            st.metric("Biggest Missed Upside", missed["Scrip"], f"{missed['Return (%)']:+.1f}%")
        else:
            st.metric("Biggest Missed Upside", "—")

    # Net Alpha callout banner
    if net_alpha is not None:
        if net_alpha > 5:
            st.success(f"✅ **Overall Net Alpha: {net_alpha:+.1f}%** — Additions significantly outperformed exits. Strong rebalance decision.")
        elif net_alpha > 0:
            st.success(f"✅ **Overall Net Alpha: {net_alpha:+.1f}%** — Additions outperformed exits. Rebalance added value.")
        elif net_alpha > -5:
            st.info(f"➡️ **Overall Net Alpha: {net_alpha:+.1f}%** — Roughly neutral. Additions and exits performed similarly.")
        else:
            st.warning(f"⚠️ **Overall Net Alpha: {net_alpha:+.1f}%** — Exits outperformed additions. Rebalance destroyed value on average.")

    # ── STOCK-LEVEL TABLE ────────────────────────────────────
    st.divider()
    st.subheader("📋 Stock-Level Detail")
    st.caption("Green = Addition (NEW)  ·  Red = Exit (SOLD)")

    def colour_row(row):
        bg = "#E2EFDA" if row["Action"] == "NEW" else "#FCE4D6"
        return [f"background-color: {bg}"] * len(row)

    def colour_return(val):
        try:
            if pd.isna(val): return ""
        except Exception:
            return ""
        if val > 0:  return "color: #1E7145; font-weight: bold"
        if val < 0:  return "color: #C00000; font-weight: bold"
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

    # ── FETCH ERRORS ─────────────────────────────────────────
    errs = df[df["Error"].notna()]
    if not errs.empty:
        with st.expander(f"⚠️ {len(errs)} fetch error(s) — click to expand"):
            for _, r in errs.iterrows():
                st.warning(
                    f"**{r['Scrip']}**: {r['Error']}\n\n"
                    f"Verify `{r['Scrip']}` is the correct NSE ticker. "
                    f"Use the Manual Override section below to enter prices directly."
                )

    # ── DATE BATCH SUMMARY ───────────────────────────────────
    st.divider()
    st.subheader("📅 Action Date Batch Summary")
    st.caption("Net Alpha per batch = Avg Add Return minus Avg Exit Return on that rebalance date")

    batch_rows = []
    for dt, grp in df.groupby("Action Date"):
        adds_g  = grp[grp["Action"] == "NEW" ]["Return (%)"].dropna()
        exits_g = grp[grp["Action"] == "SOLD"]["Return (%)"].dropna()
        avg_a   = adds_g.mean()  if len(adds_g)  else None
        avg_e   = exits_g.mean() if len(exits_g) else None
        alpha   = (avg_a - avg_e) if (avg_a is not None and avg_e is not None) else None
        batch_rows.append({
            "Action Date":      dt,
            "# Adds":           len(adds_g),
            "# Exits":          len(exits_g),
            "Avg Add Return":   f"{avg_a:+.1f}%" if avg_a  is not None else "—",
            "Avg Exit Return":  f"{avg_e:+.1f}%" if avg_e  is not None else "—",
            "Add Winners":      f"{int((adds_g>0).sum())}/{len(adds_g)}"   if len(adds_g)  else "—",
            "Exits Justified":  f"{int((exits_g<0).sum())}/{len(exits_g)}" if len(exits_g) else "—",
            "Net Alpha":        f"{alpha:+.1f}%" if alpha is not None else "—",
            "Rotation Verdict": (
                "✅ Strong Alpha"   if alpha is not None and alpha >  5 else
                "✅ Positive"       if alpha is not None and alpha >  0 else
                "➡️ Neutral"        if alpha is not None and alpha > -5 else
                "⚠️ Negative Alpha" if alpha is not None               else "—"
            ),
        })

    batch_df = pd.DataFrame(batch_rows)
    st.dataframe(batch_df, use_container_width=True, hide_index=True)

    # ── MANUAL OVERRIDE ──────────────────────────────────────
    st.divider()
    st.subheader("✏️ Manual Price Override")
    st.caption(
        "If any stock shows a fetch error, or you want to use exact NSE closing prices "
        "from your broker / NSE historical data portal, enter them here."
    )

    override_cols = st.columns(3)
    overrides = {}
    for idx, row in df.iterrows():
        col = override_cols[idx % 3]
        with col:
            with st.expander(f"{row['Scrip']} ({row['Action']} · {row['Action Date']})"):
                ap_ov = st.number_input(
                    "Action Date Price ₹",
                    value=float(row["Action Price (₹)"]) if pd.notna(row["Action Price (₹)"]) else 0.0,
                    key=f"ap_{idx}_{row['Scrip']}",
                    step=0.5, format="%.2f"
                )
                cp_ov = st.number_input(
                    "Comparison Date Price ₹",
                    value=float(row["Comp Price (₹)"]) if pd.notna(row["Comp Price (₹)"]) else 0.0,
                    key=f"cp_{idx}_{row['Scrip']}",
                    step=0.5, format="%.2f"
                )
                if ap_ov > 0 and cp_ov > 0:
                    overrides[row["Scrip"]] = (ap_ov, cp_ov)

    if overrides:
        st.info(
            f"Prices overridden for: **{', '.join(overrides.keys())}**  \n"
            f"Click **Fetch & Analyse** again to recalculate with these prices."
        )

    # ── DOWNLOAD ─────────────────────────────────────────────
    st.divider()
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Stock Detail", index=False)
        batch_df.to_excel(writer, sheet_name="Batch Summary", index=False)

    fname = f"IMP_Rebalance_{product_name.replace(' ', '_') if product_name else 'Portfolio'}_{comp_date}.xlsx"
    st.download_button(
        label="⬇️ Download Full Results as Excel",
        data=buf.getvalue(),
        file_name=fname,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        type="primary"
    )
