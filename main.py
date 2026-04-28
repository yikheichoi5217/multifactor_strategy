# -*- coding: utf-8 -*-
"""
多因子选股策略主程序入口。

执行流程：
1. 检查本地数据是否存在（不自动下载）
2. 加载数据
3. 计算三个因子
4. 因子预处理（去极值、标准化、中性化）
5. 单因子有效性分析（IC、分组回测）
6. 计算综合得分
7. 选股
8. 运行回测
9. 计算绩效指标并打印
10. 绘图保存到 results/
11. 把指标写入 results/metrics.txt
"""

from __future__ import division

import os
import traceback

import numpy as np
import pandas as pd

import config
from src import data_loader
from src.backtest_engine import BacktestEngine
from src.factor_processor import process_factor
from src.factors.growth_factor import calculate_growth_factor
from src.factors.momentum_factor import calculate_momentum_factor
from src.factors.quality_factor import calculate_quality_factor
from src.performance import (
    calculate_metrics,
    plot_drawdown,
    plot_factor_grouping,
    plot_factor_ic,
    plot_monthly_returns_heatmap,
    plot_net_value
)
from src.stock_selector import composite_score, select_top_n


def _print_step(title):
    """
    打印统一格式的步骤提示。

    参数：
        title (str): 步骤标题。

    返回：
        无
    """
    print("\n========== {0} ==========".format(title))


def _to_price_matrix(price_df, value_col):
    """
    将长表行情转换为 date x stock 的宽表矩阵。

    参数：
        price_df (pandas.DataFrame): 行情长表，至少包含 date、stock_code、value_col。
        value_col (str): 指定取值列名。

    返回：
        pandas.DataFrame: 宽表矩阵（index=日期，columns=股票代码）。
    """
    if price_df is None or price_df.empty:
        return pd.DataFrame()
    required_cols = ["date", "stock_code", value_col]
    for col in required_cols:
        if col not in price_df.columns:
            return pd.DataFrame()

    df = price_df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["stock_code"] = df["stock_code"].astype(str)
    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")
    df = df.dropna(subset=["date", "stock_code", value_col])
    if df.empty:
        return pd.DataFrame()

    pivot = df.pivot_table(
        index="date",
        columns="stock_code",
        values=value_col,
        aggfunc="last"
    ).sort_index()
    return pivot


def _infer_financial_factor_matrices(financial_df):
    """
    从财务原始表中尽量识别并构建因子所需矩阵。

    参数：
        financial_df (pandas.DataFrame): 财务数据原始表（来自 stock_financial_abstract 合并）。

    返回：
        dict:
            {
                "revenue_yoy_df": ...,
                "net_profit_yoy_df": ...,
                "roe_df": ...,
                "gross_margin_df": ...
            }

    说明：
        AKShare 不同版本字段命名可能有差异，本函数通过常见关键词做“弱匹配”；
        若某项无法识别，则返回全 NaN 矩阵，保证主流程不中断。
    """
    result = {
        "revenue_yoy_df": pd.DataFrame(),
        "net_profit_yoy_df": pd.DataFrame(),
        "roe_df": pd.DataFrame(),
        "gross_margin_df": pd.DataFrame()
    }

    if financial_df is None or financial_df.empty:
        return result

    df = financial_df.copy()

    # 兼容 stock_financial_abstract 的宽表：每行是“指标”，每列是报告期(YYYYMMDD)
    indicator_col = None
    if "指标" in df.columns:
        indicator_col = "指标"
    else:
        for col in df.columns:
            if "指标" in str(col):
                indicator_col = col
                break

    date_cols = [c for c in df.columns if str(c).isdigit() and len(str(c)) == 8]
    has_wide_layout = ("stock_code" in df.columns) and (indicator_col is not None) and (len(date_cols) > 0)

    if has_wide_layout:
        use_cols = ["stock_code", indicator_col] + date_cols
        wide = df[use_cols].copy()
        wide["stock_code"] = wide["stock_code"].astype(str)
        long_df = wide.melt(
            id_vars=["stock_code", indicator_col],
            value_vars=date_cols,
            var_name="date",
            value_name="value"
        )
        long_df["date"] = pd.to_datetime(long_df["date"].astype(str), format="%Y%m%d", errors="coerce")
        long_df["indicator"] = long_df[indicator_col].astype(str)
        long_df["value"] = pd.to_numeric(long_df["value"], errors="coerce")
        long_df = long_df.dropna(subset=["date", "stock_code", "value"])

        def build_matrix_by_keywords(keywords):
            cond = pd.Series(False, index=long_df.index)
            for kw in keywords:
                cond = cond | long_df["indicator"].str.contains(kw, case=False, na=False)
            tmp = long_df.loc[cond, ["date", "stock_code", "value"]]
            if tmp.empty:
                return pd.DataFrame()
            return tmp.pivot_table(index="date", columns="stock_code", values="value", aggfunc="last").sort_index()

        rev_level = build_matrix_by_keywords(["营业总收入", "营业收入"])
        np_level = build_matrix_by_keywords(["归母净利润", "净利润"])
        result["roe_df"] = build_matrix_by_keywords(["净资产收益率", "roe"])
        result["gross_margin_df"] = build_matrix_by_keywords(["毛利率", "gross margin"])

        # 由季度口径水平值推导同比：t / t-4 - 1
        if not rev_level.empty:
            result["revenue_yoy_df"] = rev_level.sort_index().pct_change(periods=4, fill_method=None).replace([np.inf, -np.inf], np.nan)
        if not np_level.empty:
            result["net_profit_yoy_df"] = np_level.sort_index().pct_change(periods=4, fill_method=None).replace([np.inf, -np.inf], np.nan)

        return result

    # 回退：兼容长表格式（保留原逻辑）
    if "report_date" in df.columns:
        df["date"] = pd.to_datetime(df["report_date"], errors="coerce")
    elif "日期" in df.columns:
        df["date"] = pd.to_datetime(df["日期"], errors="coerce")
    elif "报告期" in df.columns:
        df["date"] = pd.to_datetime(df["报告期"], errors="coerce")
    else:
        return result

    if "stock_code" not in df.columns:
        return result

    df["stock_code"] = df["stock_code"].astype(str)
    df = df.dropna(subset=["date", "stock_code"])
    if df.empty:
        return result

    lower_map = {}
    for col in df.columns:
        lower_map[col] = str(col).lower()

    def pick_col(keywords):
        for col in df.columns:
            lc = lower_map[col]
            matched = True
            for kw in keywords:
                if kw not in lc:
                    matched = False
                    break
            if matched:
                return col
        return None

    rev_yoy_col = pick_col(["营业", "同比"]) or pick_col(["revenue", "yoy"])
    np_yoy_col = pick_col(["净利润", "同比"]) or pick_col(["profit", "yoy"])
    roe_col = pick_col(["roe"]) or pick_col(["净资产收益率"])
    gm_col = pick_col(["毛利率"]) or pick_col(["gross", "margin"])

    mapping = {
        "revenue_yoy_df": rev_yoy_col,
        "net_profit_yoy_df": np_yoy_col,
        "roe_df": roe_col,
        "gross_margin_df": gm_col
    }

    for key, col in mapping.items():
        if col is None:
            result[key] = pd.DataFrame()
            continue
        tmp = df[["date", "stock_code", col]].copy()
        tmp = tmp.rename(columns={col: "value"})
        tmp["value"] = pd.to_numeric(tmp["value"], errors="coerce")
        tmp = tmp.dropna(subset=["value"])
        if tmp.empty:
            result[key] = pd.DataFrame()
            continue
        result[key] = tmp.pivot_table(index="date", columns="stock_code", values="value", aggfunc="last").sort_index()

    return result


def _prepare_forward_return(close_df):
    """
    计算下一期（日频）收益矩阵，用于 IC 与分组测试。

    参数：
        close_df (pandas.DataFrame): 收盘价矩阵（date x stock）。

    返回：
        pandas.DataFrame: 下一期收益矩阵（date x stock）。
    """
    if close_df is None or close_df.empty:
        return pd.DataFrame()
    return close_df.shift(-1) / close_df - 1.0


def _write_metrics(metrics, path):
    """
    将绩效指标写入文本文件。

    参数：
        metrics (dict): 指标字典。
        path (str): 输出路径。

    返回：
        无
    """
    folder = os.path.dirname(path)
    if folder and (not os.path.exists(folder)):
        os.makedirs(folder)

    with open(path, "w", encoding="utf-8") as f:
        f.write("多因子选股策略绩效指标\n")
        f.write("=" * 40 + "\n")
        for k in metrics.keys():
            v = metrics[k]
            if isinstance(v, float) and (not np.isnan(v)):
                f.write("{0}: {1:.6f}\n".format(k, v))
            else:
                f.write("{0}: {1}\n".format(k, v))


def main():
    """
    主函数。

    参数：
        无

    返回：
        无
    """
    try:
        config.ensure_directories()

        _print_step("Step 1: 数据文件完整性检查（仅使用本地数据）")
        required_files = [
            config.STOCK_POOL_PATH,
            config.PRICE_DATA_PATH,
            config.FINANCIAL_DATA_PATH,
            config.BENCHMARK_PATH
        ]
        missing_files = [p for p in required_files if (not os.path.exists(p))]
        if len(missing_files) > 0:
            raise ValueError(
                "缺少必要数据文件，请先准备以下文件: {0}".format(", ".join(missing_files))
            )

        _print_step("Step 2: 加载本地数据")
        stock_pool_df = data_loader.load_stock_pool()
        price_df = data_loader.load_price_data()
        financial_df = data_loader.load_financial_data()
        benchmark_df = data_loader.load_benchmark()
        if stock_pool_df.empty:
            raise ValueError("股票池数据为空，请检查 stock_pool.csv。")
        if price_df.empty:
            raise ValueError("价格数据为空，无法继续。")

        close_df = _to_price_matrix(price_df, "close")
        if close_df.empty:
            raise ValueError("无法从价格数据构建收盘价矩阵。")

        _print_step("Step 3: 计算三大原始因子")
        fin_mats = _infer_financial_factor_matrices(financial_df)

        # 财务列可能缺失，若缺失则补 NaN 矩阵与 close_df 对齐，确保流程可运行
        base_index = close_df.index
        base_columns = close_df.columns

        def align_or_empty(df):
            if df is None or df.empty:
                return pd.DataFrame(np.nan, index=base_index, columns=base_columns)
            out = df.reindex(index=base_index, columns=base_columns)
            return out

        revenue_yoy_df = align_or_empty(fin_mats.get("revenue_yoy_df"))
        net_profit_yoy_df = align_or_empty(fin_mats.get("net_profit_yoy_df"))
        roe_df = align_or_empty(fin_mats.get("roe_df"))
        gross_margin_df = align_or_empty(fin_mats.get("gross_margin_df"))

        growth_raw = calculate_growth_factor(revenue_yoy_df, net_profit_yoy_df)
        momentum_raw = calculate_momentum_factor(close_df)
        quality_raw = calculate_quality_factor(roe_df, gross_margin_df)

        _print_step("Step 4: 因子预处理（去极值/标准化/中性化）")
        # 示例中若缺少市值矩阵，则仅执行去极值+标准化（process_factor 内部自动处理）
        market_cap_df = pd.DataFrame(np.nan, index=close_df.index, columns=close_df.columns)

        growth_factor = process_factor(growth_raw, market_cap_df=market_cap_df, industry_df=None)
        momentum_factor = process_factor(momentum_raw, market_cap_df=market_cap_df, industry_df=None)
        quality_factor = process_factor(quality_raw, market_cap_df=market_cap_df, industry_df=None)

        _print_step("Step 5: 单因子有效性分析（IC/分组）")
        fwd_ret = _prepare_forward_return(close_df)
        factor_analysis_dir = config.FACTOR_ANALYSIS_DIR

        plot_factor_ic(growth_factor, fwd_ret, os.path.join(factor_analysis_dir, "growth_ic.png"))
        plot_factor_ic(momentum_factor, fwd_ret, os.path.join(factor_analysis_dir, "momentum_ic.png"))
        plot_factor_ic(quality_factor, fwd_ret, os.path.join(factor_analysis_dir, "quality_ic.png"))

        plot_factor_grouping(
            growth_factor, fwd_ret, n_groups=5,
            save_path=os.path.join(factor_analysis_dir, "growth_grouping.png")
        )
        plot_factor_grouping(
            momentum_factor, fwd_ret, n_groups=5,
            save_path=os.path.join(factor_analysis_dir, "momentum_grouping.png")
        )
        plot_factor_grouping(
            quality_factor, fwd_ret, n_groups=5,
            save_path=os.path.join(factor_analysis_dir, "quality_grouping.png")
        )

        _print_step("Step 6: 计算综合得分")
        factor_dict = {
            "growth": growth_factor,
            "momentum": momentum_factor,
            "quality": quality_factor
        }
        score_df = composite_score(factor_dict, config.FACTOR_WEIGHTS)
        if score_df.empty:
            raise ValueError("综合得分为空，请检查因子计算结果。")

        _print_step("Step 7: 生成调仓持仓（每月末 TopN）")
        # 先取每月最后一个交易日
        monthly_rebalance_dates = score_df.groupby(pd.Grouper(freq="M")).apply(
            lambda x: x.index.max() if len(x.index) > 0 else pd.NaT
        )
        monthly_rebalance_dates = monthly_rebalance_dates.dropna().tolist()
        rebalance_score_df = score_df.reindex(monthly_rebalance_dates).dropna(how="all")

        holdings_dict = select_top_n(rebalance_score_df, n=config.TOP_N)
        if len(holdings_dict) == 0:
            raise ValueError("未生成有效持仓，请检查综合得分和调仓日期。")

        _print_step("Step 8: 执行回测")
        engine = BacktestEngine(
            initial_cash=config.INITIAL_CASH,
            commission_rate=config.COMMISSION_RATE
        )
        engine.run(price_df, holdings_dict, benchmark_df)
        results = engine.get_results()
        net_value_df = results["net_value"]

        _print_step("Step 9: 计算绩效指标")
        metrics = calculate_metrics(net_value_df, benchmark_df)
        if len(metrics) == 0:
            print("[警告] 未计算出有效绩效指标。")
        else:
            for k in metrics.keys():
                print("{0}: {1}".format(k, metrics[k]))

        _print_step("Step 10: 保存结果图表")
        plot_net_value(
            net_value_df,
            benchmark_df,
            os.path.join(config.BACKTEST_DIR, "net_value_vs_benchmark.png")
        )
        plot_drawdown(
            net_value_df,
            os.path.join(config.BACKTEST_DIR, "drawdown.png")
        )
        plot_monthly_returns_heatmap(
            net_value_df,
            os.path.join(config.BACKTEST_DIR, "monthly_returns_heatmap.png")
        )

        _print_step("Step 11: 写入指标文件")
        _write_metrics(metrics, config.METRICS_PATH)
        print("[完成] 指标已写入: {0}".format(config.METRICS_PATH))
        print("[完成] 回测流程执行结束。")

    except Exception as e:
        print("[错误] 主程序执行失败: {0}".format(e))
        print(traceback.format_exc())


if __name__ == "__main__":
    main()
