# -*- coding: utf-8 -*-
"""
项目全局配置文件

功能：
1. 统一管理回测参数（时间区间、调仓频率、持仓数、交易成本、初始资金等）
2. 统一管理因子权重
3. 统一管理项目内所有相对路径（通过 os.path.join 构建）

说明：
- 所有路径均为相对路径（基于本文件所在目录）
- 兼容 Python 3.6
"""

import os

# ==============================
# 回测基础参数
# ==============================
START_DATE = "2021-01-01"
END_DATE = "2023-12-31"

# 调仓频率：月度（每月最后一个交易日）
REBALANCE_FREQ = "M"

# 持仓股票数量
TOP_N = 10

# 单边交易成本（千分之1.5）
COMMISSION_RATE = 0.0015

# 初始资金
INITIAL_CASH = 10000000.0

# 无风险利率（用于夏普比率）
RISK_FREE_RATE = 0.03

# ==============================
# 因子权重配置
# ==============================
FACTOR_WEIGHTS = {
    "growth": 0.33,
    "momentum": 0.34,
    "quality": 0.33
}

# ==============================
# 路径配置
# ==============================
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")

# 数据文件路径
STOCK_POOL_PATH = os.path.join(DATA_DIR, "stock_pool.csv")
PRICE_DATA_PATH = os.path.join(DATA_DIR, "price_data.csv")
FINANCIAL_DATA_PATH = os.path.join(DATA_DIR, "financial_data.csv")
BENCHMARK_PATH = os.path.join(DATA_DIR, "benchmark.csv")

# 结果路径
FACTOR_ANALYSIS_DIR = os.path.join(RESULTS_DIR, "factor_analysis")
BACKTEST_DIR = os.path.join(RESULTS_DIR, "backtest")
METRICS_PATH = os.path.join(RESULTS_DIR, "metrics.txt")


def ensure_directories():
    """
        使用 os.path.exists 判断目录是否存在，
        不存在时通过 os.makedirs 递归创建目录，避免后续文件写入报错。
    """
    dirs = [
        DATA_DIR,
        RESULTS_DIR,
        FACTOR_ANALYSIS_DIR,
        BACKTEST_DIR
    ]
    for directory in dirs:
        if not os.path.exists(directory):
            os.makedirs(directory)
