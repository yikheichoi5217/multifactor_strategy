# -*- coding: utf-8 -*-
"""
因子预处理模块。

包含如下核心步骤：
1. 去极值（MAD 方法）：缓解极端值对横截面分布的扭曲；
2. 标准化（Z-Score）：统一不同因子的量纲；
3. 中性化（回归残差法）：剔除市值（以及可选行业）暴露。
"""

from typing import Optional

import numpy as np
import pandas as pd
import statsmodels.api as sm


def winsorize(factor_series, n_mad=5):
    """
    使用 MAD（中位数绝对偏差）方法进行去极值处理。

    参数：
        factor_series (pandas.Series): 某一日横截面的因子值序列，index 为股票代码。
        n_mad (int): 截断倍数，默认 5。边界为 median ± n_mad * MAD。

    返回：
        pandas.Series: 去极值后的因子序列。

    原理说明：
        1. 中位数 median 对异常值不敏感；
        2. MAD = median(|x - median|) 能稳健刻画离散程度；
        3. 将超过 [median - n*MAD, median + n*MAD] 的值截断到边界，
           可以降低极端样本对后续标准化和回归的干扰。
    """
    if factor_series is None or len(factor_series) == 0:
        return pd.Series(dtype=float)

    s = pd.to_numeric(factor_series, errors="coerce").copy()
    s = s.replace([np.inf, -np.inf], np.nan)

    if s.dropna().empty:
        return s

    median = s.median()
    mad = (s - median).abs().median()

    # 当 MAD 为 0 时，说明截面非常集中，不做截断直接返回
    if pd.isna(mad) or mad == 0:
        return s

    lower = median - n_mad * mad
    upper = median + n_mad * mad
    s = s.clip(lower=lower, upper=upper)
    return s


def standardize(factor_series):
    """
    对因子序列执行 Z-Score 标准化。

    参数：
        factor_series (pandas.Series): 某一日横截面的因子值序列。

    返回：
        pandas.Series: 标准化后的序列，理论上均值约为 0、标准差约为 1。

    原理说明：
        Z = (x - mean) / std。
        通过标准化消除量纲差异，使不同因子可以直接比较或加权合成。
    """
    if factor_series is None or len(factor_series) == 0:
        return pd.Series(dtype=float)

    s = pd.to_numeric(factor_series, errors="coerce").copy()
    s = s.replace([np.inf, -np.inf], np.nan)

    valid = s.dropna()
    if valid.empty:
        return s

    mean = valid.mean()
    std = valid.std()

    # 若标准差接近 0，避免除零，返回去中心化结果
    if pd.isna(std) or std == 0:
        return s - mean

    return (s - mean) / std


def neutralize(factor_df, market_cap_df, industry_df=None):
    """
    对因子矩阵做横截面中性化处理（回归残差法）。

    参数：
        factor_df (pandas.DataFrame): 原始因子矩阵，index=日期，columns=股票代码。
        market_cap_df (pandas.DataFrame): 市值矩阵，index=日期，columns=股票代码。
        industry_df (Optional[pandas.DataFrame]): 行业分类矩阵（可选），
            index=日期，columns=股票代码，值可为行业编码或行业名称。

    返回：
        pandas.DataFrame: 中性化后的因子矩阵（回归残差）。

    原理说明：
        对每个交易日做横截面回归：
            factor = a + b * log(market_cap) + 行业哑变量 + residual
        residual 即剔除市值/行业暴露后的“纯因子”部分，用于提升因子可比性。
    """
    if factor_df is None or factor_df.empty:
        return pd.DataFrame()
    if market_cap_df is None or market_cap_df.empty:
        # 无市值数据时，无法做指定中性化，返回原始因子
        return factor_df.copy()

    fac = factor_df.copy()
    mcap = market_cap_df.copy()

    # 对齐索引与列，保证逐日逐股可回归
    idx = fac.index.intersection(mcap.index)
    cols = fac.columns.intersection(mcap.columns)
    fac = fac.reindex(index=idx, columns=cols)
    mcap = mcap.reindex(index=idx, columns=cols)

    ind = None
    if industry_df is not None and not industry_df.empty:
        ind_idx = idx.intersection(industry_df.index)
        ind_cols = cols.intersection(industry_df.columns)
        idx = ind_idx
        cols = ind_cols
        fac = fac.reindex(index=idx, columns=cols)
        mcap = mcap.reindex(index=idx, columns=cols)
        ind = industry_df.reindex(index=idx, columns=cols)

    result = pd.DataFrame(index=fac.index, columns=fac.columns, dtype=float)

    for dt in fac.index:
        y = pd.to_numeric(fac.loc[dt], errors="coerce")
        mc = pd.to_numeric(mcap.loc[dt], errors="coerce")
        log_mc = np.log(mc.where(mc > 0))

        base_df = pd.DataFrame({
            "y": y,
            "log_mcap": log_mc
        })

        if ind is not None:
            ind_today = ind.loc[dt]
            # 行业哑变量，drop_first=True 避免完全共线
            dummies = pd.get_dummies(ind_today, prefix="ind", drop_first=True)
            # 将哑变量索引对齐到股票代码
            dummies = dummies.reindex(base_df.index)
            reg_df = pd.concat([base_df, dummies], axis=1)
        else:
            reg_df = base_df

        reg_df = reg_df.replace([np.inf, -np.inf], np.nan).dropna()
        if reg_df.empty or reg_df.shape[0] < 3:
            continue

        y_reg = reg_df["y"]
        x_reg = reg_df.drop(columns=["y"])
        x_reg = sm.add_constant(x_reg, has_constant="add")

        try:
            model = sm.OLS(y_reg, x_reg).fit()
            resid = model.resid
            result.loc[dt, resid.index] = resid.values
        except Exception:
            # 单日回归失败时跳过，保持 NaN，避免整体流程中断
            continue

    return result


def process_factor(raw_factor, market_cap_df=None, industry_df=None, n_mad=5):
    """
    对原始因子矩阵执行完整预处理流程。

    参数：
        raw_factor (pandas.DataFrame): 原始因子矩阵（index=日期，columns=股票代码）。
        market_cap_df (Optional[pandas.DataFrame]): 市值矩阵；提供时执行中性化。
        industry_df (Optional[pandas.DataFrame]): 行业矩阵；提供时参与行业中性化。
        n_mad (int): MAD 去极值倍数。

    返回：
        pandas.DataFrame: 处理后的因子矩阵。

    原理说明：
        对每个交易日横截面依次执行：
        1) winsorize：抑制极端值；
        2) standardize：消除量纲；
        3) neutralize（可选）：剥离市值/行业暴露。
    """
    if raw_factor is None or raw_factor.empty:
        return pd.DataFrame()

    fac = raw_factor.copy()
    fac = fac.sort_index()

    # 逐日做去极值与标准化
    processed = pd.DataFrame(index=fac.index, columns=fac.columns, dtype=float)
    for dt in fac.index:
        s = fac.loc[dt]
        s = winsorize(s, n_mad=n_mad)
        s = standardize(s)
        processed.loc[dt, s.index] = s.values

    # 若提供了“有效”市值数据，继续做中性化（全 NaN 视为无效，跳过中性化）
    if market_cap_df is not None and not market_cap_df.empty:
        mcap_num = market_cap_df.apply(pd.to_numeric, errors="coerce")
        if mcap_num.notna().sum().sum() > 0:
            processed = neutralize(processed, mcap_num, industry_df=industry_df)

    return processed
