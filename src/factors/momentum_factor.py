# -*- coding: utf-8 -*-
"""
动量因子计算模块。

核心逻辑：
1. 计算过去 20 日与过去 60 日收益率；
2. 排除最近 5 日（使用 t-25 到 t-5、t-65 到 t-5）以减弱短期反转干扰；
3. 对两个期限收益率取均值作为综合动量因子。
"""

import pandas as pd


def calculate_momentum_factor(close_price_df):
    """
    计算综合动量因子。

    参数：
        close_price_df (pandas.DataFrame): 收盘价矩阵（index=日期，columns=股票代码）。

    返回：
        pandas.DataFrame: 动量因子矩阵（index=日期，columns=股票代码）。

    金融原理：
        - 中期趋势具有一定延续性，过去表现好的资产在短期内可能继续较强；
        - 但最近几日常出现反转，因此排除最近 5 个交易日可提升稳健性。
    """
    if close_price_df is None or close_price_df.empty:
        return pd.DataFrame()

    close_df = close_price_df.apply(pd.to_numeric, errors="coerce").sort_index()

    # 20日动量（排除最近5天）：P(t-5)/P(t-25) - 1
    ret_20_ex5 = close_df.shift(5) / close_df.shift(25) - 1.0

    # 60日动量（排除最近5天）：P(t-5)/P(t-65) - 1
    ret_60_ex5 = close_df.shift(5) / close_df.shift(65) - 1.0

    momentum_factor = (ret_20_ex5 + ret_60_ex5) / 2.0
    return momentum_factor
