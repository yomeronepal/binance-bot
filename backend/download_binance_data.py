#!/usr/bin/env python3
"""
Download Binance Historical Data for Backtesting
Downloads 5-minute USDⓈ-M futures data for specified symbols and date range
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
import os
from pathlib import Path
import zipfile
import io
import time

# Configuration
SYMBOLS = {
    'HIGH': ['PEPEUSDT', 'SHIBUSDT', 'DOGEUSDT', 'WIFUSDT', 'FLOKIUSDT'],
    'MEDIUM': ['SOLUSDT', 'ADAUSDT', 'MATICUSDT', 'DOTUSDT', 'AVAXUSDT'],
    'LOW': ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
}

BASE_URL = "https://data.binance.vision/data/futures/um/daily/klines"
TIMEFRAME = "5m"
OUTPUT_DIR = "backtest_data"

def download_daily_data(symbol: str, date: datetime) -> pd.DataFrame:
    """Download single day of data for a symbol"""

    date_str = date.strftime('%Y-%m-%d')
    url = f"{BASE_URL}/{symbol}/{TIMEFRAME}/{symbol}-{TIMEFRAME}-{date_str}.zip"

    print(f"  {date_str}...", end=' ', flush=True)

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        # Extract CSV from ZIP
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            csv_filename = z.namelist()[0]
            with z.open(csv_filename) as f:
                df = pd.read_csv(f, header=None)

        # Name columns
        df.columns = [
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ]

        # Convert timestamp to datetime
        df['datetime'] = pd.to_datetime(df['open_time'], unit='ms')

        print(f"✅ {len(df)}", flush=True)
        return df

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"⏭️  (no data)", flush=True)
        else:
            print(f"❌ HTTP {e.response.status_code}", flush=True)
        return None
    except Exception as e:
        print(f"❌ {str(e)[:30]}", flush=True)
        return None

def download_symbol_data(symbol: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """Download data for a symbol across date range"""

    print(f"\n{'='*60}")
    print(f"Downloading {symbol}")
    print(f"{'='*60}")

    all_data = []
    current_date = start_date

    while current_date <= end_date:
        df = download_daily_data(symbol, current_date)
        if df is not None and len(df) > 0:
            all_data.append(df)
        current_date += timedelta(days=1)
        time.sleep(0.1)  # Be nice to Binance servers

    if all_data:
        combined = pd.concat(all_data, ignore_index=True)

        # Sort by timestamp
        combined = combined.sort_values('datetime').reset_index(drop=True)

        # Remove duplicates
        combined = combined.drop_duplicates(subset=['open_time'], keep='first')

        print(f"✅ Total: {len(combined)} candles for {symbol}")
        return combined
    else:
        print(f"❌ No data downloaded for {symbol}")
        return None

def save_data(df: pd.DataFrame, symbol: str, volatility: str):
    """Save data to CSV"""

    # Create output directory
    output_path = Path(OUTPUT_DIR) / volatility.lower()
    output_path.mkdir(parents=True, exist_ok=True)

    # Save CSV
    filename = output_path / f"{symbol}_5m.csv"

    # Select relevant columns
    df_export = df[[
        'datetime', 'open', 'high', 'low', 'close', 'volume',
        'quote_volume', 'trades'
    ]].copy()

    df_export.to_csv(filename, index=False)
    print(f"💾 Saved to {filename}")

    # Print stats
    file_size = filename.stat().st_size / (1024 * 1024)  # MB
    days = (df_export['datetime'].max() - df_export['datetime'].min()).days

    print(f"   Date range: {df_export['datetime'].min()} to {df_export['datetime'].max()}")
    print(f"   Candles: {len(df_export):,} ({days} days)")
    print(f"   File size: {file_size:.2f} MB")

def main():
    print("="*60)
    print("BINANCE HISTORICAL DATA DOWNLOADER")
    print("="*60)
    print()

    # Date range - 3 months
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)

    print(f"Configuration:")
    print(f"  Date range: {start_date.date()} to {end_date.date()}")
    print(f"  Timeframe: {TIMEFRAME}")
    print(f"  Futures type: USDⓈ-M")
    print(f"  Symbols: {sum(len(v) for v in SYMBOLS.values())}")
    print(f"  Output: {OUTPUT_DIR}/")
    print()

    input("Press Enter to start download...")

    # Download each volatility group
    for volatility, symbols in SYMBOLS.items():
        print(f"\n{'#'*60}")
        print(f"# {volatility} VOLATILITY SYMBOLS")
        print(f"{'#'*60}")

        for symbol in symbols:
            df = download_symbol_data(symbol, start_date, end_date)

            if df is not None:
                save_data(df, symbol, volatility)

            print()

    print("="*60)
    print("✅ DOWNLOAD COMPLETE")
    print("="*60)
    print()
    print(f"Data saved to: {OUTPUT_DIR}/")
    print()
    print("Next steps:")
    print("1. Verify data files in backtest_data/ directory")
    print("2. Run: python simple_backtest.py")
    print("3. Analyze results")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Download cancelled by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
