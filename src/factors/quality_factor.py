# -*- coding: utf-8 -*-
"""
质量因子计算模块。

核心逻辑：
1. 使用 ROE（净资产收益率）衡量资本回报效率；
2. 使用毛利率衡量产品与业务的盈利质量；
3. 取两者均值形成综合质量因子。
"""

import pandas as pd


def _safe_to_numeric(df):
    """
    将 DataFrame 转换为数值类型，无法转换则记为 NaN。

    参数：
        df (pandas.DataFrame): 原始数据。

    返回：
        pandas.DataFrame: 数值化后的数据。
    """
    if df is None or df.empty:
        return pd.DataFrame()
    return df.apply(pd.to_numeric, errors="coerce")


def calculate_quality_factor(roe_df, gross_margin_df):
    """
    计算综合质量因子。

    参数：
        roe_df (pandas.DataFrame): ROE 矩阵（date x stock）。
        gross_margin_df (pandas.DataFrame): 毛利率矩阵（date x stock）。

    返回：
        pandas.DataFrame: 综合质量因子矩阵（date x stock）。

    金融原理：
        - ROE 高通常说明公司在股东资本上的回报能力较强；
        - 毛利率高通常说明公司竞争壁垒或成本控制较好；
        - 二者合并可更全面刻画公司经营质量与盈利韧性。
    """
    roe_num = _safe_to_numeric(roe_df)
    gm_num = _safe_to_numeric(gross_margin_df)

    if roe_num.empty and gm_num.empty:
        return pd.DataFrame()

    idx = roe_num.index.union(gm_num.index)
    cols = roe_num.columns.union(gm_num.columns)
    roe_num = roe_num.reindex(index=idx, columns=cols)
    gm_num = gm_num.reindex(index=idx, columns=cols)

    quality_factor = (roe_num + gm_num) / 2.0
    return quality_factor
