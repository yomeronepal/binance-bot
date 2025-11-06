#!/usr/bin/env python3
"""
Fast Parallel Data Downloader
Uses async/await for concurrent downloads - much faster!
"""
import asyncio
import aiohttp
import pandas as pd
import os
from datetime import datetime, timedelta
from typing import List, Dict

# Configuration
BINANCE_API = "https://api.binance.com/api/v3/klines"
OUTPUT_DIR = "backtest_data"

# Quick download config (recommended for testing)
QUICK_CONFIG = {
    "symbols": {
        "low": ["BTCUSDT", "ETHUSDT"],
        "medium": ["SOLUSDT", "ADAUSDT"],
        "high": ["DOGEUSDT"]
    },
    "timeframes": ["15m", "1h", "4h"],
    "months": 3  # Last 3 months
}

# Full download config
FULL_CONFIG = {
    "symbols": {
        "low": ["BTCUSDT", "ETHUSDT"],
        "medium": ["SOLUSDT", "ADAUSDT", "BNBUSDT", "XRPUSDT", "AVAXUSDT"],
        "high": ["DOGEUSDT", "SHIBUSDT", "PEPEUSDT"]
    },
    "timeframes": ["15m", "30m", "1h", "4h", "1d"],
    "months": 12  # Last year
}


async def fetch_klines_async(
    session: aiohttp.ClientSession,
    symbol: str,
    interval: str,
    start_time: int,
    end_time: int
) -> List:
    """Async fetch klines from Binance"""
    params = {
        "symbol": symbol,
        "interval": interval,
        "startTime": start_time,
        "endTime": end_time,
        "limit": 1000
    }

    try:
        async with session.get(BINANCE_API, params=params, timeout=30) as response:
            response.raise_for_status()
            return await response.json()
    except Exception as e:
        print(f"❌ Error fetching {symbol} {interval}: {e}")
        return []


async def download_symbol_timeframe(
    session: aiohttp.ClientSession,
    symbol: str,
    interval: str,
    start_date: datetime,
    end_date: datetime,
    volatility: str
) -> Dict:
    """Download complete history for one symbol/timeframe combination"""

    # Convert to timestamps
    start_ts = int(start_date.timestamp() * 1000)
    end_ts = int(end_date.timestamp() * 1000)

    # Interval duration in milliseconds
    interval_ms = {
        "1m": 60000, "5m": 300000, "15m": 900000,
        "30m": 1800000, "1h": 3600000, "4h": 14400000, "1d": 86400000
    }[interval]

    all_klines = []
    current_start = start_ts

    # Fetch all batches
    while current_start < end_ts:
        batch_end = min(current_start + (interval_ms * 1000), end_ts)

        klines = await fetch_klines_async(session, symbol, interval, current_start, batch_end)

        if not klines:
            break

        all_klines.extend(klines)
        current_start = klines[-1][0] + interval_ms

        # Small delay to respect rate limits
        await asyncio.sleep(0.1)

    if not all_klines:
        return {
            "symbol": symbol,
            "interval": interval,
            "volatility": volatility,
            "success": False,
            "candles": 0
        }

    # Convert to DataFrame
    df = pd.DataFrame(all_klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ])

    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[['datetime', 'open', 'high', 'low', 'close', 'volume', 'quote_volume', 'trades']]

    # Convert types
    for col in ['open', 'high', 'low', 'close', 'volume', 'quote_volume']:
        df[col] = df[col].astype(float)
    df['trades'] = df['trades'].astype(int)

    # Save to CSV
    dir_path = os.path.join(OUTPUT_DIR, volatility)
    os.makedirs(dir_path, exist_ok=True)

    file_path = os.path.join(dir_path, f"{symbol}_{interval}.csv")
    df.to_csv(file_path, index=False)

    file_size = os.path.getsize(file_path) / 1024

    return {
        "symbol": symbol,
        "interval": interval,
        "volatility": volatility,
        "success": True,
        "candles": len(df),
        "file_size_kb": file_size,
        "file_path": file_path
    }


async def download_all_parallel(config: Dict):
    """Download all data in parallel using async"""

    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30 * config["months"])

    print("=" * 80)
    print("FAST PARALLEL DOWNLOADER")
    print("=" * 80)
    print(f"\n📅 Date Range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"⏰ Timeframes: {', '.join(config['timeframes'])}")

    # Count total tasks
    total_tasks = sum(len(symbols) for symbols in config["symbols"].values()) * len(config["timeframes"])
    print(f"📊 Total downloads: {total_tasks}")
    print(f"🚀 Using parallel async downloads (much faster!)\n")

    # Create all download tasks
    tasks = []
    async with aiohttp.ClientSession() as session:
        for volatility, symbols in config["symbols"].items():
            for symbol in symbols:
                for interval in config["timeframes"]:
                    task = download_symbol_timeframe(
                        session, symbol, interval, start_date, end_date, volatility
                    )
                    tasks.append(task)

        # Execute all tasks concurrently with progress tracking
        results = []
        completed = 0

        print("⏳ Downloading...")
        for coro in asyncio.as_completed(tasks):
            result = await coro
            completed += 1

            if result["success"]:
                print(f"✅ [{completed}/{total_tasks}] {result['symbol']:<12} {result['interval']:<5} "
                      f"→ {result['candles']:>6} candles ({result['file_size_kb']:.1f} KB)")
            else:
                print(f"❌ [{completed}/{total_tasks}] {result['symbol']:<12} {result['interval']:<5} → Failed")

            results.append(result)

    return results


def print_summary(results: List[Dict]):
    """Print download summary"""
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]

    print("\n" + "=" * 80)
    print("DOWNLOAD SUMMARY")
    print("=" * 80)

    print(f"\n✅ Successful: {len(successful)}/{len(results)}")
    print(f"❌ Failed: {len(failed)}")

    if successful:
        total_candles = sum(r["candles"] for r in successful)
        total_size = sum(r["file_size_kb"] for r in successful)
        print(f"\n📊 Total candles downloaded: {total_candles:,}")
        print(f"💾 Total size: {total_size / 1024:.2f} MB")

    print(f"\n📁 Data saved to: {os.path.abspath(OUTPUT_DIR)}")

    # Show directory structure
    print("\n📂 Files created:")
    volatility_groups = {}
    for r in successful:
        vol = r["volatility"]
        if vol not in volatility_groups:
            volatility_groups[vol] = []
        volatility_groups[vol].append(r)

    for vol, items in sorted(volatility_groups.items()):
        print(f"\n  {vol}/ ({len(items)} files)")
        for item in sorted(items, key=lambda x: (x['symbol'], x['interval']))[:10]:
            print(f"    • {os.path.basename(item['file_path']):<20} "
                  f"{item['candles']:>6} candles ({item['file_size_kb']:>6.1f} KB)")
        if len(items) > 10:
            print(f"    ... and {len(items) - 10} more files")


async def main_async(mode: str = "quick"):
    """Main async function"""
    if mode == "quick":
        print("\n🎯 QUICK MODE - Downloading essential data for testing")
        print("   • 3 months of data")
        print("   • 5 symbols (BTCUSDT, ETHUSDT, SOLUSDT, ADAUSDT, DOGEUSDT)")
        print("   • 3 timeframes (15m, 1h, 4h)")
        print("   • Estimated time: 1-2 minutes\n")
        config = QUICK_CONFIG
    else:
        print("\n🔥 FULL MODE - Downloading comprehensive dataset")
        print("   • 12 months of data")
        print("   • 10 symbols across 3 volatility categories")
        print("   • 5 timeframes (15m, 30m, 1h, 4h, 1d)")
        print("   • Estimated time: 5-10 minutes\n")
        config = FULL_CONFIG

    response = input("Continue? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled.")
        return

    start_time = datetime.now()

    results = await download_all_parallel(config)

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    print_summary(results)

    print(f"\n⏱️  Total time: {duration:.1f} seconds")

    print("\n✅ Download complete!")
    print("\n💡 Next steps:")
    print("   1. Run: python quick_optimize.py")
    print("   2. Or: python optimize_timeframes.py")


def main():
    import sys

    mode = "quick"
    if len(sys.argv) > 1:
        if sys.argv[1] == "--full":
            mode = "full"
        elif sys.argv[1] == "--help":
            print("Usage:")
            print("  python download_data_fast.py          # Quick mode (recommended)")
            print("  python download_data_fast.py --full   # Full mode (all data)")
            return

    asyncio.run(main_async(mode))


if __name__ == "__main__":
    main()
