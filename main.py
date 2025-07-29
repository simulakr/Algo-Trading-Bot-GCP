import pandas as pd
from indicators import calculate_indicators
from signals import generate_signals
from binance_api import get_ohlcv  # Binance API'den veri çeken fonksiyon

# 🔁 Burada coin ve zaman dilimini tanımlayalım
symbol = 'SUIUSDT'
interval = '15m'
limit = 500  # Son 500 mum verisi

def main():
    # 1. Extract Data with API
    df = get_ohlcv(symbol=symbol, interval=interval, limit=limit)

    # 2. Calculate Indicators
    df = calculate_indicators(df)

    # 3. Generate Buy/sell Signal
    df = generate_signals(df)

    # 4. Printing Last Signals
    print(f"\n[{symbol} - {interval}] Son sinyaller:")
    print(df[['close', 'bb_3_touch_long_clean', 'bb_3_touch_short_clean', 'dc_breakout_clean_50', 'dc_breakdown_clean_50']].tail(10))

if __name__ == '__main__':
    main()
