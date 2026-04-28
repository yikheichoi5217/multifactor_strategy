# -*- coding: utf-8 -*-
"""
成长因子计算模块。

核心逻辑：
1. 使用营业收入同比增长率与净利润同比增长率；
2. 对两个增长指标取均值，得到综合成长因子。
"""

import pandas as pd


def _safe_to_numeric(df):
    """
    将 DataFrame 转为数值类型，无法转换则为 NaN。

    参数：
        df (pandas.DataFrame): 原始数据。

    返回：
        pandas.DataFrame: 数值化后的 DataFrame。
    """
    if df is None or df.empty:
        return pd.DataFrame()
    return df.apply(pd.to_numeric, errors="coerce")


def calculate_growth_factor(revenue_yoy_df, net_profit_yoy_df):
    """
    计算综合成长因子。

    参数：
        revenue_yoy_df (pandas.DataFrame): 营业收入同比增速矩阵（date x stock）。
        net_profit_yoy_df (pandas.DataFrame): 净利润同比增速矩阵（date x stock）。

    返回：
        pandas.DataFrame: 综合成长因子矩阵（date x stock）。

    金融原理：
        - 收入增长反映业务扩张能力；
        - 净利润增长反映盈利增长能力；
        - 两者均值兼顾“规模增长”与“利润增长”，减少单指标噪声。
    """
    rev = _safe_to_numeric(revenue_yoy_df)
    npy = _safe_to_numeric(net_profit_yoy_df)

    if rev.empty and npy.empty:
        return pd.DataFrame()

    idx = rev.index.union(npy.index)
    cols = rev.columns.union(npy.columns)
    rev = rev.reindex(index=idx, columns=cols)
    npy = npy.reindex(index=idx, columns=cols)

    growth_factor = (rev + npy) / 2.0
    return growth_factor
