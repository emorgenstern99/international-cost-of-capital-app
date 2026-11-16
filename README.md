# International Cost of Capital App

Streamlit app comparing a project's cost of equity, cost of debt and WACC in USD and in the currency of any selected country.

## Run
```
pip install -r requirements.txt
streamlit run app.py
```
Deploy on Streamlit Community Cloud: push `app.py`, `requirements.txt`, `README.md` to GitHub, then choose the repo and `app.py`.

## Data (with refresh button)
| Input | Source |
|---|---|
| Industry unlevered beta | Damodaran `betas.xls` (Industry Averages) |
| BBB (Baa2) USD spread | Damodaran `ratings.html` (large non-financial firms) |
| Corporate tax rates | OECD Corporate Tax Statistics (falls back to the 2026 course-packet table if the live page cannot be parsed) |
| 10-year government yields | Trading Economics `/bonds` (falls back to course-packet yields) |

Sources, data dates and live/fallback status are shown at the bottom of the app.

## Method
- D/E = d/(1-d); beta_E = beta_U [1 + (1-tau) D/E]
- Re(USD) = Rf_US + beta_E x ERP; Rd = Rf_US + s; WACC = (1-d) Re + d Rd (1-tau)
- F = (1+Rf*)/(1+Rf); Re* = (1+Re) F - 1; default s* = s F, Rd* = Rf* + s*
- Same tax rate (U.S. or selected country), debt share and ERP in both currencies.

## Defaults
Software (System & Application), United States, U.S. tax rate, ERP 6.5%, debt 30%.

## Overrides
Unlevered beta, tax rate, USD spread, both countries' yields, and foreign-currency spread (when off, shows the auto value s x F).

## Checks
Equal yields give equal USD/local results; d = 0 gives WACC = cost of equity; overriding the foreign spread leaves USD unchanged.

## Limitations
U.S. market as risk benchmark, no country risk premium, CAPM only, fully usable interest deductions, government yields as risk-free proxies.
