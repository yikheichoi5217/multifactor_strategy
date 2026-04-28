# -*- coding: utf-8 -*-
"""
策略绩效分析模块。

功能包括：
1. 回测指标计算（收益、风险、超额、胜率等）；
2. 净值曲线、回撤曲线、月度收益热力图绘制；
3. 单因子 IC 时序分析；
4. 因子分组回测可视化。
"""

from __future__ import division

import os
from typing import Dict

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns


# 解决中文显示问题
plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False


def _to_net_value_series(data):
    """
    将输入统一转换为净值序列（DatetimeIndex + float）。

    参数：
        data (pandas.Series or pandas.DataFrame): 净值数据。

    返回：
        pandas.Series: 净值序列，索引为日期，值为净值。
    """
    if data is None:
        return pd.Series(dtype=float)

    if isinstance(data, pd.Series):
        s = pd.to_numeric(data, errors="coerce")
        s.index = pd.to_datetime(s.index, errors="coerce")
        s = s[~s.index.isna()].sort_index()
        return s.dropna()

    if isinstance(data, pd.DataFrame):
        df = data.copy()
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.dropna(subset=["date"])
            if "net_value" in df.columns:
                s = pd.to_numeric(df["net_value"], errors="coerce")
                s.index = df["date"]
                s = s.sort_index()
                return s.dropna()
            if "close" in df.columns:
                close = pd.to_numeric(df["close"], errors="coerce")
                close.index = df["date"]
                close = close.sort_index().dropna()
                if close.empty:
                    return pd.Series(dtype=float)
                return close / close.iloc[0]
        return pd.Series(dtype=float)

    return pd.Series(dtype=float)


def _annual_factor(index_like):
    """
    根据数据频率估计年化换算因子。

    参数：
        index_like: 日期索引。

    返回：
        int: 年化换算周期数（日频默认 252）。
    """
    if index_like is None or len(index_like) < 2:
        return 252
    return 252


def calculate_metrics(net_value, benchmark):
    """
    计算策略绩效指标。

    参数：
        net_value (pandas.Series or pandas.DataFrame): 策略净值序列。
        benchmark (pandas.Series or pandas.DataFrame): 基准净值序列或可转换数据。

    返回：
        Dict[str, float]: 指标字典，包含：
            - 累计收益率、年化收益率、年化波动率
            - 夏普比率（无风险利率 0.03）
            - 最大回撤、Calmar 比率
            - 超额累计收益、超额年化收益
            - 信息比率、超额最大回撤
            - 月度胜率（相对基准）

    金融原理：
        通过收益、波动、回撤和超额维度综合刻画策略表现，
        兼顾绝对收益能力与相对基准的稳定性。
    """
    risk_free_rate = 0.03

    strat_nv = _to_net_value_series(net_value)
    bench_nv = _to_net_value_series(benchmark)

    if strat_nv.empty:
        return {}

    # 对齐日期
    if not bench_nv.empty:
        common_idx = strat_nv.index.intersection(bench_nv.index)
        if len(common_idx) > 1:
            strat_nv = strat_nv.reindex(common_idx).dropna()
            bench_nv = bench_nv.reindex(common_idx).dropna()

    if len(strat_nv) < 2:
        return {}

    ann_factor = _annual_factor(strat_nv.index)

    strat_ret = strat_nv.pct_change().dropna()
    if strat_ret.empty:
        return {}

    # 绝对收益维度
    cumulative_return = strat_nv.iloc[-1] / strat_nv.iloc[0] - 1.0
    years = float(len(strat_ret)) / float(ann_factor)
    if years <= 0:
        annual_return = np.nan
    else:
        annual_return = (1.0 + cumulative_return) ** (1.0 / years) - 1.0

    annual_vol = strat_ret.std() * np.sqrt(ann_factor)
    sharpe = np.nan
    if annual_vol is not None and annual_vol > 0:
        sharpe = (annual_return - risk_free_rate) / annual_vol

    running_max = strat_nv.cummax()
    drawdown = strat_nv / running_max - 1.0
    max_drawdown = drawdown.min()
    calmar = np.nan
    if max_drawdown is not None and max_drawdown < 0:
        calmar = annual_return / abs(max_drawdown)

    # 相对基准维度
    excess_cum_return = np.nan
    excess_ann_return = np.nan
    information_ratio = np.nan
    excess_max_drawdown = np.nan
    monthly_win_rate = np.nan

    if not bench_nv.empty and len(bench_nv) >= 2:
        bench_ret = bench_nv.pct_change().dropna()
        aligned_idx = strat_ret.index.intersection(bench_ret.index)
        if len(aligned_idx) > 1:
            strat_r = strat_ret.reindex(aligned_idx).dropna()
            bench_r = bench_ret.reindex(aligned_idx).dropna()
            aligned_idx = strat_r.index.intersection(bench_r.index)
            strat_r = strat_r.reindex(aligned_idx)
            bench_r = bench_r.reindex(aligned_idx)

            if len(aligned_idx) > 1:
                excess_r = strat_r - bench_r
                te = excess_r.std() * np.sqrt(ann_factor)
                if te is not None and te > 0:
                    information_ratio = (excess_r.mean() * ann_factor) / te

                # 超额净值与超额回撤
                excess_nv = (1.0 + excess_r).cumprod()
                excess_cum_return = excess_nv.iloc[-1] - 1.0
                years_excess = float(len(excess_r)) / float(ann_factor)
                if years_excess > 0:
                    excess_ann_return = (1.0 + excess_cum_return) ** (1.0 / years_excess) - 1.0
                ex_running_max = excess_nv.cummax()
                ex_drawdown = excess_nv / ex_running_max - 1.0
                excess_max_drawdown = ex_drawdown.min()

                # 月度胜率（策略月收益 > 基准月收益）
                strat_monthly = strat_nv.resample("M").last().pct_change().dropna()
                bench_monthly = bench_nv.resample("M").last().pct_change().dropna()
                m_idx = strat_monthly.index.intersection(bench_monthly.index)
                if len(m_idx) > 0:
                    win = (strat_monthly.reindex(m_idx) > bench_monthly.reindex(m_idx)).sum()
                    monthly_win_rate = float(win) / float(len(m_idx))

    metrics = {
        "累计收益率": float(cumulative_return),
        "年化收益率": float(annual_return) if pd.notna(annual_return) else np.nan,
        "年化波动率": float(annual_vol) if pd.notna(annual_vol) else np.nan,
        "夏普比率": float(sharpe) if pd.notna(sharpe) else np.nan,
        "最大回撤": float(max_drawdown) if pd.notna(max_drawdown) else np.nan,
        "Calmar比率": float(calmar) if pd.notna(calmar) else np.nan,
        "超额累计收益": float(excess_cum_return) if pd.notna(excess_cum_return) else np.nan,
        "超额年化收益": float(excess_ann_return) if pd.notna(excess_ann_return) else np.nan,
        "信息比率": float(information_ratio) if pd.notna(information_ratio) else np.nan,
        "超额最大回撤": float(excess_max_drawdown) if pd.notna(excess_max_drawdown) else np.nan,
        "月度胜率": float(monthly_win_rate) if pd.notna(monthly_win_rate) else np.nan
    }
    return metrics


def plot_net_value(net_value, benchmark, save_path):
    """
    绘制策略净值与基准净值对比图。

    参数：
        net_value (pandas.Series or pandas.DataFrame): 策略净值数据。
        benchmark (pandas.Series or pandas.DataFrame): 基准净值数据。
        save_path (str): 图片保存路径。

    返回：
        无
    """
    strat_nv = _to_net_value_series(net_value)
    bench_nv = _to_net_value_series(benchmark)
    if strat_nv.empty:
        return

    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    plt.figure(figsize=(12, 6))
    plt.plot(strat_nv.index, strat_nv.values, label="策略净值", linewidth=1.8)
    if not bench_nv.empty:
        idx = strat_nv.index.intersection(bench_nv.index)
        if len(idx) > 0:
            plt.plot(idx, bench_nv.reindex(idx).values, label="基准净值(沪深300)", linewidth=1.5)
    plt.title("策略与基准净值曲线")
    plt.xlabel("日期")
    plt.ylabel("净值")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()


def plot_drawdown(net_value, save_path):
    """
    绘制策略回撤曲线。

    参数：
        net_value (pandas.Series or pandas.DataFrame): 策略净值数据。
        save_path (str): 图片保存路径。

    返回：
        无
    """
    strat_nv = _to_net_value_series(net_value)
    if strat_nv.empty:
        return

    running_max = strat_nv.cummax()
    drawdown = strat_nv / running_max - 1.0

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.figure(figsize=(12, 4.5))
    plt.fill_between(drawdown.index, drawdown.values, 0, color="tomato", alpha=0.6)
    plt.plot(drawdown.index, drawdown.values, color="red", linewidth=1.0)
    plt.title("策略回撤曲线")
    plt.xlabel("日期")
    plt.ylabel("回撤")
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()


def plot_monthly_returns_heatmap(net_value, save_path):
    """
    绘制月度收益热力图（行=年份，列=月份）。

    参数：
        net_value (pandas.Series or pandas.DataFrame): 策略净值数据。
        save_path (str): 图片保存路径。

    返回：
        无
    """
    strat_nv = _to_net_value_series(net_value)
    if strat_nv.empty:
        return

    monthly_ret = strat_nv.resample("M").last().pct_change().dropna()
    if monthly_ret.empty:
        return

    hm_df = pd.DataFrame({
        "year": monthly_ret.index.year,
        "month": monthly_ret.index.month,
        "ret": monthly_ret.values
    })
    pivot = hm_df.pivot(index="year", columns="month", values="ret")

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.figure(figsize=(12, 4 + max(1, len(pivot) * 0.3)))
    sns.heatmap(
        pivot,
        annot=True,
        fmt=".2%",
        cmap="RdYlGn",
        center=0,
        cbar_kws={"label": "月度收益率"}
    )
    plt.title("月度收益热力图")
    plt.xlabel("月份")
    plt.ylabel("年份")
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()


def plot_factor_ic(factor_df, return_df, save_path):
    """
    绘制单因子 IC 时序图。

    参数：
        factor_df (pandas.DataFrame): 因子值矩阵（date x stock）。
        return_df (pandas.DataFrame): 下一期收益矩阵（date x stock）。
        save_path (str): 图片保存路径。

    返回：
        无

    原理：
        对每个日期，计算横截面相关系数：
            IC_t = corr(factor_t, return_{t+1})
        该序列可衡量因子择股有效性与稳定性。
    """
    if factor_df is None or factor_df.empty:
        print("[诊断][IC] 跳过: factor_df 为空，未生成 {0}".format(save_path))
        return
    if return_df is None or return_df.empty:
        print("[诊断][IC] 跳过: return_df 为空，未生成 {0}".format(save_path))
        return

    fac = factor_df.copy().sort_index()
    ret = return_df.copy().sort_index()

    idx = fac.index.intersection(ret.index)
    cols = fac.columns.intersection(ret.columns)
    if len(idx) == 0 or len(cols) == 0:
        print("[诊断][IC] 跳过: 因子与收益无有效交集(idx={0}, cols={1})，未生成 {2}".format(len(idx), len(cols), save_path))
        return

    fac = fac.reindex(index=idx, columns=cols)
    ret = ret.reindex(index=idx, columns=cols)

    ic_values = []
    ic_dates = []
    total_dates = len(fac.index)
    insufficient_pair_dates = 0
    nan_ic_dates = 0
    for dt in fac.index:
        x = pd.to_numeric(fac.loc[dt], errors="coerce")
        y = pd.to_numeric(ret.loc[dt], errors="coerce")
        pair = pd.concat([x, y], axis=1).dropna()
        if pair.shape[0] < 3:
            insufficient_pair_dates += 1
            continue
        ic = pair.iloc[:, 0].corr(pair.iloc[:, 1], method="spearman")
        if pd.notna(ic):
            ic_dates.append(dt)
            ic_values.append(ic)
        else:
            nan_ic_dates += 1

    if len(ic_values) == 0:
        print(
            "[诊断][IC] 跳过: 无有效IC样本(total_dates={0}, insufficient_pair_dates={1}, nan_ic_dates={2})，未生成 {3}".format(
                total_dates, insufficient_pair_dates, nan_ic_dates, save_path
            )
        )
        return

    ic_series = pd.Series(ic_values, index=pd.to_datetime(ic_dates)).sort_index()
    cum_ic = ic_series.cumsum()

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.figure(figsize=(12, 6))
    plt.plot(ic_series.index, ic_series.values, label="IC", linewidth=1.2)
    plt.plot(cum_ic.index, cum_ic.values, label="累计IC", linewidth=1.2)
    plt.axhline(ic_series.mean(), color="orange", linestyle="--", linewidth=1, label="IC均值")
    plt.axhline(0, color="gray", linestyle=":", linewidth=1)
    plt.title("单因子IC时序图")
    plt.xlabel("日期")
    plt.ylabel("IC")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()
    print(
        "[诊断][IC] 已保存: {0} (valid_dates={1}/{2}, insufficient_pair_dates={3}, nan_ic_dates={4})".format(
            save_path, len(ic_values), total_dates, insufficient_pair_dates, nan_ic_dates
        )
    )


def plot_factor_grouping(factor_df, return_df, n_groups=5, save_path="factor_grouping.png"):
    """
    因子分组回测可视化。

    参数：
        factor_df (pandas.DataFrame): 因子值矩阵（date x stock）。
        return_df (pandas.DataFrame): 下一期收益矩阵（date x stock）。
        n_groups (int): 分组数量，默认 5。
        save_path (str): 图片保存路径。

    返回：
        无

    原理：
        每个截面按因子值从低到高分成 n 组，分别计算各组下一期等权收益，
        再累乘得到各组累计净值。若高组长期显著优于低组，说明因子有效。
    """
    if factor_df is None or factor_df.empty:
        print("[诊断][分组] 跳过: factor_df 为空，未生成 {0}".format(save_path))
        return
    if return_df is None or return_df.empty:
        print("[诊断][分组] 跳过: return_df 为空，未生成 {0}".format(save_path))
        return
    if n_groups < 2:
        print("[诊断][分组] 跳过: n_groups={0} 非法，未生成 {1}".format(n_groups, save_path))
        return

    fac = factor_df.copy().sort_index()
    ret = return_df.copy().sort_index()

    idx = fac.index.intersection(ret.index)
    cols = fac.columns.intersection(ret.columns)
    if len(idx) == 0 or len(cols) == 0:
        print("[诊断][分组] 跳过: 因子与收益无有效交集(idx={0}, cols={1})，未生成 {2}".format(len(idx), len(cols), save_path))
        return

    fac = fac.reindex(index=idx, columns=cols)
    ret = ret.reindex(index=idx, columns=cols)

    group_ret_list = []
    date_list = []
    total_dates = len(fac.index)
    insufficient_stock_dates = 0
    qcut_fail_dates = 0
    empty_group_ret_dates = 0

    for dt in fac.index:
        x = pd.to_numeric(fac.loc[dt], errors="coerce")
        y = pd.to_numeric(ret.loc[dt], errors="coerce")
        pair = pd.concat([x, y], axis=1)
        pair.columns = ["factor", "ret"]
        pair = pair.dropna()
        if pair.shape[0] < n_groups:
            insufficient_stock_dates += 1
            continue

        try:
            pair["group"] = pd.qcut(pair["factor"], q=n_groups, labels=False, duplicates="drop")
        except Exception:
            qcut_fail_dates += 1
            continue

        g_ret = pair.groupby("group")["ret"].mean()
        if g_ret.empty:
            empty_group_ret_dates += 1
            continue

        # 补齐组别索引，缺失组用 NaN
        g_ret = g_ret.reindex(range(n_groups))
        group_ret_list.append(g_ret.values)
        date_list.append(dt)

    if len(group_ret_list) == 0:
        print(
            "[诊断][分组] 跳过: 无有效分组样本(total_dates={0}, insufficient_stock_dates={1}, qcut_fail_dates={2}, empty_group_ret_dates={3})，未生成 {4}".format(
                total_dates, insufficient_stock_dates, qcut_fail_dates, empty_group_ret_dates, save_path
            )
        )
        return

    group_ret_df = pd.DataFrame(group_ret_list, index=pd.to_datetime(date_list))
    group_ret_df.columns = ["G{0}".format(i + 1) for i in range(n_groups)]
    group_nv_df = (1.0 + group_ret_df.fillna(0.0)).cumprod()

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.figure(figsize=(12, 6))
    for col in group_nv_df.columns:
        plt.plot(group_nv_df.index, group_nv_df[col], label=col, linewidth=1.2)
    plt.title("因子分组回测净值曲线")
    plt.xlabel("日期")
    plt.ylabel("累计净值")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()
    print(
        "[诊断][分组] 已保存: {0} (valid_dates={1}/{2}, insufficient_stock_dates={3}, qcut_fail_dates={4}, empty_group_ret_dates={5})".format(
            save_path, len(group_ret_list), total_dates, insufficient_stock_dates, qcut_fail_dates, empty_group_ret_dates
        )
    )
