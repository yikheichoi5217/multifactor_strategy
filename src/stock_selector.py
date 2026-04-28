# -*- coding: utf-8 -*-
"""
选股引擎模块。

核心功能：
1. 将多个因子按权重合成为综合得分；
2. 在每个调仓日选出得分最高的 Top N 股票。
"""

from typing import Dict, List

import pandas as pd


def composite_score(factor_dict, weights):
    """
    计算多因子综合得分。

    参数：
        factor_dict (Dict[str, pandas.DataFrame]):
            因子字典，key 为因子名，value 为因子矩阵（index=日期，columns=股票代码）。
        weights (Dict[str, float]):
            因子权重字典，key 为因子名，value 为权重。

    返回：
        pandas.DataFrame:
            综合得分矩阵（index=日期，columns=股票代码）。

    原理：
        对每个交易日横截面执行加权求和：
            score = Σ(weight_i * factor_i)
        因子应在外部先完成方向统一与标准化，确保可直接线性合成。
    """
    if factor_dict is None or len(factor_dict) == 0:
        return pd.DataFrame()

    # 仅使用同时存在于 factor_dict 与 weights 的因子
    valid_factor_names = [name for name in factor_dict.keys() if name in weights]
    if len(valid_factor_names) == 0:
        return pd.DataFrame()

    # 统一对齐 index 和 columns（取并集）
    union_index = None
    union_columns = None
    for name in valid_factor_names:
        factor_df = factor_dict[name]
        if factor_df is None or factor_df.empty:
            continue
        if union_index is None:
            union_index = factor_df.index
            union_columns = factor_df.columns
        else:
            union_index = union_index.union(factor_df.index)
            union_columns = union_columns.union(factor_df.columns)

    if union_index is None or union_columns is None:
        return pd.DataFrame()

    score_df = pd.DataFrame(0.0, index=union_index, columns=union_columns)
    total_weight = 0.0

    for name in valid_factor_names:
        factor_df = factor_dict[name]
        if factor_df is None or factor_df.empty:
            continue
        w = float(weights.get(name, 0.0))
        if w == 0.0:
            continue

        aligned = factor_df.reindex(index=union_index, columns=union_columns)
        aligned = aligned.apply(pd.to_numeric, errors="coerce")
        score_df = score_df + aligned.fillna(0.0) * w
        total_weight += w

    # 防止传入权重总和异常，做一次归一化
    if total_weight > 0:
        score_df = score_df / total_weight

    # 若某截面全部为空，保留 NaN 语义更合理
    all_nan_mask = score_df.isna().all(axis=1)
    if all_nan_mask.any():
        score_df.loc[all_nan_mask, :] = pd.NA

    return score_df.sort_index()


def select_top_n(score_df, n=10):
    """
    在每个调仓日选择综合得分最高的 N 只股票。

    参数：
        score_df (pandas.DataFrame):
            综合得分矩阵，index=调仓日期，columns=股票代码，values=综合得分。
        n (int):
            每个调仓日选股数量，默认 10。

    返回：
        Dict[pandas.Timestamp, List[str]]:
            选股结果字典，格式为 {date: [stock_code1, stock_code2, ...]}。

    原理：
        每个日期截面按分数从高到低排序，取前 N 名。
        为避免异常数据影响，先剔除 NaN，再执行排名。
    """
    result = {}
    if score_df is None or score_df.empty:
        return result

    if n <= 0:
        return result

    sorted_score = score_df.sort_index()
    for dt in sorted_score.index:
        s = pd.to_numeric(sorted_score.loc[dt], errors="coerce").dropna()
        if s.empty:
            result[dt] = []
            continue

        top_codes = s.sort_values(ascending=False).head(n).index.astype(str).tolist()
        result[dt] = top_codes

    return result
