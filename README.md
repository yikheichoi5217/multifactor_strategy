# Multi-Factor Stock Selection Strategy | A-Share Quantitative Framework

🌐 **Language**: [English](README.md) | [中文](README_CN.md)

---

## 1. Overview

This project implements a **multi-factor stock selection and backtesting framework** for the **CSI 300 (沪深300) universe** in the Chinese A-share market.

The strategy constructs a composite score based on three factor categories: **Growth, Momentum, and Quality**, and performs **monthly rebalancing** by selecting top-ranked stocks with **equal-weight allocation**.

The project provides a full pipeline including:

* Data acquisition
* Factor construction
* Factor preprocessing
* Stock selection
* Backtesting engine
* Performance evaluation
* Visualization

It is well-suited for **quantitative research, factor testing, and strategy prototyping**.

---

## 2. Key Features

* End-to-end multi-factor workflow: data → factors → preprocessing → portfolio → backtest
* Classic factor categories: Growth, Momentum, Quality
* Factor preprocessing with:

  * MAD-based outlier removal
  * Z-score normalization
  * Neutralization interface (market cap / industry)
* Daily backtesting engine with:

  * Monthly rebalancing
  * Equal-weight allocation
  * Transaction cost modeling
  * Suspension handling
  * Trade logging
* Rich outputs:

  * Net value curve
  * Drawdown curve
  * Monthly return heatmap
  * Factor IC analysis
  * Group backtest charts

---

## 3. Strategy Logic

### 3.1 Universe & Backtest Setup

* **Universe**: CSI 300 constituents
* **Period**: 2021-01-01 to 2022-12-31
* **Rebalancing**: Monthly (last trading day)
* **Portfolio Size**: Top 10 stocks
* **Weighting**: Equal-weight
* **Initial Capital**: 10,000,000
* **Transaction Cost**: 0.15% per side
* **Benchmark**: CSI 300 Index

---

### 3.2 Multi-Factor Selection Framework

The core idea:

> Single factors may be unstable or noisy, while combining multiple factors improves robustness and consistency.

Workflow:

1. Compute three factor categories
2. Apply preprocessing (outlier removal, normalization, neutralization)
3. Combine factors into a composite score
4. Select top-ranked stocks monthly
5. Construct equal-weight portfolio

---

### 3.3 Factor Definitions

| Factor Type  | Indicators                                      | Economic Meaning                     |
| ------------ | ----------------------------------------------- | ------------------------------------ |
| **Growth**   | Revenue YoY, Net Profit YoY                     | Business expansion & earnings growth |
| **Momentum** | 20-day & 60-day returns (excluding last 5 days) | Medium-term price trend              |
| **Quality**  | ROE, Gross Margin                               | Profitability & capital efficiency   |

Composite score:

```python
score = 0.33 * growth + 0.34 * momentum + 0.33 * quality
```

---

### 3.4 Factor Preprocessing

To address common issues such as outliers and scale differences:

* **Outlier Removal (MAD)**: reduces impact of extreme values
* **Z-score Normalization**: ensures comparability
* **Neutralization (OLS residuals)**: removes exposure to market cap / industry

---

## 4. Project Structure

```text
quant/
├── data/
│   ├── stock_pool.csv
│   ├── price_data.csv
│   ├── financial_data.csv
│   └── benchmark.csv
├── src/
│   ├── __init__.py
│   ├── data_loader.py
│   ├── factors/
│   │   ├── __init__.py
│   │   ├── growth_factor.py
│   │   ├── momentum_factor.py
│   │   └── quality_factor.py
│   ├── factor_processor.py
│   ├── stock_selector.py
│   ├── backtest_engine.py
│   └── performance.py
├── results/
│   ├── factor_analysis/
│   ├── backtest/
│   └── metrics.txt
├── generate_data_py311.py
├── generate_data_requirements.txt
├── config.py
├── main.py
├── README_CN.md
├── README.md
└── requirements.txt
```

### Module Description

* `config.py`: global configuration (parameters, weights, paths)
* `data_loader.py`: data loading (market, financial, benchmark)
* `factors/`: factor calculations
* `factor_processor.py`: preprocessing pipeline
* `stock_selector.py`: scoring & Top-N selection
* `backtest_engine.py`: daily simulation engine
* `performance.py`: metrics & visualization
* `main.py`: pipeline entry point

---

## 5. Environment Setup

> Requirement: Python 3.6

### 5.1 Create Environment

```bash
conda create -n quant python=3.6 -c conda-forge
conda activate quant
```

### 5.2 Install Dependencies

```bash
cd multifactor_strategy
pip install -r requirements.txt
```

---

## 6. How to Run

### 6.1 Data Preparation (Python 3.11)

Due to compatibility requirements (e.g., AKShare), run data generation under Python 3.11:

```bash
conda create --name data python=3.11
conda activate data
pip install -r generate_data_requirements.txt
```

```bash
python generate_data_py311.py
```

Generated files:

```
data/
├── stock_pool.csv
├── price_data.csv
├── financial_data.csv
└── benchmark.csv
```

---

### 6.2 Run Backtest

```bash
python main.py
```

---

## 7. Outputs

Results are stored in `results/`:

### 7.1 Performance Metrics

`results/metrics.txt`

Includes:

* Total return, annual return, volatility
* Sharpe ratio, max drawdown, Calmar ratio
* Excess return & information ratio
* Monthly win rate

---

### 7.2 Visualization

* `net_value_vs_benchmark.png`: strategy vs benchmark
* `drawdown.png`: drawdown curve
* `monthly_returns_heatmap.png`: return distribution
* `*_ic.png`: factor IC
* `*_grouping.png`: factor grouping backtest

---

## 8. Backtest Results

| Metric               | Strategy | CSI 300 |
| -------------------- | -------: | ------: |
| Total Return         |   15.94% | -34.16% |
| Annual Return        |    5.27% | -12.97% |
| Volatility           |   33.10% |       - |
| Sharpe Ratio         |     0.07 |       - |
| Max Drawdown         |  -43.42% |       - |
| Calmar Ratio         |     0.12 |       - |
| Excess Return        |   74.57% |       - |
| Excess Annual Return |   21.33% |       - |
| Information Ratio    |     0.79 |       - |
| Excess Max Drawdown  |  -31.38% |       - |
| Monthly Win Rate     |   54.29% |       - |

**Interpretation:**

Although the strategy achieved a slightly negative absolute return, it significantly outperformed the benchmark during a bearish market period, demonstrating **strong downside resilience and alpha generation capability**.

---

## 9. Disclaimer

This project is for **research, educational, and technical demonstration purposes only**.

* It does NOT constitute investment advice
* Backtest results are based on historical data and do not guarantee future performance
* Real trading involves additional risks such as slippage, liquidity constraints, and rule changes

Users should make independent decisions and bear their own investment risks.

---
