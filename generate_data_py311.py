# -*- coding: utf-8 -*-
"""
Python 3.11+ 数据生成脚本。

用途：
1. 在高版本 Python 环境中使用 AKShare 下载数据；
2. 落地为本项目 data/*.csv

"""

from __future__ import division

import os
import time
import traceback

import akshare as ak
import baostock as bs
import pandas as pd
import requests


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

STOCK_POOL_PATH = os.path.join(DATA_DIR, "stock_pool.csv")
PRICE_DATA_PATH = os.path.join(DATA_DIR, "price_data.csv")
FINANCIAL_DATA_PATH = os.path.join(DATA_DIR, "financial_data.csv")
BENCHMARK_PATH = os.path.join(DATA_DIR, "benchmark.csv")

START_DATE = "20210101"
END_DATE = "20231231"

MAX_RETRY = 4
RETRY_SLEEP = 1.0


def ensure_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)


def format_date(date_str):
    """
    将 YYYYMMDD 转为 YYYY-MM-DD。
    """
    return "{0}-{1}-{2}".format(date_str[0:4], date_str[4:6], date_str[6:8])


def disable_env_proxy():
    """
    清理常见代理环境变量，避免代理不可达导致请求失败。
    """
    for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
        if key in os.environ:
            os.environ.pop(key, None)
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"


def disable_requests_proxy():
    """
    强制 requests 不使用系统/环境代理（包含 AKShare 内部请求）。
    """
    original_request = requests.sessions.Session.request

    def patched_request(self, method, url, **kwargs):
        self.trust_env = False
        kwargs["proxies"] = {"http": None, "https": None}
        return original_request(self, method, url, **kwargs)

    requests.sessions.Session.request = patched_request


def normalize_code(code):
    if code is None:
        return ""
    code_str = str(code).strip()
    digits = "".join([c for c in code_str if c.isdigit()])
    if len(digits) >= 6:
        return digits[-6:]
    return code_str


def call_with_retry(func, *args, **kwargs):
    """
    通用重试封装。
    """
    last_error = None
    for i in range(MAX_RETRY):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_error = e
            sleep_seconds = RETRY_SLEEP * (i + 1)
            time.sleep(sleep_seconds)
    if last_error is not None:
        raise last_error
    raise RuntimeError("未知错误")


def to_bs_code(code):
    """
    将 6 位股票代码转换为 baostock 代码格式。
    """
    symbol = normalize_code(code)
    if "." in str(code):
        return str(code).strip()
    if symbol.startswith(("5", "6", "9")):
        return "sh.{0}".format(symbol)
    return "sz.{0}".format(symbol)


def fetch_price_with_baostock(code, start_date, end_date):
    """
    使用 baostock 下载单只股票日线。
    """
    bs_code = to_bs_code(code)
    rs = bs.query_history_k_data_plus(
        bs_code,
        "date,code,open,high,low,close,volume,amount,pctChg",
        start_date=start_date,
        end_date=end_date,
        frequency="d",
        adjustflag="2"
    )
    if rs.error_code != "0":
        raise RuntimeError("baostock错误[{0}]: {1}".format(rs.error_code, rs.error_msg))

    rows = []
    while rs.error_code == "0" and rs.next():
        rows.append(rs.get_row_data())
    if len(rows) == 0:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=rs.fields)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["stock_code"] = normalize_code(code)

    for col in ["open", "high", "low", "close", "volume", "amount", "pctChg"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.rename(columns={"pctChg": "pct_chg"})
    return df.dropna(subset=["date", "close"])


def download_stock_pool():
    """
    使用 AKShare 中证指数成分股接口下载沪深300股票池。
    """
    print("下载沪深300成分股...")
    df = call_with_retry(ak.index_stock_cons_csindex, symbol="000300")
    if df is None or df.empty:
        raise ValueError("成分股下载为空。")

    code_col = None
    for col in ["成分券代码", "证券代码", "股票代码", "code"]:
        if col in df.columns:
            code_col = col
            break

    if code_col is None:
        raise ValueError("未识别成分股代码列。")

    df["stock_code"] = df[code_col].astype(str).map(normalize_code)
    df.to_csv(STOCK_POOL_PATH, index=False, encoding="utf-8-sig")

    print("成分股下载完成: {0}".format(len(df)))
    return df["stock_code"].dropna().astype(str).tolist()


def _load_existing_price_data():
    """
    读取已有 price_data.csv，用于断点续跑。

    """
    frames = []
    completed = set()

    if not os.path.exists(PRICE_DATA_PATH):
        return frames, completed

    try:
        old_df = pd.read_csv(PRICE_DATA_PATH, encoding="utf-8-sig")
        if old_df is None or old_df.empty:
            return frames, completed

        if "stock_code" not in old_df.columns or "date" not in old_df.columns:
            return frames, completed

        old_df["date"] = pd.to_datetime(old_df["date"], errors="coerce")
        old_df["stock_code"] = old_df["stock_code"].astype(str).map(normalize_code)
        old_df = old_df.dropna(subset=["date", "stock_code"])

        if old_df.empty:
            return frames, completed

        frames.append(old_df)

        start_dt = pd.to_datetime(format_date(START_DATE))
        end_dt = pd.to_datetime(format_date(END_DATE))

        coverage = old_df.groupby("stock_code")["date"].agg(["min", "max"])
        completed = set(
            coverage[
                (coverage["min"] <= start_dt) & (coverage["max"] >= end_dt)
            ].index.astype(str).tolist()
        )

        if len(completed) > 0:
            print("检测到已有 price_data.csv，已完整覆盖区间的股票数: {0}".format(len(completed)))
        else:
            print("检测到已有 price_data.csv，但未完整覆盖 {0} 至 {1}，将继续补充下载。".format(
                format_date(START_DATE), format_date(END_DATE)
            ))

    except Exception:
        pass

    return frames, completed


def _save_price_data(frames):
    """
    保存价格数据，保持原来的字段格式。
    """
    merged = pd.concat(frames, axis=0, ignore_index=True)

    if "date" in merged.columns:
        merged["date"] = pd.to_datetime(merged["date"], errors="coerce")

    if "stock_code" in merged.columns:
        merged["stock_code"] = merged["stock_code"].astype(str).map(normalize_code)

    merged = merged.dropna(subset=["date", "stock_code", "close"])
    merged = merged.drop_duplicates(subset=["date", "stock_code"], keep="last")
    merged = merged.sort_values(["date", "stock_code"]).reset_index(drop=True)

    merged.to_csv(PRICE_DATA_PATH, index=False, encoding="utf-8-sig")
    return merged


def download_price_data(stock_codes):
    print("下载股票日线...")

    frames, completed = _load_existing_price_data()

    success = 0
    total = len(stock_codes)
    failed_codes = []

    for i, code in enumerate(stock_codes):
        symbol = normalize_code(code)

        if symbol in completed:
            print("[跳过] {0} 已存在且覆盖完整区间 ({1}/{2})".format(symbol, i + 1, total))
            continue

        try:
            df = call_with_retry(
                fetch_price_with_baostock,
                symbol,
                format_date(START_DATE),
                format_date(END_DATE)
            )

            if df is None or df.empty:
                print("[空] {0} ({1}/{2})".format(symbol, i + 1, total))
                time.sleep(0.2)
                continue

            frames.append(df)
            success += 1
            completed.add(symbol)

            print("[OK] {0} ({1}/{2})".format(symbol, i + 1, total))

            # 每成功一只就落盘，避免中断丢失进度
            _save_price_data(frames)

        except Exception as e:
            print("[失败] {0}: {1}".format(symbol, e))
            failed_codes.append(symbol)

        time.sleep(0.2)

    # 第二轮补抓失败代码
    if len(failed_codes) > 0:
        print("\n开始第二轮补抓失败股票，数量: {0}".format(len(failed_codes)))

    for symbol in failed_codes:
        try:
            df = call_with_retry(
                fetch_price_with_baostock,
                symbol,
                format_date(START_DATE),
                format_date(END_DATE)
            )

            if df is None or df.empty:
                print("[二轮仍空] {0}".format(symbol))
                continue

            frames.append(df)
            success += 1
            completed.add(symbol)

            print("[二轮OK] {0}".format(symbol))

            _save_price_data(frames)

        except Exception as e:
            print("[二轮失败] {0}: {1}".format(symbol, e))

        time.sleep(0.3)

    if len(frames) == 0:
        raise ValueError("价格数据全部下载失败。")

    merged = _save_price_data(frames)
    print("价格数据下载完成: 成功 {0}/{1}，总行数 {2}".format(success, total, len(merged)))


def download_financial_data(stock_codes):
    print("下载财务摘要...")

    frames = []
    success = 0
    total = len(stock_codes)
    failed_codes = []
    completed = set()

    # 断点续跑：如果已有 financial_data.csv，则跳过已完成股票
    if os.path.exists(FINANCIAL_DATA_PATH):
        try:
            old_df = pd.read_csv(FINANCIAL_DATA_PATH, encoding="utf-8-sig")
            if "stock_code" in old_df.columns:
                old_df["stock_code"] = old_df["stock_code"].astype(str).map(normalize_code)
                completed = set(old_df["stock_code"].astype(str).tolist())
                if len(completed) > 0:
                    frames.append(old_df)
                    print("检测到已有 financial_data.csv，已完成股票数: {0}".format(len(completed)))
        except Exception:
            pass

    for i, code in enumerate(stock_codes):
        symbol = normalize_code(code)

        if symbol in completed:
            print("[跳过] {0} 已存在 ({1}/{2})".format(symbol, i + 1, total))
            continue

        try:
            df = call_with_retry(ak.stock_financial_abstract, symbol=symbol)

            if df is None or df.empty:
                print("[空] {0} ({1}/{2})".format(symbol, i + 1, total))
                time.sleep(0.2)
                continue

            if "报告期" in df.columns:
                df["report_date"] = pd.to_datetime(df["报告期"], errors="coerce")
            elif "日期" in df.columns:
                df["report_date"] = pd.to_datetime(df["日期"], errors="coerce")
            else:
                df["report_date"] = pd.NaT

            df["stock_code"] = symbol

            frames.append(df)
            success += 1
            completed.add(symbol)

            print("[OK] {0} ({1}/{2})".format(symbol, i + 1, total))

            tmp_merged = pd.concat(frames, axis=0, ignore_index=True)
            tmp_merged.to_csv(FINANCIAL_DATA_PATH, index=False, encoding="utf-8-sig")

        except Exception as e:
            print("[失败] {0}: {1}".format(symbol, e))
            failed_codes.append(symbol)

        time.sleep(0.2)

    if len(failed_codes) > 0:
        print("\n开始第二轮补抓失败财务数据，数量: {0}".format(len(failed_codes)))

    for symbol in failed_codes:
        try:
            df = call_with_retry(ak.stock_financial_abstract, symbol=symbol)

            if df is None or df.empty:
                print("[二轮仍空] {0}".format(symbol))
                continue

            if "报告期" in df.columns:
                df["report_date"] = pd.to_datetime(df["报告期"], errors="coerce")
            elif "日期" in df.columns:
                df["report_date"] = pd.to_datetime(df["日期"], errors="coerce")
            else:
                df["report_date"] = pd.NaT

            df["stock_code"] = symbol

            frames.append(df)
            success += 1
            completed.add(symbol)

            print("[二轮OK] {0}".format(symbol))

            tmp_merged = pd.concat(frames, axis=0, ignore_index=True)
            tmp_merged.to_csv(FINANCIAL_DATA_PATH, index=False, encoding="utf-8-sig")

        except Exception as e:
            print("[二轮失败] {0}: {1}".format(symbol, e))

        time.sleep(0.3)

    if len(frames) == 0:
        raise ValueError("财务数据全部下载失败。")

    merged = pd.concat(frames, axis=0, ignore_index=True)
    merged.to_csv(FINANCIAL_DATA_PATH, index=False, encoding="utf-8-sig")

    print("财务数据下载完成: 成功 {0}/{1}".format(success, total))


def download_benchmark():
    print("下载沪深300指数...")

    df = call_with_retry(
        fetch_price_with_baostock,
        "sh.000300",
        format_date(START_DATE),
        format_date(END_DATE)
    )

    if df is None or df.empty:
        raise ValueError("基准指数下载为空。")

    df = df.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)
    df.to_csv(BENCHMARK_PATH, index=False, encoding="utf-8-sig")

    print("基准下载完成: {0}".format(len(df)))


def main():
    disable_env_proxy()
    disable_requests_proxy()
    ensure_dir()

    print("数据生成区间: {0} ~ {1}".format(format_date(START_DATE), format_date(END_DATE)))

    lg = bs.login()
    if lg.error_code != "0":
        raise RuntimeError("baostock 登录失败[{0}]: {1}".format(lg.error_code, lg.error_msg))

    try:
        codes = download_stock_pool()
        download_price_data(codes)
        download_financial_data(codes)
        download_benchmark()

        print("\n全部数据已生成到 data/ 目录。")

    except Exception as e:
        print("\n数据生成失败: {0}".format(e))
        print(traceback.format_exc())

    finally:
        bs.logout()


if __name__ == "__main__":
    main()