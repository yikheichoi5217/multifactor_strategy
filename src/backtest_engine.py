# -*- coding: utf-8 -*-
"""
回测引擎模块。

实现按日推进的股票组合回测，支持：
1. 月度调仓（由外部传入调仓日持仓列表）；
2. 等权配置；
3. 双边交易成本；
4. 停牌不交易（无当日价格时沿用上一可用价格估值）；
5. 完整记录每日净值、现金、持仓与交易日志。
"""

from __future__ import division

from typing import Dict, List

import numpy as np
import pandas as pd


class BacktestEngine(object):
    """
    多因子选股策略回测引擎。
    """

    def __init__(self, initial_cash, commission_rate):
        """
        初始化回测引擎。

        参数：
            initial_cash (float): 初始资金。
            commission_rate (float): 单边交易费率（买入和卖出都收取）。

        返回：
            无

        说明：
            - cash: 当前可用现金
            - positions: 当前持仓股数，格式 {stock_code: shares}
            - last_prices: 最近可用价格（用于停牌估值）
            - records: 每日回测记录
            - trade_logs: 交易日志
        """
        self.initial_cash = float(initial_cash)
        self.commission_rate = float(commission_rate)

        self.cash = float(initial_cash)
        self.positions = {}
        self.last_prices = {}

        self.records = []
        self.trade_logs = []

    @staticmethod
    def _build_price_table(price_data):
        """
        将原始长表行情转换为宽表价格矩阵（date x stock）。

        参数：
            price_data (pandas.DataFrame): 原始价格数据，至少包含 date、stock_code、close 列。

        返回：
            pandas.DataFrame: 收盘价矩阵，index=日期，columns=股票代码。
        """
        if price_data is None or price_data.empty:
            return pd.DataFrame()

        required_cols = ["date", "stock_code", "close"]
        for col in required_cols:
            if col not in price_data.columns:
                return pd.DataFrame()

        df = price_data.copy()
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["stock_code"] = df["stock_code"].astype(str)
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = df.dropna(subset=["date", "stock_code", "close"])

        if df.empty:
            return pd.DataFrame()

        price_table = df.pivot_table(
            index="date",
            columns="stock_code",
            values="close",
            aggfunc="last"
        ).sort_index()
        return price_table

    @staticmethod
    def _normalize_holdings_dict(holdings_dict):
        """
        标准化调仓字典的日期索引。

        参数：
            holdings_dict (Dict): 原始调仓字典，key 可为字符串或时间类型。

        返回：
            Dict[pandas.Timestamp, List[str]]: 标准化后的调仓字典。
        """
        result = {}
        if holdings_dict is None:
            return result

        for k, v in holdings_dict.items():
            dt = pd.to_datetime(k, errors="coerce")
            if pd.isna(dt):
                continue
            stocks = []
            if v is not None:
                stocks = [str(x) for x in v]
            result[dt] = stocks
        return result

    def _get_valuation_price(self, stock_code, current_date, price_table):
        """
        获取某股票在当前日期的估值价格。

        参数：
            stock_code (str): 股票代码。
            current_date (pandas.Timestamp): 当前日期。
            price_table (pandas.DataFrame): 收盘价宽表。

        返回：
            float or None: 可用价格；若无可用价格返回 None。

        说明：
            - 若当日有价格，使用当日价格并更新 last_prices；
            - 若当日无价格（可能停牌），使用 last_prices 中的上次可用价格；
            - 若历史上从未出现有效价格，则返回 None。
        """
        px = None
        if stock_code in price_table.columns and current_date in price_table.index:
            px = price_table.at[current_date, stock_code]
            if pd.notna(px):
                px = float(px)
                self.last_prices[stock_code] = px
                return px

        # 当日无价，使用上一可用价格估值
        if stock_code in self.last_prices:
            return float(self.last_prices[stock_code])
        return None

    def _record_trade(self, trade_date, stock_code, side, shares, price, amount, commission):
        """
        记录一笔交易日志。

        参数：
            trade_date (pandas.Timestamp): 交易日期。
            stock_code (str): 股票代码。
            side (str): BUY 或 SELL。
            shares (float): 成交股数。
            price (float): 成交价格。
            amount (float): 成交金额（不含手续费）。
            commission (float): 手续费金额。

        返回：
            无
        """
        self.trade_logs.append({
            "date": trade_date,
            "stock_code": stock_code,
            "side": side,
            "shares": float(shares),
            "price": float(price),
            "amount": float(amount),
            "commission": float(commission)
        })

    def _rebalance(self, current_date, target_stocks, price_table):
        """
        在调仓日执行组合调仓。

        参数：
            current_date (pandas.Timestamp): 调仓日期。
            target_stocks (List[str]): 新目标持仓股票列表。
            price_table (pandas.DataFrame): 收盘价宽表。

        返回：
            无

        调仓逻辑：
            1. 先卖出不在新组合中的股票（若当日无价则视为停牌，不交易）；
            2. 再按等权目标买入目标股票；
            3. 当日无价的股票不交易，但可按上一价格估值持有。
        """
        target_set = set([str(s) for s in target_stocks if s is not None])
        current_set = set(self.positions.keys())

        # 1) 卖出不再持有的股票
        to_sell = list(current_set - target_set)
        for code in to_sell:
            shares = float(self.positions.get(code, 0.0))
            if shares <= 0:
                continue

            px = self._get_valuation_price(code, current_date, price_table)
            # 停牌（无当日价）不交易
            if code not in price_table.columns or pd.isna(
                price_table.at[current_date, code] if current_date in price_table.index else np.nan
            ):
                continue
            if px is None or px <= 0:
                continue

            amount = shares * px
            commission = amount * self.commission_rate
            self.cash += (amount - commission)
            self.positions.pop(code, None)
            self._record_trade(current_date, code, "SELL", shares, px, amount, commission)

        # 2) 计算总资产，用于目标等权
        portfolio_value = 0.0
        for code, shares in self.positions.items():
            px = self._get_valuation_price(code, current_date, price_table)
            if px is not None and px > 0:
                portfolio_value += float(shares) * px
        total_asset = self.cash + portfolio_value

        if len(target_set) == 0:
            return

        target_each_value = total_asset / float(len(target_set))

        # 3) 对目标股票逐只调整仓位（先算差额，再买卖）
        for code in target_set:
            px_today = None
            has_today_price = False
            if code in price_table.columns and current_date in price_table.index:
                px_today = price_table.at[current_date, code]
                has_today_price = pd.notna(px_today)

            px = self._get_valuation_price(code, current_date, price_table)
            # 无估值价格或当日停牌都不交易
            if px is None or px <= 0 or (not has_today_price):
                continue

            current_shares = float(self.positions.get(code, 0.0))
            current_value = current_shares * px
            diff_value = target_each_value - current_value

            # 需要买入
            if diff_value > 0:
                # 考虑手续费后的最大可买金额
                max_buy_amount = self.cash / (1.0 + self.commission_rate)
                buy_amount = min(diff_value, max_buy_amount)
                if buy_amount <= 0:
                    continue
                buy_shares = buy_amount / px
                commission = buy_amount * self.commission_rate
                self.cash -= (buy_amount + commission)
                self.positions[code] = current_shares + buy_shares
                self._record_trade(current_date, code, "BUY", buy_shares, px, buy_amount, commission)

            # 需要卖出
            elif diff_value < 0:
                sell_amount_target = -diff_value
                max_sell_amount = current_shares * px
                sell_amount = min(sell_amount_target, max_sell_amount)
                if sell_amount <= 0:
                    continue
                sell_shares = sell_amount / px
                commission = sell_amount * self.commission_rate
                self.cash += (sell_amount - commission)
                new_shares = current_shares - sell_shares
                if new_shares <= 1e-12:
                    self.positions.pop(code, None)
                else:
                    self.positions[code] = new_shares
                self._record_trade(current_date, code, "SELL", sell_shares, px, sell_amount, commission)

    def _mark_to_market(self, current_date, price_table):
        """
        按当前可用价格对组合进行盯市估值。

        参数：
            current_date (pandas.Timestamp): 当前日期。
            price_table (pandas.DataFrame): 收盘价宽表。

        返回：
            tuple: (portfolio_value, total_asset)
                - portfolio_value: 持仓市值
                - total_asset: 总资产（现金 + 持仓市值）
        """
        portfolio_value = 0.0
        for code, shares in self.positions.items():
            px = self._get_valuation_price(code, current_date, price_table)
            if px is None or px <= 0:
                continue
            portfolio_value += float(shares) * px
        total_asset = self.cash + portfolio_value
        return portfolio_value, total_asset

    def run(self, price_data, holdings_dict, benchmark):
        """
        运行回测主流程。

        参数：
            price_data (pandas.DataFrame): 股票价格数据（长表或可转换为 date x stock）。
            holdings_dict (Dict[pandas.Timestamp, List[str]]): 调仓日目标持仓字典。
            benchmark (pandas.DataFrame): 基准指数数据（本函数中主要用于对齐日期范围，可为空）。

        返回：
            无

        执行流程：
            1. 构建价格矩阵；
            2. 按交易日推进；
            3. 调仓日执行调仓，非调仓日仅估值；
            4. 记录每日净值、现金、持仓数量。
        """
        price_table = self._build_price_table(price_data)
        if price_table.empty:
            raise ValueError("price_data 无法构建有效价格矩阵，请检查数据列（date/stock_code/close）。")

        holdings_norm = self._normalize_holdings_dict(holdings_dict)
        rebalance_dates = set(holdings_norm.keys())

        # 可选：与 benchmark 日期做交集，以便结果可比
        trading_dates = price_table.index
        if benchmark is not None and isinstance(benchmark, pd.DataFrame) and (not benchmark.empty):
            if "date" in benchmark.columns:
                bench_dates = pd.to_datetime(benchmark["date"], errors="coerce").dropna().unique()
                bench_dates = pd.DatetimeIndex(bench_dates)
                common_dates = trading_dates.intersection(bench_dates)
                if len(common_dates) > 0:
                    trading_dates = common_dates

        for dt in trading_dates:
            # 调仓日执行交易
            if dt in rebalance_dates:
                target = holdings_norm.get(dt, [])
                self._rebalance(dt, target, price_table)

            # 每日估值
            portfolio_value, total_asset = self._mark_to_market(dt, price_table)
            net_value = total_asset / self.initial_cash if self.initial_cash > 0 else np.nan

            self.records.append({
                "date": dt,
                "cash": float(self.cash),
                "portfolio_value": float(portfolio_value),
                "total_asset": float(total_asset),
                "net_value": float(net_value),
                "positions_count": int(len(self.positions))
            })

    def get_results(self):
        """
        获取回测结果。

        参数：
            无

        返回：
            dict:
                {
                    "daily_records": 每日记录 DataFrame,
                    "net_value": 净值序列 DataFrame(date, net_value),
                    "trade_logs": 交易日志 DataFrame
                }
        """
        daily_records = pd.DataFrame(self.records)
        if not daily_records.empty and "date" in daily_records.columns:
            daily_records = daily_records.sort_values("date").reset_index(drop=True)

        if daily_records.empty:
            net_value_df = pd.DataFrame(columns=["date", "net_value"])
        else:
            net_value_df = daily_records[["date", "net_value"]].copy()

        trade_logs_df = pd.DataFrame(self.trade_logs)
        if not trade_logs_df.empty and "date" in trade_logs_df.columns:
            trade_logs_df = trade_logs_df.sort_values("date").reset_index(drop=True)

        return {
            "daily_records": daily_records,
            "net_value": net_value_df,
            "trade_logs": trade_logs_df
        }
