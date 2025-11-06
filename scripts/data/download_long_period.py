#!/usr/bin/env python3
"""
Download 12-month historical data for extended backtesting
Period: Jan 1, 2024 - Nov 2, 2025 (vs previous 3-month period)
"""
import asyncio
import aiohttp
import pandas as pd
from datetime import datetime, timedelta
import os
from pathlib import Path

# Binance API base URL
BASE_URL = "https://api.binance.com/api/v3/klines"

# Symbols to download (focus on main pairs)
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

# Timeframes (focus on 4h since that's our winner)
INTERVALS = ["4h", "1d"]  # 4h for trading, 1d for trend confirmation

# Extended date range
START_DATE = "2024-01-01"
END_DATE = "2025-11-02"

# Output directory
OUTPUT_DIR = Path("backtest_data_extended")

# Volatility classification
VOLATILITY_MAP = {
    'BTCUSDT': 'low',
    'ETHUSDT': 'low',
    'SOLUSDT': 'medium',
}


async def fetch_klines_async(session, symbol, interval, start_time, end_time):
    """Fetch klines from Binance API asynchronously"""
    params = {
        'symbol': symbol,
        'interval': interval,
        'startTime': start_time,
        'endTime': end_time,
        'limit': 1000
    }

    try:
        async with session.get(BASE_URL, params=params) as response:
            if response.status == 200:
                return await response.json()
            else:
                print(f"❌ Error fetching {symbol} {interval}: {response.status}")
                return []
    except Exception as e:
        print(f"❌ Exception fetching {symbol} {interval}: {e}")
        return []


async def download_symbol_timeframe(session, symbol, interval, start_date, end_date, volatility):
    """Download complete history for one symbol/timeframe"""
    print(f"📥 Downloading {symbol} {interval} ({volatility} vol)")

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    start_ts = int(start_dt.timestamp() * 1000)
    end_ts = int(end_dt.timestamp() * 1000)

    all_klines = []
    current_start = start_ts

    # Batch size based on interval
    if interval == "1m":
        batch_size = 1000 * 60 * 1000  # 1000 minutes
    elif interval == "5m":
        batch_size = 1000 * 5 * 60 * 1000
    elif interval == "15m":
        batch_size = 1000 * 15 * 60 * 1000
    elif interval == "1h":
        batch_size = 1000 * 60 * 60 * 1000
    elif interval == "4h":
        batch_size = 1000 * 4 * 60 * 60 * 1000
    elif interval == "1d":
        batch_size = 1000 * 24 * 60 * 60 * 1000
    else:
        batch_size = 1000 * 60 * 60 * 1000  # Default 1h

    batch_count = 0
    while current_start < end_ts:
        batch_end = min(current_start + batch_size, end_ts)

        klines = await fetch_klines_async(session, symbol, interval, current_start, batch_end)

        if klines:
            all_klines.extend(klines)
            batch_count += 1
            print(f"  Batch {batch_count}: Got {len(klines)} candles (total: {len(all_klines)})")
            current_start = klines[-1][0] + 1  # Start from next timestamp
        else:
            # No more data or error
            break

        # Rate limiting
        await asyncio.sleep(0.1)

    if not all_klines:
        print(f"  ⚠️  No data retrieved for {symbol} {interval}")
        return None

    # Convert to DataFrame
    df = pd.DataFrame(all_klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ])

    # Convert types
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['datetime'] = df['timestamp']

    for col in ['open', 'high', 'low', 'close', 'volume', 'quote_volume']:
        df[col] = df[col].astype(float)

    df['trades'] = df['trades'].astype(int)

    # Keep only needed columns
    df = df[['datetime', 'open', 'high', 'low', 'close', 'volume', 'quote_volume', 'trades']]

    # Save to CSV
    output_dir = OUTPUT_DIR / volatility / interval
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"{symbol}.csv"
    df.to_csv(output_file, index=False)

    print(f"  ✅ Saved {len(df)} candles to {output_file}")
    return len(df)


async def main():
    print("=" * 80)
    print("EXTENDED HISTORICAL DATA DOWNLOAD")
    print("=" * 80)
    print(f"\n📅 Period: {START_DATE} to {END_DATE} (11 months)")
    print(f"📊 Symbols: {', '.join(SYMBOLS)}")
    print(f"⏱️  Timeframes: {', '.join(INTERVALS)}")
    print(f"💾 Output: {OUTPUT_DIR}/\n")

    start_time = datetime.now()

    async with aiohttp.ClientSession() as session:
        tasks = []

        for symbol in SYMBOLS:
            volatility = VOLATILITY_MAP.get(symbol, 'medium')
            for interval in INTERVALS:
                task = download_symbol_timeframe(
                    session, symbol, interval, START_DATE, END_DATE, volatility
                )
                tasks.append(task)

        results = await asyncio.gather(*tasks)

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    successful = sum(1 for r in results if r is not None)
    total_candles = sum(r for r in results if r is not None)

    print("\n" + "=" * 80)
    print("DOWNLOAD COMPLETE")
    print("=" * 80)
    print(f"✅ Successfully downloaded: {successful}/{len(SYMBOLS) * len(INTERVALS)} files")
    print(f"📊 Total candles: {total_candles:,}")
    print(f"⏱️  Time taken: {duration:.2f} seconds")
    print(f"💾 Output directory: {OUTPUT_DIR}/")

    print("\n📁 File structure:")
    for volatility in set(VOLATILITY_MAP.values()):
        vol_dir = OUTPUT_DIR / volatility
        if vol_dir.exists():
            print(f"\n  {volatility}/")
            for interval in INTERVALS:
                interval_dir = vol_dir / interval
                if interval_dir.exists():
                    files = list(interval_dir.glob("*.csv"))
                    print(f"    {interval}/")
                    for f in files:
                        size_mb = f.stat().st_size / (1024 * 1024)
                        print(f"      {f.name} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    asyncio.run(main())
