"""Stock market analysis pipeline for Korean equities.

This module is designed to run inside Google Colab and automates
post-market analysis at 15:30 KST, producing a summary of the trading day
and recommending candidates for the next session.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

# External packages expected in Colab:
#   FinanceDataReader, pykrx, ta, investpy
import FinanceDataReader as fdr
import investpy
from pykrx import stock
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands


KOSPI_INDEX_TICKER = "1001"
KOSDAQ_INDEX_TICKER = "2001"


@dataclass
class MarketOverview:
    as_of: date
    kospi_close: float
    kospi_change_pct: float
    kosdaq_close: float
    kosdaq_change_pct: float
    sector_performance: pd.DataFrame
    strong_stocks: pd.DataFrame
    supply_demand: pd.DataFrame


@dataclass
class EconomicOutlook:
    events: pd.DataFrame
    us_index_outlook: pd.DataFrame


@dataclass
class Recommendation:
    ticker: str
    name: str
    open_price: float
    close_price: float
    change_pct: float
    recommendation_reason: str
    key_issues: str


def _krx_business_day(target: date) -> date:
    """Return the most recent KRX trading day on or before ``target``."""
    current = target
    while True:
        try:
            df = stock.get_market_ohlcv_by_ticker(current.strftime("%Y%m%d"))
        except ValueError:
            df = pd.DataFrame()
        if not df.empty:
            return current
        current -= timedelta(days=1)


def _infer_quarter_ends(latest: date, quarters: int = 4) -> List[date]:
    """Infer the latest ``quarters`` quarter-end dates on or before ``latest``."""
    result: List[date] = []
    current = latest
    while len(result) < quarters:
        quarter_end_month = ((current.month - 1) // 3 + 1) * 3
        quarter_end = date(current.year, quarter_end_month, 1)
        # go to last day of quarter
        next_month = quarter_end.month % 12 + 1
        next_year = quarter_end.year + (quarter_end.month // 12)
        first_of_next = date(next_year, next_month, 1)
        quarter_end = first_of_next - timedelta(days=1)
        if quarter_end <= latest and quarter_end not in result:
            result.append(quarter_end)
        current = quarter_end - timedelta(days=1)
    return sorted(result)


def get_market_overview(as_of: Optional[date] = None) -> MarketOverview:
    if as_of is None:
        as_of = _krx_business_day(date.today())
    latest_str = as_of.strftime("%Y%m%d")

    kospi_df = stock.get_index_ohlcv_by_date(latest_str, latest_str, KOSPI_INDEX_TICKER)
    kosdaq_df = stock.get_index_ohlcv_by_date(latest_str, latest_str, KOSDAQ_INDEX_TICKER)

    kospi_close = float(kospi_df["종가"].iloc[0])
    kospi_change_pct = float(kospi_df["등락률"].iloc[0])
    kosdaq_close = float(kosdaq_df["종가"].iloc[0])
    kosdaq_change_pct = float(kosdaq_df["등락률"].iloc[0])

    sector_perf = _compute_sector_performance(as_of)
    strong_stocks = _strong_stocks_from_sector(sector_perf, as_of, top_n=5)
    supply_demand = _supply_demand_snapshot(as_of, top_n=10)

    return MarketOverview(
        as_of=as_of,
        kospi_close=kospi_close,
        kospi_change_pct=kospi_change_pct,
        kosdaq_close=kosdaq_close,
        kosdaq_change_pct=kosdaq_change_pct,
        sector_performance=sector_perf,
        strong_stocks=strong_stocks,
        supply_demand=supply_demand,
    )


def _compute_sector_performance(as_of: date) -> pd.DataFrame:
    listings = fdr.StockListing("KRX")
    listings = listings.dropna(subset=["Sector"])
    ticker_map = listings.set_index("Symbol")["Sector"].to_dict()

    date_str = as_of.strftime("%Y%m%d")
    price_df = stock.get_market_ohlcv_by_ticker(date_str)
    price_df = price_df.assign(Sector=price_df.index.map(ticker_map))
    price_df = price_df.dropna(subset=["Sector"])
    price_df["등락률"] = price_df["등락률"].astype(float)
    if price_df.empty:
        return pd.DataFrame(columns=["avg_pct_change", "symbols"])

    sector_perf = (
        price_df.groupby("Sector")["등락률"].agg(["mean", "count"])
        .rename(columns={"mean": "avg_pct_change", "count": "symbols"})
        .sort_values("avg_pct_change", ascending=False)
    )
    sector_perf.index.name = "Sector"
    return sector_perf


def _strong_stocks_from_sector(
    sector_perf: pd.DataFrame, as_of: date, top_n: int = 5
) -> pd.DataFrame:
    top_sectors = sector_perf.head(3).index.tolist()
    if not top_sectors:
        return pd.DataFrame(columns=["종목명", "등락률", "거래대금"])
    listings = fdr.StockListing("KRX")
    top_symbols = listings[listings["Sector"].isin(top_sectors)]["Symbol"].tolist()

    price_df = stock.get_market_ohlcv_by_ticker(as_of.strftime("%Y%m%d"))
    price_df = price_df.loc[price_df.index.intersection(top_symbols)].copy()
    price_df["등락률"] = price_df["등락률"].astype(float)
    if price_df.empty:
        return pd.DataFrame(columns=["종목명", "등락률", "거래대금"])
    price_df = price_df.sort_values("등락률", ascending=False).head(top_n)
    names = {symbol: stock.get_market_ticker_name(symbol) for symbol in price_df.index}
    price_df.insert(0, "종목명", price_df.index.map(names))
    return price_df[["종목명", "등락률", "거래대금"]]


def _supply_demand_snapshot(as_of: date, top_n: int = 10) -> pd.DataFrame:
    prev = as_of - timedelta(days=4)
    df = stock.get_market_trading_value_by_investor(
        prev.strftime("%Y%m%d"),
        as_of.strftime("%Y%m%d"),
        market="ALL",
    )
    # Aggregate net buying for foreigners and institutions
    available_cols = [col for col in ["외국인", "기관합계"] if col in df.columns]
    if not available_cols:
        return pd.DataFrame()
    df = df[available_cols].groupby(level=1).sum()
    if "외국인" not in df.columns:
        df["외국인"] = 0
    if "기관합계" not in df.columns:
        df["기관합계"] = 0
    df["합산"] = df["외국인"] + df["기관합계"]
    df = df.sort_values("합산", ascending=False).head(top_n)
    df.insert(0, "종목명", df.index.map(stock.get_market_ticker_name))
    return df


def get_economic_outlook(as_of: Optional[date] = None) -> EconomicOutlook:
    if as_of is None:
        as_of = _krx_business_day(date.today())
    next_day = as_of + timedelta(days=1)

    events = _fetch_economic_calendar(next_day)
    us_outlook = _fetch_us_index_outlook(as_of)
    return EconomicOutlook(events=events, us_index_outlook=us_outlook)


def _fetch_economic_calendar(target_day: date) -> pd.DataFrame:
    try:
        calendar = investpy.news.economic_calendar(time_zone="GMT+9")
    except Exception:
        return pd.DataFrame()
    calendar["date"] = pd.to_datetime(calendar["date"]).dt.date
    return calendar[calendar["date"] == target_day][
        ["date", "time", "country", "event", "importance"]
    ]


def _fetch_us_index_outlook(as_of: date) -> pd.DataFrame:
    start = as_of - timedelta(days=10)
    end = as_of
    indices = {"^GSPC": "S&P 500", "^DJI": "Dow Jones", "^IXIC": "Nasdaq"}
    result = []
    for ticker, name in indices.items():
        try:
            series = fdr.DataReader(ticker, start=start, end=end)
        except Exception:
            continue
        if series.empty:
            continue
        last_row = series.iloc[-1]
        if "Change" in series.columns:
            change_pct = float(last_row["Change"]) * 100
        else:
            prev_close = series.iloc[-2]["Close"] if len(series) > 1 else last_row["Close"]
            change_pct = (float(last_row["Close"]) / float(prev_close) - 1) * 100
        result.append({
            "index": name,
            "close": float(last_row["Close"]),
            "change_pct": change_pct,
        })
    return pd.DataFrame(result)


@dataclass
class ScreeningConfig:
    recommendation_count: int = 10
    ma_windows: Tuple[int, int, int, int] = (5, 20, 60, 120)
    investor_window: int = 3
    rsi_window: int = 14
    bollinger_window: int = 20
    bollinger_sigma: float = 2.0


def screen_candidates(
    as_of: Optional[date] = None,
    config: Optional[ScreeningConfig] = None,
) -> List[Recommendation]:
    if config is None:
        config = ScreeningConfig()
    if as_of is None:
        as_of = _krx_business_day(date.today())

    listings = fdr.StockListing("KRX")
    listings = listings.drop_duplicates(subset="Symbol")
    listings = listings[listings["Market"].isin(["KOSPI", "KOSDAQ"])]
    fundamentals = _load_recent_fundamentals(as_of, listings["Symbol"].tolist())

    qualified = _filter_financial_health(fundamentals)
    technicals = _evaluate_technicals(qualified, as_of, config)
    investor_data = _evaluate_investor_flow(technicals.index.tolist(), as_of, config)

    scored = _score_candidates(technicals, investor_data, listings)
    top = scored.head(config.recommendation_count)

    recommendations: List[Recommendation] = []
    latest_prices = stock.get_market_ohlcv_by_ticker(as_of.strftime("%Y%m%d"))
    for symbol, row in top.iterrows():
        if symbol not in latest_prices.index:
            continue
        latest = latest_prices.loc[symbol]
        recommendation_reason = _build_reason(row)
        key_issues = _sector_issue(symbol, listings)
        recommendations.append(
            Recommendation(
                ticker=symbol,
                name=row["Name"],
                open_price=float(latest["시가"]),
                close_price=float(latest["종가"]),
                change_pct=float(latest["등락률"]),
                recommendation_reason=recommendation_reason,
                key_issues=key_issues,
            )
        )
    return recommendations


def _load_recent_fundamentals(as_of: date, tickers: List[str]) -> Dict[str, pd.DataFrame]:
    quarter_dates = _infer_quarter_ends(as_of)
    fundamentals: Dict[str, pd.DataFrame] = {}
    for q_date in quarter_dates:
        df = stock.get_market_fundamental_by_ticker(q_date.strftime("%Y%m%d"))
        fundamentals[q_date.strftime("%Y-%m-%d")] = df.loc[df.index.intersection(tickers)]
    return fundamentals


def _filter_financial_health(fundamentals: Dict[str, pd.DataFrame]) -> pd.Index:
    tickers = None
    for df in fundamentals.values():
        positive_eps = df[df["EPS"] > 0]
        if tickers is None:
            tickers = positive_eps.index
        else:
            tickers = tickers.intersection(positive_eps.index)
    if tickers is None:
        return pd.Index([])
    return tickers


def _evaluate_technicals(
    tickers: Iterable[str],
    as_of: date,
    config: ScreeningConfig,
) -> pd.DataFrame:
    start = as_of - timedelta(days=max(config.ma_windows) * 3)
    records = []
    for symbol in tickers:
        ohlcv = stock.get_market_ohlcv_by_date(
            start.strftime("%Y%m%d"),
            as_of.strftime("%Y%m%d"),
            symbol,
        )
        if ohlcv.empty or len(ohlcv) < max(config.ma_windows):
            continue
        close = ohlcv["종가"].astype(float)
        ma = {window: close.rolling(window).mean().iloc[-1] for window in config.ma_windows}
        if not (ma[config.ma_windows[0]] > ma[config.ma_windows[1]] > ma[config.ma_windows[2]] > ma[config.ma_windows[3]]):
            continue

        rsi = RSIIndicator(close=close, window=config.rsi_window).rsi().iloc[-1]
        bb = BollingerBands(close=close, window=config.bollinger_window, window_dev=config.bollinger_sigma)
        bb_high = bb.bollinger_hband().iloc[-1]
        bb_low = bb.bollinger_lband().iloc[-1]
        band_range = bb_high - bb_low
        if band_range == 0:
            continue
        bb_position = (close.iloc[-1] - bb_low) / band_range
        bb_position = float(np.clip(bb_position, 0, 1))

        records.append(
            {
                "Ticker": symbol,
                "RSI": rsi,
                "BB_Pos": bb_position,
                "Close": close.iloc[-1],
                "MA5": ma[config.ma_windows[0]],
                "MA20": ma[config.ma_windows[1]],
                "MA60": ma[config.ma_windows[2]],
                "MA120": ma[config.ma_windows[3]],
            }
        )
    df = pd.DataFrame(records)
    if df.empty:
        return df
    return df.set_index("Ticker")


def _evaluate_investor_flow(
    tickers: List[str],
    as_of: date,
    config: ScreeningConfig,
) -> pd.DataFrame:
    start = as_of - timedelta(days=config.investor_window * 2)
    investor_frames = []
    for symbol in tickers:
        flow = stock.get_market_trading_value_by_investor(
            start.strftime("%Y%m%d"),
            as_of.strftime("%Y%m%d"),
            symbol,
        )
        if flow.empty:
            continue
        window = flow.tail(config.investor_window)
        foreign_positive = (window["외국인"] > 0).all()
        inst_positive = (window["기관합계"] > 0).all()
        investor_frames.append(
            {
                "Ticker": symbol,
                "Foreign_Streak": int(foreign_positive),
                "Institutional_Streak": int(inst_positive),
                "Foreign_Net": window["외국인"].sum(),
                "Institutional_Net": window["기관합계"].sum(),
            }
        )
    df = pd.DataFrame(investor_frames)
    if df.empty:
        return df
    return df.set_index("Ticker")


def _score_candidates(
    technicals: pd.DataFrame,
    investor_data: pd.DataFrame,
    listings: pd.DataFrame,
) -> pd.DataFrame:
    if technicals.empty or investor_data.empty:
        return pd.DataFrame()
    merged = technicals.join(investor_data, how="inner")
    if merged.empty:
        return merged
    merged = merged.join(listings.set_index("Symbol")["Name"], how="left")
    merged["Foreign_Score"] = np.tanh(merged["Foreign_Net"] / 1e9)
    merged["Institutional_Score"] = np.tanh(merged["Institutional_Net"] / 1e9)
    merged["RSI_Score"] = 1 - np.abs(merged["RSI"] - 60) / 60
    merged["BB_Score"] = 1 - np.abs(merged["BB_Pos"] - 0.5)
    merged["Total_Score"] = (
        0.3 * merged["RSI_Score"]
        + 0.3 * merged["BB_Score"]
        + 0.2 * merged["Foreign_Score"]
        + 0.2 * merged["Institutional_Score"]
    )
    return merged.sort_values("Total_Score", ascending=False)


def _build_reason(row: pd.Series) -> str:
    reasons = [
        f"RSI {row['RSI']:.1f} (target ~60)",
        f"Bollinger position {row['BB_Pos']:.2f}",
    ]
    if row.get("Foreign_Streak", 0) > 0:
        reasons.append("연속 외국인 순매수")
    if row.get("Institutional_Streak", 0) > 0:
        reasons.append("연속 기관 순매수")
    return ", ".join(reasons)


def _sector_issue(symbol: str, listings: pd.DataFrame) -> str:
    info = listings.set_index("Symbol")
    if symbol not in info.index:
        return ""
    record = info.loc[symbol]
    sector = record.get("Sector", "")
    industry = record.get("Industry", "")
    components = []
    if sector:
        components.append(f"섹터: {sector}")
    if industry:
        components.append(f"업종: {industry}")
    return ", ".join(components)


def build_recommendation_table(recommendations: List[Recommendation]) -> pd.DataFrame:
    records = []
    for rec in recommendations:
        records.append(
            {
                "종목코드": rec.ticker,
                "종목명": rec.name,
                "당일시가": rec.open_price,
                "당일종가": rec.close_price,
                "등락률": rec.change_pct,
                "추천근거": rec.recommendation_reason,
                "이슈사항": rec.key_issues,
            }
        )
    return pd.DataFrame(records)


def summarize_market(overview: MarketOverview, outlook: EconomicOutlook) -> str:
    lines = [
        f"[{overview.as_of} 마감시황]",
        f"- KOSPI 종가 {overview.kospi_close:,.0f}p ({overview.kospi_change_pct:.2f}%)",
        f"- KOSDAQ 종가 {overview.kosdaq_close:,.0f}p ({overview.kosdaq_change_pct:.2f}%)",
    ]
    lines.append("\n[주요 강세 섹터]")
    for sector, row in overview.sector_performance.head(5).iterrows():
        lines.append(f"- {sector}: {row['avg_pct_change']:.2f}% ({int(row['symbols'])}개 종목)")

    lines.append("\n[수급 특이사항]")
    for _, row in overview.supply_demand.iterrows():
        lines.append(
            f"- {row['종목명']} 외국인 {row['외국인'] / 1e8:.1f}억, 기관 {row['기관합계'] / 1e8:.1f}억"
        )

    lines.append("\n[익일 주요 이벤트]")
    if outlook.events.empty:
        lines.append("- 발표 예정된 주요 경제지표 없음")
    else:
        for _, row in outlook.events.iterrows():
            lines.append(f"- {row['time']} {row['country']} {row['event']} ({row['importance']})")

    lines.append("\n[미 증시 체크]")
    for _, row in outlook.us_index_outlook.iterrows():
        lines.append(f"- {row['index']}: {row['close']:.2f} ({row['change_pct']:.2f}%)")
    return "\n".join(lines)


def run_pipeline(as_of: Optional[date] = None, config: Optional[ScreeningConfig] = None) -> Tuple[str, pd.DataFrame]:
    overview = get_market_overview(as_of)
    outlook = get_economic_outlook(as_of)
    recommendations = screen_candidates(as_of, config)
    summary = summarize_market(overview, outlook)
    table = build_recommendation_table(recommendations)
    return summary, table


def demo(as_of: Optional[str] = None) -> None:
    """Execute the complete pipeline and pretty-print the output."""
    if as_of is None:
        target_date = None
    else:
        target_date = datetime.strptime(as_of, "%Y-%m-%d").date()

    summary, table = run_pipeline(target_date)
    print(summary)
    print()
    print("[추천 종목]")
    print(table.to_string(index=False))


if __name__ == "__main__":
    summary_text, recommendation_table = run_pipeline()
    print(summary_text)
    print()
    print(recommendation_table)
