# international-cost-of-capital-app
Streamlit app that compares a project's cost of equity and WACC in USD and the currency of any selected country.

Developed for coursework (Professor Sergio Rebelo).

Features

Computes Cost of Equity, Pretax/After-Tax Borrowing Cost, and WACC in both USD and foreign target currencies.

Integrates data sources (Damodaran betas & spreads, OECD tax rates, Trading Economics government bond yields).

Interactive parameter sliders/inputs for Equity Risk Premium, Target Debt Share, and manual overrides.

Side-by-side comparison and downloadable CSV results.

Running Locally

Install dependencies: pip install -r requirements.txt

Run Streamlit app: streamlit run app.py
