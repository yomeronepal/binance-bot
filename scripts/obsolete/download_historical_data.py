#!/usr/bin/env python3
"""
Download Historical Data from Binance
Downloads OHLCV data for multiple symbols and timeframes for backtesting.
"""
import requests
import pandas as pd
import os
from datetime import datetime, timedelta
import time
from typing import List, Optional

# Binance API endpoint
BINANCE_API = "https://api.binance.com/api/v3/klines"

# Symbols organized by volatility
SYMBOLS = {
    "high": ["DOGEUSDT", "SHIBUSDT", "PEPEUSDT"],
    "medium": ["ADAUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "AVAXUSDT"],
    "low": ["BTCUSDT", "ETHUSDT", "USDCUSDT"]
}

# Timeframes to download
TIMEFRAMES = {
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d"
}

# Date range (adjust as needed)
# Binance limits: max 1000 candles per request
DEFAULT_START_DATE = "2024-01-01"  # 1 year of data
DEFAULT_END_DATE = "2025-01-01"

# Output directory
OUTPUT_DIR = "backtest_data"


def get_binance_klines(
    symbol: str,
    interval: str,
    start_time: int,
    end_time: int,
    limit: int = 1000
) -> List:
    """
    Fetch klines from Binance API

    Args:
        symbol: Trading pair (e.g., 'BTCUSDT')
        interval: Timeframe (e.g., '15m', '1h', '1d')
        start_time: Start timestamp in milliseconds
        end_time: End timestamp in milliseconds
        limit: Number of candles to fetch (max 1000)

    Returns:
        List of klines
    """
    params = {
        "symbol": symbol,
        "interval": interval,
        "startTime": start_time,
        "endTime": end_time,
        "limit": limit
    }

    try:
        response = requests.get(BINANCE_API, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching data for {symbol} {interval}: {e}")
        return []


def download_full_history(
    symbol: str,
    interval: str,
    start_date: str,
    end_date: str
) -> pd.DataFrame:
    """
    Download full historical data by making multiple API calls

    Args:
        symbol: Trading pair
        interval: Timeframe
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        DataFrame with OHLCV data
    """
    # Convert dates to timestamps (milliseconds)
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    start_ts = int(start_dt.timestamp() * 1000)
    end_ts = int(end_dt.timestamp() * 1000)

    # Calculate interval in milliseconds
    interval_ms = {
        "1m": 60000,
        "5m": 300000,
        "15m": 900000,
        "30m": 1800000,
        "1h": 3600000,
        "4h": 14400000,
        "1d": 86400000
    }

    interval_duration = interval_ms.get(interval, 900000)  # Default to 15m

    all_klines = []
    current_start = start_ts

    print(f"  Downloading {symbol} {interval} from {start_date} to {end_date}...")

    batch_count = 0
    while current_start < end_ts:
        # Calculate end time for this batch (max 1000 candles)
        batch_end = min(current_start + (interval_duration * 1000), end_ts)

        # Fetch klines
        klines = get_binance_klines(symbol, interval, current_start, batch_end, limit=1000)

        if not klines:
            print(f"    ⚠️  No data returned for batch starting at {datetime.fromtimestamp(current_start/1000)}")
            break

        all_klines.extend(klines)
        batch_count += 1

        # Update start time for next batch
        if klines:
            current_start = klines[-1][0] + interval_duration
        else:
            break

        # Rate limiting - be nice to Binance API
        time.sleep(0.5)

        # Progress indicator
        progress = ((current_start - start_ts) / (end_ts - start_ts)) * 100
        print(f"    Progress: {progress:.1f}% ({len(all_klines)} candles, {batch_count} batches)", end="\r")

    print(f"    ✅ Downloaded {len(all_klines)} candles in {batch_count} batches" + " " * 20)

    if not all_klines:
        return pd.DataFrame()

    # Convert to DataFrame
    df = pd.DataFrame(all_klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ])

    # Convert timestamp to datetime
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')

    # Keep only needed columns
    df = df[['datetime', 'open', 'high', 'low', 'close', 'volume', 'quote_volume', 'trades']]

    # Convert to appropriate types
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)
    df['quote_volume'] = df['quote_volume'].astype(float)
    df['trades'] = df['trades'].astype(int)

    return df


def save_to_csv(df: pd.DataFrame, symbol: str, interval: str, volatility: str):
    """
    Save DataFrame to CSV file

    Args:
        df: DataFrame with OHLCV data
        symbol: Trading pair
        interval: Timeframe
        volatility: Volatility category (high/medium/low)
    """
    # Create directory structure
    dir_path = os.path.join(OUTPUT_DIR, volatility)
    os.makedirs(dir_path, exist_ok=True)

    # File path
    file_path = os.path.join(dir_path, f"{symbol}_{interval}.csv")

    # Save to CSV
    df.to_csv(file_path, index=False)

    # File size
    file_size = os.path.getsize(file_path) / 1024  # KB

    print(f"    💾 Saved to {file_path} ({file_size:.1f} KB)")


def download_all_data(
    timeframes: Optional[List[str]] = None,
    symbols_dict: Optional[dict] = None,
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE
):
    """
    Download data for all symbols and timeframes

    Args:
        timeframes: List of timeframes to download (default: all)
        symbols_dict: Dict of symbols by volatility (default: all)
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
    """
    if timeframes is None:
        timeframes = list(TIMEFRAMES.keys())

    if symbols_dict is None:
        symbols_dict = SYMBOLS

    print("=" * 80)
    print("BINANCE HISTORICAL DATA DOWNLOADER")
    print("=" * 80)
    print(f"\n📅 Date Range: {start_date} to {end_date}")
    print(f"⏰ Timeframes: {', '.join(timeframes)}")

    # Count total downloads
    total_downloads = sum(len(symbols) for symbols in symbols_dict.values()) * len(timeframes)
    print(f"📊 Total downloads: {total_downloads}")
    print()

    completed = 0
    failed = []

    for volatility, symbols in symbols_dict.items():
        print(f"\n{'=' * 80}")
        print(f"Volatility: {volatility.upper()}")
        print(f"{'=' * 80}\n")

        for symbol in symbols:
            print(f"📈 {symbol}")

            for interval in timeframes:
                try:
                    # Download data
                    df = download_full_history(symbol, interval, start_date, end_date)

                    if df.empty:
                        print(f"    ⚠️  No data available for {symbol} {interval}")
                        failed.append((symbol, interval, "No data"))
                        continue

                    # Save to CSV
                    save_to_csv(df, symbol, interval, volatility)

                    completed += 1

                except Exception as e:
                    print(f"    ❌ Error: {e}")
                    failed.append((symbol, interval, str(e)))

            print()  # Blank line between symbols

    # Summary
    print("\n" + "=" * 80)
    print("DOWNLOAD SUMMARY")
    print("=" * 80)
    print(f"\n✅ Completed: {completed}/{total_downloads}")

    if failed:
        print(f"\n❌ Failed: {len(failed)}")
        for symbol, interval, error in failed:
            print(f"   • {symbol} {interval}: {error}")

    print(f"\n📁 Data saved to: {os.path.abspath(OUTPUT_DIR)}")

    # Show directory structure
    print("\n📂 Directory Structure:")
    for volatility in symbols_dict.keys():
        vol_dir = os.path.join(OUTPUT_DIR, volatility)
        if os.path.exists(vol_dir):
            files = os.listdir(vol_dir)
            print(f"\n  {volatility}/ ({len(files)} files)")
            for file in sorted(files)[:5]:  # Show first 5
                file_path = os.path.join(vol_dir, file)
                size = os.path.getsize(file_path) / 1024
                print(f"    • {file} ({size:.1f} KB)")
            if len(files) > 5:
                print(f"    ... and {len(files) - 5} more")


def quick_download():
    """
    Quick download - just the essentials for testing
    Downloads 3 months of data for 3 symbols (1 per volatility)
    """
    print("=" * 80)
    print("QUICK DOWNLOAD - ESSENTIAL DATA ONLY")
    print("=" * 80)
    print("\n📦 Downloading 3 months of data for testing...")
    print("   • BTCUSDT (LOW volatility)")
    print("   • SOLUSDT (MEDIUM volatility)")
    print("   • DOGEUSDT (HIGH volatility)")
    print("   • Timeframes: 15m, 1h, 4h")
    print()

    # 3 months of data
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)

    quick_symbols = {
        "low": ["BTCUSDT"],
        "medium": ["SOLUSDT"],
        "high": ["DOGEUSDT"]
    }

    quick_timeframes = ["15m", "1h", "4h"]

    download_all_data(
        timeframes=quick_timeframes,
        symbols_dict=quick_symbols,
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d")
    )


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Download historical data from Binance for backtesting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download all data (full year, all symbols, all timeframes)
  python download_historical_data.py --all

  # Quick download (3 months, 3 symbols, 3 timeframes) - RECOMMENDED FOR TESTING
  python download_historical_data.py --quick

  # Specific timeframes
  python download_historical_data.py --timeframes 15m 1h 4h

  # Specific date range
  python download_historical_data.py --start 2024-06-01 --end 2024-12-31

  # Specific symbols (low volatility only)
  python download_historical_data.py --volatility low --timeframes 15m 1h
        """
    )

    parser.add_argument("--all", action="store_true",
                        help="Download all data (1 year, all symbols, all timeframes)")
    parser.add_argument("--quick", action="store_true",
                        help="Quick download (3 months, 3 symbols, 3 timeframes) - RECOMMENDED")
    parser.add_argument("--timeframes", nargs="+", choices=list(TIMEFRAMES.keys()),
                        help="Timeframes to download (default: all)")
    parser.add_argument("--volatility", choices=["high", "medium", "low"],
                        help="Download only specific volatility category")
    parser.add_argument("--start", default=DEFAULT_START_DATE,
                        help=f"Start date (YYYY-MM-DD, default: {DEFAULT_START_DATE})")
    parser.add_argument("--end", default=DEFAULT_END_DATE,
                        help=f"End date (YYYY-MM-DD, default: {DEFAULT_END_DATE})")

    args = parser.parse_args()

    # Quick mode
    if args.quick:
        quick_download()
        return

    # Full download mode
    timeframes = args.timeframes if args.timeframes else list(TIMEFRAMES.keys())

    # Filter symbols by volatility if specified
    if args.volatility:
        symbols_dict = {args.volatility: SYMBOLS[args.volatility]}
    else:
        symbols_dict = SYMBOLS

    # Confirm if downloading a lot of data
    if not args.all and not args.volatility and not args.timeframes:
        total = sum(len(s) for s in symbols_dict.values()) * len(timeframes)
        print(f"\n⚠️  You're about to download {total} datasets.")
        print(f"   Date range: {args.start} to {args.end}")
        print(f"   This may take 10-30 minutes.\n")

        response = input("Continue? (y/n): ")
        if response.lower() != 'y':
            print("Cancelled.")
            return

    download_all_data(
        timeframes=timeframes,
        symbols_dict=symbols_dict,
        start_date=args.start,
        end_date=args.end
    )

    print("\n✅ Download complete!")
    print("\n💡 Next steps:")
    print("   1. Run quick optimization: python quick_optimize.py")
    print("   2. Or compare timeframes: python optimize_timeframes.py")


if __name__ == "__main__":
    main()
