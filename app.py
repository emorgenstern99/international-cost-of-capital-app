"""International cost of capital: USD vs. selected-country currency.

Formulas (course packet, ch. 12):
  D/E      = d / (1 - d)
  beta_E   = beta_U * [1 + (1 - tau) * D/E]
  Re (USD) = Rf_US + beta_E * ERP
  Rd (USD) = Rf_US + s
  WACC     = (1 - d) * Re + d * Rd * (1 - tau)
  F        = (1 + Rf_foreign) / (1 + Rf_US)          # expected depreciation factor
  Re*      = (1 + Re) * F - 1
  s*       = s * F   (default)  ->  Rd* = Rf_foreign + s*   (= F * (1 + Rd) - 1)
  WACC*    = (1 - d) * Re* + d * Rd* * (1 - tau)
"""
import io
import re
from datetime import datetime

import numpy as np
import pandas as pd
import requests
import streamlit as st

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CostOfCapitalApp/1.0)"}
BETA_URL = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls"
RATINGS_URL = "https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html"
OECD_URL = ("https://www.oecd.org/en/publications/corporate-tax-statistics-2024_9c27d6e8-en/"
            "full-report/statutory-corporate-income-tax-rates_440f9286.html")
TE_URL = "https://tradingeconomics.com/bonds"

DEFAULT_INDUSTRY = "Software (System & Application)"
DEFAULT_COUNTRY = "United States"

# ---- Fallbacks (used only if a live fetch fails; labelled as such in the UI) ----
FALLBACK_SPREAD = 1.11  # percent, BBB, Damodaran Jan 2026
FALLBACK_BETAS = {DEFAULT_INDUSTRY: 1.2254}
FALLBACK_YIELDS = {  # percent, 10-year, Nov 6 2026 (course packet)
    "Brazil": 15.2, "Colombia": 12.8, "Mexico": 9.1, "India": 7.2, "Poland": 6.2,
    "United Kingdom": 5.2, "Australia": 5.0, "United States": 4.9, "France": 4.8,
    "Slovakia": 4.2, "Portugal": 3.7, "Canada": 3.7, "Germany": 3.3, "Japan": 2.6,
    "China": 1.6, "Switzerland": 0.4}
_TAX = """France 36.1,Argentina 35,Germany 30.1,Australia 30,Kenya 30,Mexico 30,Nigeria 30,Senegal 30,
Zambia 30,Japan 29.7,Portugal 29.5,Peru 29.5,Pakistan 29,Congo 28,New Zealand 28,Italy 27.8,
South Korea 27.5,Chile 27,Dominican Republic 27,South Africa 27,Greenland 26.5,Canada 26,
Netherlands 25.8,United States 25.5,India 25.2,Angola 25,Belgium 25,China 25,Spain 25,
United Kingdom 25,Jamaica 25,Monaco 25,Panama 25,Philippines 25,Uruguay 25,Türkiye 25,Malaysia 24,
Slovakia 24,Luxembourg 23.9,Austria 23,Israel 23,Egypt 22.5,Botswana 22,Denmark 22,Greece 22,
Indonesia 22,Norway 22,Slovenia 22,Estonia 22,Czechia 21,Sweden 20.6,Cabo Verde 20.4,Iceland 20,
Azerbaijan 20,Finland 20,Jordan 20,Kazakhstan 20,Latvia 20,Saudi Arabia 20,Thailand 20,Vietnam 20,
Tunisia 20,Switzerland 19.5,Poland 19,Brunei 18.5,Armenia 18,Croatia 18,Ukraine 18,Singapore 17,
Lithuania 17,Hong Kong 16.5,Romania 16,Albania 15,Georgia 15,Kuwait 15,Ireland 12.5,Macau 12,
Bulgaria 10,Paraguay 10,Qatar 10,United Arab Emirates 9,Hungary 9"""
FALLBACK_TAX = {k.strip(): float(v) for k, v in
                (item.rsplit(" ", 1) for item in _TAX.replace("\n", "").split(",") if item.strip())}
ALIASES = {"Turkey": "Türkiye", "Czech Republic": "Czechia", "Slovak Republic": "Slovakia",
           "UAE": "United Arab Emirates", "Cape Verde": "Cabo Verde", "Macao": "Macau",
           "U.K.": "United Kingdom", "Dominican R.": "Dominican Republic",
           "Korea, South": "South Korea", "Korea": "South Korea", "Republic of Korea": "South Korea",
           "United States of America": "United States", "U.S.": "United States", "USA": "United States"}


def canon(name: str) -> str:
    name = re.sub(r"[\*†\d]+$", "", str(name)).strip()
    return ALIASES.get(name, name)


# ------------------------------------------------------------------ data fetch
@st.cache_data(ttl=6 * 3600, show_spinner=False)
def load_betas():
    meta = {"source": "Damodaran, betas.xls (Industry Averages)", "live": True, "date": "n/a", "note": ""}
    try:
        r = requests.get(BETA_URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        raw = pd.read_excel(io.BytesIO(r.content), sheet_name="Industry Averages", header=None)
        hdr = raw.index[raw.iloc[:, 0].astype(str).str.strip().str.lower() == "industry name"][0]
        for v in raw.iloc[:hdr, 0].dropna().astype(str):
            m = re.search(r"(?:January|February|March|April|May|June|July|August|September|October|"
                          r"November|December)\s+\d{4}|\b20\d{2}\b", v)
            if m:
                meta["date"] = m.group(0)
        df = raw.iloc[hdr + 1:].copy()
        df.columns = [str(c).strip() for c in raw.iloc[hdr]]
        col = next(c for c in df.columns if c.lower() == "unlevered beta")
        df = df[["Industry Name", col]].rename(columns={"Industry Name": "Industry", col: "beta_u"})
        df["beta_u"] = pd.to_numeric(df["beta_u"], errors="coerce")
        df = df.dropna()
        df = df[~df["Industry"].astype(str).str.startswith("Total Market")].reset_index(drop=True)
        return df, meta
    except Exception as e:  # noqa: BLE001
        meta.update(live=False, note=f"Live fetch failed ({type(e).__name__}); showing fallback.", date="Jan 2026")
        return pd.DataFrame({"Industry": list(FALLBACK_BETAS), "beta_u": list(FALLBACK_BETAS.values())}), meta


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def load_bbb_spread():
    meta = {"source": "Damodaran, ratings.html (Baa2/BBB, large non-financial firms)", "live": True,
            "date": "n/a", "note": ""}
    try:
        r = requests.get(RATINGS_URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        m = re.search(r"(?:January|February|March|April|May|June|July|August|September|October|"
                      r"November|December)\s+\d{4}", r.text)
        meta["date"] = m.group(0) if m else "n/a"
        for t in pd.read_html(io.StringIO(r.text)):
            for _, row in t.iterrows():
                cells = [str(x) for x in row.values]
                if any("Baa2/BBB" in c for c in cells):
                    pct = [float(re.sub(r"[^\d.]", "", c)) for c in cells
                           if "%" in c and re.search(r"\d", c)]
                    if pct:
                        return pct[-1], meta  # last % cell in the row = spread
        raise ValueError("BBB row not found")
    except Exception as e:  # noqa: BLE001
        meta.update(live=False, date="Jan 2026", note=f"Live fetch failed ({type(e).__name__}); showing fallback.")
        return FALLBACK_SPREAD, meta


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def load_tax():
    meta = {"source": "OECD Corporate Tax Statistics (statutory CIT rates)", "live": True, "date": "n/a", "note": ""}
    try:
        r = requests.get(OECD_URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        best = {}
        for t in pd.read_html(io.StringIO(r.text)):
            cname = next((c for c in t.columns if re.search(r"country|jurisdiction", str(c), re.I)), None)
            if cname is None:
                continue
            vals = t.iloc[:, -1]
            rates = {canon(k): float(v) for k, v in zip(t[cname], pd.to_numeric(vals, errors="coerce"))
                     if pd.notna(v) and 0 < v < 100}
            if len(rates) > len(best):
                best, meta["date"] = rates, str(t.columns[-1])
        if len(best) < 30:
            raise ValueError("table not parsed")
        return best, meta
    except Exception as e:  # noqa: BLE001
        meta.update(live=False, date="2026",
                    source="OECD Corporate Tax Statistics 2026 (values from course packet)",
                    note=f"Live OECD fetch failed ({type(e).__name__}); showing packet values.")
        return dict(FALLBACK_TAX), meta


@st.cache_data(ttl=1800, show_spinner=False)
def load_yields():
    meta = {"source": "Trading Economics /bonds (10-year)", "live": True, "date": "n/a", "note": ""}
    try:
        r = requests.get(TE_URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        out, dates = {}, []
        for t in pd.read_html(io.StringIO(r.text)):
            cols = [str(c) for c in t.columns]
            if "Yield" not in cols:
                continue
            for _, row in t.iterrows():
                name = next((str(v).strip() for v in row.values
                             if isinstance(v, str) and re.search(r"[A-Za-z]{3}", v)
                             and not re.fullmatch(r"[A-Za-z]{3}/\d{1,2}|\d{1,2}:\d{2}", v.strip())), None)
                y = pd.to_numeric(row["Yield"], errors="coerce")
                if name and pd.notna(y):
                    out[canon(name)] = float(y)
                    if "Date" in cols:
                        dates.append(str(row["Date"]))
        if len(out) < 10:
            raise ValueError("yield table not parsed")
        meta["date"] = max(set(dates), key=dates.count) if dates else datetime.now().strftime("%Y-%m-%d")
        return out, meta
    except Exception as e:  # noqa: BLE001
        meta.update(live=False, date="Nov 6, 2026",
                    note=f"Live fetch failed ({type(e).__name__}); showing course-packet yields.")
        return dict(FALLBACK_YIELDS), meta


# ------------------------------------------------------------------ calculations
def compute(beta_u, d, tau, erp, rf_us, s, rf_f, s_f_override=None):
    """All inputs in decimals. Returns dict with USD and foreign-currency results."""
    de = d / (1 - d)
    beta_e = beta_u * (1 + (1 - tau) * de)
    re_usd = rf_us + beta_e * erp
    rd_usd = rf_us + s
    wacc_usd = (1 - d) * re_usd + d * rd_usd * (1 - tau)
    F = (1 + rf_f) / (1 + rf_us)
    re_f = (1 + re_usd) * F - 1
    s_f = s * F if s_f_override is None else s_f_override
    rd_f = rf_f + s_f
    wacc_f = (1 - d) * re_f + d * rd_f * (1 - tau)
    return dict(de=de, beta_e=beta_e, F=F, s_f=s_f,
                usd=dict(rf=rf_us, s=s, re=re_usd, rd=rd_usd, rd_at=rd_usd * (1 - tau), wacc=wacc_usd),
                foreign=dict(rf=rf_f, s=s_f, re=re_f, rd=rd_f, rd_at=rd_f * (1 - tau), wacc=wacc_f))


def pct(x, nd=2):
    return f"{x * 100:.{nd}f}%"


# ------------------------------------------------------------------ UI
def main():
    st.set_page_config(page_title="International cost of capital", layout="wide")

    betas, beta_meta = load_betas()
    spread_auto, spread_meta = load_bbb_spread()
    taxes, tax_meta = load_tax()
    yields, yld_meta = load_yields()
    yields.setdefault(DEFAULT_COUNTRY, FALLBACK_YIELDS[DEFAULT_COUNTRY])

    sb = st.sidebar
    sb.header("Project assumptions")
    if sb.button("Refresh source data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    industries = sorted(betas["Industry"].tolist())
    idx = industries.index(DEFAULT_INDUSTRY) if DEFAULT_INDUSTRY in industries else 0
    industry = sb.selectbox("U.S. industry", industries, index=idx)
    beta_auto = float(betas.loc[betas["Industry"] == industry, "beta_u"].iloc[0])
    ov_beta = sb.checkbox("Override unlevered beta")
    beta_u = sb.number_input("Unlevered beta", value=beta_auto, step=0.01, format="%.4f",
                             disabled=not ov_beta) if ov_beta else beta_auto
    if not ov_beta:
        sb.caption(f"Damodaran unlevered beta: {beta_auto:.4f}")

    erp = sb.number_input("Annual equity risk premium (%)", value=6.5, step=0.25, min_value=0.0) / 100
    d = sb.slider("Fraction financed with debt (%)", 0, 90, 30) / 100

    countries = sorted(yields)
    country = sb.selectbox("Project country / currency", countries, index=countries.index(DEFAULT_COUNTRY))

    sb.subheader("Corporate tax rate")
    tax_basis = sb.radio("Use tax rate of", ["U.S.", "Selected country"], horizontal=True)
    tax_name = "United States" if tax_basis == "U.S." else country
    tax_auto = taxes.get(canon(tax_name))
    if tax_auto is None:
        sb.warning(f"No OECD rate found for {tax_name}; enter it manually below.")
    ov_tax = sb.checkbox("Override corporate tax rate", value=tax_auto is None)
    tax_pct = sb.number_input("Corporate tax rate (%)", value=float(tax_auto or taxes["United States"]),
                              step=0.5, min_value=0.0, max_value=60.0) if ov_tax else tax_auto
    if not ov_tax:
        sb.caption(f"OECD statutory rate, {tax_name}: {tax_auto:.2f}%")
    tau = tax_pct / 100

    sb.subheader("Yields and spreads")
    ov_us = sb.checkbox("Override U.S. 10-year yield")
    y_us = sb.number_input("U.S. 10-year yield (%)", value=float(yields["United States"]), step=0.05,
                           format="%.3f") if ov_us else yields["United States"]
    ov_f = sb.checkbox("Override selected-country 10-year yield")
    y_f_auto = yields[country]
    y_f = sb.number_input(f"{country} 10-year yield (%)", value=float(y_f_auto), step=0.05,
                          format="%.3f") if ov_f else y_f_auto
    ov_s = sb.checkbox("Override USD BBB spread")
    s_pct = sb.number_input("USD BBB spread (percentage points)", value=float(spread_auto), step=0.05,
                            format="%.2f") if ov_s else spread_auto
    ov_sf = sb.checkbox("Override foreign-currency spread")
    s_f_auto = s_pct * (1 + y_f / 100) / (1 + y_us / 100)
    s_f_pct = sb.number_input("Foreign-currency spread (percentage points)", value=float(s_f_auto),
                              step=0.05, format="%.4f", key="sf_manual") if ov_sf else None
    if not ov_sf:
        sb.caption(f"Auto: s × (1+Rf*)/(1+Rf) = {s_f_auto:.4f} pp")

    # ---- main calc
    s = s_pct / 100
    args = dict(d=d, tau=tau, erp=erp, rf_us=y_us / 100, s=s, rf_f=y_f / 100,
                s_f_override=None if s_f_pct is None else s_f_pct / 100)
    res = compute(beta_u, **args)
    U, Fx = res["usd"], res["foreign"]

    st.title("Cost of capital: USD vs. local currency")
    st.caption(f"{industry} project in {country}. Tax: {tax_name} ({tax_pct:.2f}%). "
               f"Debt share {d:.0%}, ERP {erp:.2%}.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cost of equity, USD", pct(U["re"]))
    c2.metric("WACC, USD", pct(U["wacc"]))
    c3.metric(f"Cost of equity, {country}", pct(Fx["re"]))
    c4.metric(f"WACC, {country}", pct(Fx["wacc"]))

    rows = [("Unlevered beta", f"{beta_u:.4f}", f"{beta_u:.4f}"),
            ("Relevered equity beta", f"{res['beta_e']:.4f}", f"{res['beta_e']:.4f}"),
            ("10-year government yield (risk-free proxy)", pct(U["rf"], 3), pct(Fx["rf"], 3)),
            ("Borrowing spread", pct(U["s"], 4), pct(Fx["s"], 4)),
            ("Cost of equity", pct(U["re"], 4), pct(Fx["re"], 4)),
            ("Pretax cost of debt", pct(U["rd"], 4), pct(Fx["rd"], 4)),
            ("After-tax cost of debt", pct(U["rd_at"], 4), pct(Fx["rd_at"], 4)),
            ("WACC", pct(U["wacc"], 4), pct(Fx["wacc"], 4))]
    table = pd.DataFrame(rows, columns=["Item", "USD", f"Local ({country})"]).set_index("Item")
    st.subheader("Results side by side")
    st.dataframe(table, use_container_width=True)
    st.caption(f"Currency factor F = (1+Rf*)/(1+Rf) = {res['F']:.6f}, implying expected depreciation of the "
               f"local currency vs. USD of about {pct(1 - 1 / res['F'], 2)} per year "
               f"(local cost = F × (1 + USD cost) − 1).")

    dl = table.copy()
    dl.loc["Tax rate"] = [pct(tau), pct(tau)]
    dl.loc["Equity risk premium"] = [pct(erp), pct(erp)]
    dl.loc["Debt share"] = [pct(d, 0), pct(d, 0)]
    st.download_button("Download results (CSV)", dl.to_csv().encode(), "cost_of_capital_results.csv", "text/csv")

    with st.expander("Main assumptions and formulas", expanded=False):
        st.markdown(f"""
- **Relevering:** D/E = d/(1−d) = {res['de']:.4f}; β_E = β_U [1 + (1−τ) D/E]. Debt and the tax shield have zero beta.
- **USD cost of equity:** CAPM with the U.S. 10-year yield as the risk-free proxy and the market ERP; no separate country premium.
- **Cost of debt:** government yield + BBB spread; interest is fully and immediately deductible at the same τ in both currencies.
- **Currency conversion:** equal real rates and relative PPP, so yield differences equal expected depreciation: (1+R*) = (1+R)(1+Rf*)/(1+Rf).
  The default foreign spread is s × F; overriding it changes only local-currency debt cost and WACC.
- **Currency risk:** FX betas near zero imply no separate currency risk premium.
- **Weights:** target market-value debt share, held constant. Government yields include liquidity, term and possibly sovereign risk.
""")

    # ---- all industries
    rows_all = []
    for _, r_ in betas.iterrows():
        x = compute(float(r_["beta_u"]), **args)
        rows_all.append({"Industry": r_["Industry"], "Unlevered beta": r_["beta_u"],
                         "Equity beta": x["beta_e"],
                         "Cost of equity USD (%)": x["usd"]["re"] * 100, "WACC USD (%)": x["usd"]["wacc"] * 100,
                         f"Cost of equity {country} (%)": x["foreign"]["re"] * 100,
                         f"WACC {country} (%)": x["foreign"]["wacc"] * 100})
    allind = pd.DataFrame(rows_all).sort_values("Industry")
    st.subheader("All-industry comparison")
    st.caption("Uses the current ERP, debt share, tax rate, yields and spreads; each industry's own Damodaran unlevered beta.")
    st.dataframe(allind.style.format({c: "{:.2f}" for c in allind.columns[3:]} |
                                     {"Unlevered beta": "{:.4f}", "Equity beta": "{:.4f}"}),
                 use_container_width=True, hide_index=True)
    st.download_button("Download all-industry results (CSV)", allind.to_csv(index=False).encode(),
                       "cost_of_capital_all_industries.csv", "text/csv")

    # ---- sources
    st.subheader("Data sources")
    src = pd.DataFrame([
        ("Unlevered beta", beta_meta), ("BBB spread", spread_meta),
        ("Corporate tax rates", tax_meta), ("10-year yields", yld_meta)],
        columns=["Item", "meta"])
    src["Source"] = src["meta"].map(lambda m: m["source"])
    src["Data date"] = src["meta"].map(lambda m: m["date"])
    src["Status"] = src["meta"].map(lambda m: "Live" if m["live"] else "Fallback")
    st.dataframe(src.drop(columns="meta"), use_container_width=True, hide_index=True)
    for m in (beta_meta, spread_meta, tax_meta, yld_meta):
        if m["note"]:
            st.warning(m["note"])
    st.caption(f"Page loaded {datetime.now():%Y-%m-%d %H:%M}. Use 'Refresh source data' to refetch.")


if __name__ == "__main__":
    main()
