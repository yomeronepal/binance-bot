#!/usr/bin/env python3
"""
Simple Binance Data Downloader (No external dependencies)
Uses only Python standard library
"""

import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
import zipfile
import io
import time

# Configuration
SYMBOLS = {
    'HIGH': ['DOGEUSDT'],  # High volatility meme coin
    'MEDIUM': ['SOLUSDT', 'ADAUSDT'],  # Medium volatility alts
    'LOW': ['BTCUSDT', 'ETHUSDT']  # Low volatility majors
}

BASE_URL = "https://data.binance.vision/data/futures/um/daily/klines"
TIMEFRAME = "5m"
OUTPUT_DIR = "backtest_data"

def download_daily_data(symbol: str, date: datetime):
    """Download single day of data for a symbol"""

    date_str = date.strftime('%Y-%m-%d')
    url = f"{BASE_URL}/{symbol}/{TIMEFRAME}/{symbol}-{TIMEFRAME}-{date_str}.zip"

    print(f"  {date_str}...", end=' ', flush=True)

    try:
        # Download using urllib
        with urllib.request.urlopen(url, timeout=30) as response:
            zip_data = response.read()

        # Extract CSV from ZIP
        with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
            csv_filename = z.namelist()[0]
            with z.open(csv_filename) as f:
                # Read CSV data
                lines = f.read().decode('utf-8').strip().split('\n')

        # Parse CSV manually (skip header row)
        data = []
        for i, line in enumerate(lines):
            if i == 0:  # Skip header row
                continue

            parts = line.split(',')
            if len(parts) >= 12:
                try:
                    data.append({
                        'open_time': int(parts[0]),
                        'open': float(parts[1]),
                        'high': float(parts[2]),
                        'low': float(parts[3]),
                        'close': float(parts[4]),
                        'volume': float(parts[5]),
                        'close_time': int(parts[6]),
                        'quote_volume': float(parts[7]),
                        'trades': int(parts[8])
                    })
                except (ValueError, IndexError):
                    # Skip malformed lines
                    continue

        print(f"[OK] {len(data)} candles", flush=True)
        return data

    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"[SKIP] (no data)", flush=True)
        else:
            print(f"[ERROR] HTTP {e.code}", flush=True)
        return None
    except Exception as e:
        print(f"[ERROR] {str(e)[:30]}", flush=True)
        return None

def download_symbol_data(symbol: str, start_date: datetime, end_date: datetime):
    """Download data for a symbol across date range"""

    print(f"\n{'='*60}")
    print(f"Downloading {symbol}")
    print(f"{'='*60}")

    all_data = []
    current_date = start_date

    while current_date <= end_date:
        data = download_daily_data(symbol, current_date)
        if data:
            all_data.extend(data)
        current_date += timedelta(days=1)
        time.sleep(0.2)  # Be nice to Binance servers

    if all_data:
        # Sort by timestamp
        all_data.sort(key=lambda x: x['open_time'])

        # Remove duplicates
        seen = set()
        unique_data = []
        for row in all_data:
            if row['open_time'] not in seen:
                seen.add(row['open_time'])
                unique_data.append(row)

        print(f"[SUCCESS] Total: {len(unique_data)} candles for {symbol}")
        return unique_data
    else:
        print(f"[ERROR] No data downloaded for {symbol}")
        return None

def save_data(data, symbol: str, volatility: str):
    """Save data to CSV"""

    # Create output directory
    output_path = Path(OUTPUT_DIR) / volatility.lower()
    output_path.mkdir(parents=True, exist_ok=True)

    # Save CSV
    filename = output_path / f"{symbol}_5m.csv"

    # Write CSV manually
    with open(filename, 'w') as f:
        # Write header
        f.write('datetime,open,high,low,close,volume,quote_volume,trades\n')

        # Write data
        for row in data:
            dt = datetime.fromtimestamp(row['open_time'] / 1000)
            f.write(f"{dt.isoformat()},{row['open']},{row['high']},{row['low']},"
                   f"{row['close']},{row['volume']},{row['quote_volume']},{row['trades']}\n")

    print(f"[SAVED] Saved to {filename}")

    # Print stats
    file_size = filename.stat().st_size / (1024 * 1024)  # MB
    first_dt = datetime.fromtimestamp(data[0]['open_time'] / 1000)
    last_dt = datetime.fromtimestamp(data[-1]['open_time'] / 1000)
    days = (last_dt - first_dt).days

    print(f"   Date range: {first_dt} to {last_dt}")
    print(f"   Candles: {len(data):,} ({days} days)")
    print(f"   File size: {file_size:.2f} MB")

def main():
    print("="*60)
    print("BINANCE HISTORICAL DATA DOWNLOADER")
    print("(Standard Library Version - No Dependencies)")
    print("="*60)
    print()

    # Date range - Use actual historical dates (2024)
    # Binance only has data up to current real date
    end_date = datetime(2024, 12, 31)  # End of 2024
    start_date = end_date - timedelta(days=30)  # Last 30 days of 2024

    print(f"Configuration:")
    print(f"  Date range: {start_date.date()} to {end_date.date()}")
    print(f"  Timeframe: {TIMEFRAME}")
    print(f"  Futures type: USDT-M (USD-M)")
    print(f"  Symbols: {sum(len(v) for v in SYMBOLS.values())}")
    print(f"  Output: {OUTPUT_DIR}/")
    print()
    print("Starting download in 3 seconds...")
    time.sleep(3)

    # Download each volatility group
    for volatility, symbols in SYMBOLS.items():
        print(f"\n{'#'*60}")
        print(f"# {volatility} VOLATILITY SYMBOLS")
        print(f"{'#'*60}")

        for symbol in symbols:
            data = download_symbol_data(symbol, start_date, end_date)

            if data:
                save_data(data, symbol, volatility)

            print()

    print("="*60)
    print("[SUCCESS] DOWNLOAD COMPLETE")
    print("="*60)
    print()
    print(f"Data saved to: {OUTPUT_DIR}/")
    print()
    print("Next steps:")
    print("1. Verify data files in backtest_data/ directory")
    print("2. Extend date range if needed (edit start_date)")
    print("3. Add more symbols if desired")
    print("4. Create backtest script to analyze the data")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[CANCELLED] Download cancelled by user")
    except Exception as e:
        print(f"\n\n[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
