import yfinance as yf
import pandas as pd
from time import sleep

def download_crypto_data(symbols, interval="1h", period="max"):
    """
    Download cryptocurrency data from Yahoo Finance for multiple symbols
    
    Args:
        symbols (list): List of cryptocurrency symbols (e.g., ["BTC-USD", "ETH-USD"])
        interval (str): Data interval (default: "1h")
        period (str): Data period (default: "max")
    """
    for symbol in symbols:
        try:
            print(f"Downloading {symbol} data...")
            df = yf.download(symbol, interval=interval, period=period)
            
            if len(df) > 0:
                filename = f"{symbol.replace('-','_')}_{interval}_{period}.csv"
                df.to_csv(filename)
                print(f"Successfully saved: {filename}")
                print(f"Total bars: {len(df)}")
                print(f"Date range: {df.index[0]} to {df.index[-1]}")
            else:
                print(f"No data available for {symbol}")
            
            # Pause between requests
            sleep(2)
            
        except Exception as e:
            print(f"Error downloading {symbol}: {str(e)}")

if __name__ == "__main__":
    # List of cryptocurrency pairs
    crypto_symbols = [
        "BTC-USD", 
        "ETH-USD",
        "SOL-USD",
        "DOGE-USD",
        "PEPE-USD",
        "TRX-USD",
        "ARB-USD",
        "CAKE-USD",
        "XRP-USD"
    ]
    
    download_crypto_data(crypto_symbols)
    print("All data downloads completed.")
