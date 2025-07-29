import os
import pandas as pd
from binance.client import Client
from dotenv import load_dotenv

load_dotenv()


def get_ohlcv(symbol='SUIUSDT', interval='15m', limit=500):
    """
    Binance API'den OHLCV (Open, High, Low, Close, Volume) verisini çeker.
    """
    api_key = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_API_SECRET')

    if not api_key or not api_secret:
        raise ValueError("API keys are not defined in the .env file.")

    client = Client(api_key, api_secret)

    klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(klines, columns=[
        'time', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
    ])
    df = df[['time', 'open', 'high', 'low', 'close', 'volume']].copy()
    df['time'] = pd.to_datetime(df['time'], unit='ms')
    df.set_index('time', inplace=True)
    df = df.astype(float)
    return df
