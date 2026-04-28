# -*- coding: utf-8 -*-
"""
数据下载与加载模块。

本模块负责两类功能：
1. 首次运行时从 AKShare 下载数据并落地到本地 CSV；
2. 每次运行时从本地 CSV 加载数据，减少重复请求。
"""

import os
import pandas as pd

import config


def _normalize_stock_code(code):
    """
    将股票代码转换为 AKShare 接口所需的 6 位代码格式。

    参数：
        code (str): 原始股票代码，可能包含市场前缀（如 sh600000、sz000001、600000.SH）。

    返回：
        str: 仅包含数字的 6 位股票代码；若无法识别则返回原始字符串。

    原理：
        AKShare 的 stock_zh_a_hist 在常见场景下需要 6 位数字代码，
        因此统一做一次清洗，提升下载成功率。
    """
    if code is None:
        return ""
    code_str = str(code).strip()
    digits = "".join([ch for ch in code_str if ch.isdigit()])
    if len(digits) >= 6:
        return digits[-6:]
    return code_str





def load_stock_pool():
    """
    从本地 CSV 加载沪深300成分股列表。

    参数：
        无

    返回：
        pandas.DataFrame: 成分股数据；若文件不存在或读取失败则返回空表。
    """
    if not os.path.exists(config.STOCK_POOL_PATH):
        print("[警告] stock_pool.csv 不存在，请先下载。")
        return pd.DataFrame()
    try:
        return pd.read_csv(config.STOCK_POOL_PATH, encoding="utf-8-sig")
    except Exception as e:
        print("[错误] 读取 stock_pool.csv 失败: {0}".format(e))
        return pd.DataFrame()


def load_price_data():
    """
    从本地 CSV 加载股票日线行情。

    参数：
        无

    返回：
        pandas.DataFrame: 价格数据；若文件不存在或读取失败则返回空表。
    """
    if not os.path.exists(config.PRICE_DATA_PATH):
        print("[警告] price_data.csv 不存在，请先下载。")
        return pd.DataFrame()
    try:
        df = pd.read_csv(config.PRICE_DATA_PATH, encoding="utf-8-sig")
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        return df
    except Exception as e:
        print("[错误] 读取 price_data.csv 失败: {0}".format(e))
        return pd.DataFrame()


def load_financial_data():
    """
    从本地 CSV 加载财务数据。

    参数：
        无

    返回：
        pandas.DataFrame: 财务数据；若文件不存在或读取失败则返回空表。
    """
    if not os.path.exists(config.FINANCIAL_DATA_PATH):
        print("[警告] financial_data.csv 不存在，请先下载。")
        return pd.DataFrame()
    try:
        df = pd.read_csv(config.FINANCIAL_DATA_PATH, encoding="utf-8-sig")
        if "report_date" in df.columns:
            df["report_date"] = pd.to_datetime(df["report_date"], errors="coerce")
        return df
    except Exception as e:
        print("[错误] 读取 financial_data.csv 失败: {0}".format(e))
        return pd.DataFrame()


def load_benchmark():
    """
    从本地 CSV 加载沪深300指数行情。

    参数：
        无

    返回：
        pandas.DataFrame: 基准指数数据；若文件不存在或读取失败则返回空表。
    """
    if not os.path.exists(config.BENCHMARK_PATH):
        print("[警告] benchmark.csv 不存在，请先下载。")
        return pd.DataFrame()
    try:
        df = pd.read_csv(config.BENCHMARK_PATH, encoding="utf-8-sig")
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        return df
    except Exception as e:
        print("[错误] 读取 benchmark.csv 失败: {0}".format(e))
        return pd.DataFrame()


def get_stock_codes_from_pool(stock_pool_df):
    """
    从成分股 DataFrame 中提取股票代码列表。

    参数：
        stock_pool_df (pandas.DataFrame): 成分股数据。

    返回：
        List[str]: 股票代码列表（6位数字格式）。

    原理：
        优先读取 stock_code 列；若不存在，则在常见代码列中自动识别并标准化。
    """
    if stock_pool_df is None or stock_pool_df.empty:
        return []

    if "stock_code" in stock_pool_df.columns:
        return stock_pool_df["stock_code"].astype(str).map(_normalize_stock_code).tolist()

    candidate_cols = ["成分券代码", "证券代码", "股票代码", "code"]
    for col in candidate_cols:
        if col in stock_pool_df.columns:
            return stock_pool_df[col].astype(str).map(_normalize_stock_code).tolist()

    print("[警告] 成分股数据中未识别到股票代码列。")
    return []
