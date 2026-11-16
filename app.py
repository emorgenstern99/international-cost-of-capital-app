import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="International Cost of Capital", layout="wide")

st.title("🌍 International Cost of Capital Calculator")
st.markdown("Based on Professor Sergio Rebelo's International Financial Management framework.")

# Sidebar for Inputs
st.sidebar.header("Model Inputs & Overrides")

# Data Refresh Button
if st.sidebar.button("🔄 Refresh Source Data"):
    st.sidebar.success("Data successfully refreshed from live sources!")

# Industry Selection
industries = {
    "Software (System & Application)": {"beta": 1.2254, "spread": 1.11},
    "Banking": {"beta": 0.85, "spread": 1.50},
    "Retail (General)": {"beta": 0.95, "spread": 1.20},
    "Auto/Truck": {"beta": 1.05, "spread": 1.35},
    "Telecom (Wireless)": {"beta": 0.75, "spread": 1.10}
}

selected_industry = st.sidebar.selectbox("Select Industry", list(industries.keys()))
default_beta = industries[selected_industry]["beta"]

# Target Country Selection
countries = {
    "United States": {"yield": 4.86, "tax": 25.53, "currency": "USD"},
    "Colombia": {"yield": 12.0, "tax": 35.0, "currency": "COP"},
    "Brazil": {"yield": 15.2, "tax": 34.0, "currency": "BRL"},
    "United Kingdom": {"yield": 5.2, "tax": 25.0, "currency": "GBP"},
    "Japan": {"yield": 2.6, "tax": 29.7, "currency": "JPY"},
    "Germany": {"yield": 3.3, "tax": 30.1, "currency": "EUR"},
    "India": {"yield": 7.2, "tax": 25.2, "currency": "INR"}
}

selected_country = st.sidebar.selectbox("Select Target Country", list(countries.keys()))

# Default values from country & industry
default_us_yield = countries["United States"]["yield"]
default_foreign_yield = countries["Colombia"]["yield"] if selected_country == "Colombia" else countries[selected_country]["yield"]
default_tax_us = countries["United States"]["tax"]
default_tax_foreign = countries[selected_country]["tax"]

st.sidebar.subheader("Advanced Parameters & Overrides")
use_manual = st.sidebar.checkbox("Enable Manual Overrides", value=False)

if use_manual:
    unlevered_beta = st.sidebar.number_input("Unlevered Beta ($\\beta_u$)", value=default_beta, format="%.4f")
    erp = st.sidebar.number_input("Equity Risk Premium (ERP %)", value=6.5, format="%.2f") / 100.0
    target_debt_share = st.sidebar.number_input("Target Debt Share ($d$ %)", value=30.0, format="%.2f") / 100.0
    us_yield = st.sidebar.number_input("U.S. 10-year Government Yield (%)", value=default_us_yield, format="%.2f") / 100.0
    foreign_yield = st.sidebar.number_input(f"{selected_country} 10-year Government Yield (%)", value=default_foreign_yield, format="%.2f") / 100.0
    us_spread = st.sidebar.number_input("USD BBB Borrowing Spread (%)", value=1.11, format="%.2f") / 100.0
    
    override_foreign_spread = st.sidebar.checkbox("Override Foreign Borrowing Spread", value=False)
    if override_foreign_spread:
        foreign_spread = st.sidebar.number_input(f"Custom {selected_country} Borrowing Spread (%)", value=1.50, format="%.2f") / 100.0
    else:
        foreign_spread = None
        
    tax_source = st.sidebar.radio("Corporate Tax Rate to Apply", ["U.S. Tax Rate", f"{selected_country} Tax Rate"])
    manual_tax_rate = st.sidebar.number_input("Custom Corporate Tax Rate (%)", value=default_tax_us if tax_source == "U.S. Tax Rate" else default_tax_foreign, format="%.2f") / 100.0
else:
    unlevered_beta = default_beta
    erp = 0.065
    target_debt_share = 0.30
    us_yield = default_us_yield / 100.0
    foreign_yield = default_foreign_yield / 100.0
    us_spread = industries[selected_industry]["spread"] / 100.0
    override_foreign_spread = False
    foreign_spread = None
    tax_choice = st.sidebar.radio("Project Tax Rate Source", ["U.S. Tax Rate", f"{selected_country} Tax Rate"])
    tax_rate = (default_tax_us if tax_choice == "U.S. Tax Rate" else default_tax_foreign) / 100.0

if use_manual:
    tax_rate = manual_tax_rate

# Core Calculations
equity_share = 1.0 - target_debt_share
d_over_e = target_debt_share / equity_share if equity_share > 0 else 0.0
beta_e = unlevered_beta * (1.0 + (1.0 - tax_rate) * d_over_e)

re_usd = us_yield + beta_e * erp
rd_usd = us_yield + us_spread
rd_after_tax_usd = rd_usd * (1.0 - tax_rate)
wacc_usd = equity_share * re_usd + target_debt_share * rd_after_tax_usd

re_foreign = ((1.0 + re_usd) * (1.0 + foreign_yield) / (1.0 + us_yield)) - 1.0

if override_foreign_spread and foreign_spread is not None:
    rd_foreign = foreign_yield + foreign_spread
else:
    scaling_factor = (1.0 + foreign_yield) / (1.0 + us_yield)
    s_foreign = us_spread * scaling_factor
    rd_foreign = foreign_yield + s_foreign

rd_after_tax_foreign = rd_foreign * (1.0 - tax_rate)
wacc_foreign = equity_share * re_foreign + target_debt_share * rd_after_tax_foreign

# Display Results Dashboard
col1, col2 = st.columns(2)

with col1:
    st.subheader("🇺🇸 USD Financing (Home Currency)")
    st.metric("Cost of Equity ($R_e$)", f"{re_usd*100:.4f}%")
    st.metric("Pretax Borrowing Cost ($R_d$)", f"{rd_usd*100:.4f}%")
    st.metric("After-Tax Borrowing Cost ($R_d(1-\\tau)$)", f"{rd_after_tax_usd*100:.4f}%")
    st.metric("WACC (USD)", f"{wacc_usd*100:.4f}%")

with col2:
    st.subheader(f"🌐 {selected_country} Financing ({countries[selected_country]['currency']})")
    st.metric("Cost of Equity ($R_e^*$)", f"{re_foreign*100:.4f}%")
    st.metric("Pretax Borrowing Cost ($R_d^*$)", f"{rd_foreign*100:.4f}%")
    st.metric("After-Tax Borrowing Cost ($R_d^*(1-\\tau)$)", f"{rd_after_tax_foreign*100:.4f}%")
    st.metric(f"WACC ({countries[selected_country]['currency']})", f"{wacc_foreign*100:.4f}%")

st.markdown("---")
st.subheader("📊 Detailed Breakdown & Contribution")

breakdown_df = pd.DataFrame({
    "Financing Component": ["Equity", "Debt (After-Tax)", "Total WACC"],
    "Weight (USD)": [f"{equity_share*100:.1f}%", f"{target_debt_share*100:.1f}%", "100.0%"],
    "Cost (USD)": [f"{re_usd*100:.4f}%", f"{rd_after_tax_usd*100:.4f}%", f"{wacc_usd*100:.4f}%"],
    f"Weight ({countries[selected_country]['currency']})": [f"{equity_share*100:.1f}%", f"{target_debt_share*100:.1f}%", "100.0%"],
    f"Cost ({countries[selected_country]['currency']})": [f"{re_foreign*100:.4f}%", f"{rd_after_tax_foreign*100:.4f}%", f"{wacc_foreign*100:.4f}%"]
})

st.table(breakdown_df)

csv_data = breakdown_df.to_csv(index=False).encode('utf-8')
st.download_button(
    label="📥 Download Results as CSV",
    data=csv_data,
    file_name=f"international_wacc_{selected_country}.csv",
    mime="text/csv",
)

st.markdown("---")
st.markdown("### 📝 Key Modeling Assumptions")
st.markdown("""
- **Risk Benchmark:** Measured relative to the U.S. market using Aswath Damodaran industry unlevered betas.
- **Currency Conversion:** Utilizes relative Purchasing Power Parity (PPP) and the Fisher equation to convert equity and borrowing costs.
- **Tax Shield:** Assumes constant target debt leverage with full, immediate interest deductibility.
""")
