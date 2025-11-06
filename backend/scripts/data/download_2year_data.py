#!/usr/bin/env python3
"""
Download 2 years of historical data for backtesting
Downloads data for multiple symbols, volatility classes, and timeframes
Timeframes: 5m, 15m, 1h, 4h, 1d
Symbols: Low (BTC, ETH), Medium (ADA, SOL), High (DOGE) volatility
Period: Jan 2023 - Dec 2024 (2 years)
"""
import asyncio
import aiohttp
from datetime import datetime, timezone
import pandas as pd
import os
from pathlib import Path

# Configuration
SYMBOLS = {
    'low': ['BTCUSDT', 'ETHUSDT'],      # Low volatility
    'medium': ['ADAUSDT', 'SOLUSDT'],   # Medium volatility
    'high': ['DOGEUSDT']                # High volatility
}

TIMEFRAMES = ['5m', '15m', '1h', '4h', '1d']
START_DATE = "2023-01-01"
END_DATE = "2024-12-31"
OUTPUT_BASE_DIR = "backtest_data"
BASE_URL = "https://api.binance.com/api/v3/klines"

# Create directory structure
for volatility in SYMBOLS.keys():
    os.makedirs(f"{OUTPUT_BASE_DIR}/{volatility}", exist_ok=True)

def date_to_timestamp(date_str):
    """Convert date string to millisecond timestamp"""
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)

async def fetch_klines(session, symbol, interval, start_ts, end_ts):
    """Fetch klines from Binance API with progress tracking"""
    all_klines = []
    current_start = start_ts

    print(f"  Downloading {symbol} {interval}...", end='', flush=True)

    while current_start < end_ts:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": current_start,
            "endTime": end_ts,
            "limit": 1000  # Max limit per request
        }

        try:
            async with session.get(BASE_URL, params=params) as response:
                if response.status == 200:
                    klines = await response.json()

                    if not klines:
                        break

                    all_klines.extend(klines)

                    # Update start time for next batch
                    current_start = int(klines[-1][0]) + 1

                    # Rate limiting
                    await asyncio.sleep(0.1)
                elif response.status == 429:
                    # Rate limit hit, wait longer
                    print(" [RATE LIMIT]", end='', flush=True)
                    await asyncio.sleep(60)
                else:
                    print(f" [ERROR {response.status}]", end='', flush=True)
                    await asyncio.sleep(1)

        except Exception as e:
            print(f" [ERROR: {e}]", end='', flush=True)
            await asyncio.sleep(1)
            continue

    print(f" [{len(all_klines)} candles]")
    return all_klines

def save_to_csv(klines, symbol, interval, volatility):
    """Save klines to CSV file"""
    if not klines:
        print(f"    [WARNING] No data to save for {symbol} {interval}")
        return False

    # Convert to DataFrame
    df = pd.DataFrame(klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ])

    # Convert timestamp to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')

    # Convert price columns to float
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)

    # Save to CSV
    filename = f"{OUTPUT_BASE_DIR}/{volatility}/{symbol}_{interval}.csv"
    df.to_csv(filename, index=False)

    # File size in MB
    size_mb = os.path.getsize(filename) / (1024 * 1024)

    print(f"    [OK] Saved {len(df):,} rows to {filename} ({size_mb:.2f} MB)")
    print(f"    [OK] Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")

    return True

async def download_symbol_data(session, symbol, volatility, timeframes):
    """Download all timeframes for a single symbol"""
    print(f"\n{'='*70}")
    print(f"Symbol: {symbol} ({volatility.upper()} volatility)")
    print(f"{'='*70}")

    for timeframe in timeframes:
        start_ts = date_to_timestamp(START_DATE)
        end_ts = date_to_timestamp(END_DATE)

        klines = await fetch_klines(session, symbol, timeframe, start_ts, end_ts)

        if klines:
            save_to_csv(klines, symbol, timeframe, volatility)
        else:
            print(f"    [ERROR] Failed to download {symbol} {timeframe}")

        # Small delay between timeframes
        await asyncio.sleep(0.5)

async def main():
    """Main execution"""
    print(f"\n{'='*70}")
    print(f"DOWNLOADING 2-YEAR HISTORICAL DATA FOR BACKTESTING")
    print(f"{'='*70}")
    print(f"Period: {START_DATE} to {END_DATE} (2 years)")
    print(f"Timeframes: {', '.join(TIMEFRAMES)}")
    print(f"Symbols by Volatility:")
    for vol, syms in SYMBOLS.items():
        print(f"  {vol.upper()}: {', '.join(syms)}")
    print(f"Output: {OUTPUT_BASE_DIR}/")
    print(f"{'='*70}\n")

    start_time = datetime.now()

    async with aiohttp.ClientSession() as session:
        for volatility, symbols in SYMBOLS.items():
            for symbol in symbols:
                await download_symbol_data(session, symbol, volatility, TIMEFRAMES)

    duration = (datetime.now() - start_time).total_seconds()

    print(f"\n{'='*70}")
    print(f"[OK] Download complete!")
    print(f"Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
    print(f"{'='*70}\n")

    # Summary
    print("SUMMARY:")
    total_files = 0
    total_size = 0

    for volatility in SYMBOLS.keys():
        vol_path = Path(f"{OUTPUT_BASE_DIR}/{volatility}")
        if vol_path.exists():
            files = list(vol_path.glob("*.csv"))
            vol_size = sum(f.stat().st_size for f in files) / (1024 * 1024)
            print(f"  {volatility.upper()}: {len(files)} files, {vol_size:.2f} MB")
            total_files += len(files)
            total_size += vol_size

    print(f"\nTOTAL: {total_files} files, {total_size:.2f} MB")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    asyncio.run(main())
