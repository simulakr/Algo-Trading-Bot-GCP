import os
from dotenv import load_dotenv

load_dotenv()  # .env dosyasındaki API anahtarlarını yükle

# ByBit API Ayarları
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")

# Sembol ve Zaman Aralığı Ayarları
SYMBOLS = ['BTCUSDT', 'ETHUSDT', "SOLUSDT",'XRPUSDT','DOGEUSDT']  # "SUIUSDT"
INTERVAL = "15"  # (15m-'15', 1h-'60')

# Percent ATR Ranges: atr.quantile(0.20 - 0.95)
atr_ranges = {'SOLUSDT':  (0.423, 1.176), 
              'BTCUSDT': (0.173, 0.645), 
               'ETHUSDT':  (0.363, 0.990), 
              'DOGEUSDT':  (0.465, 1.306), 
              'XRPUSDT':  (0.363, 1.378),  
              }

# Z: atr.quantile(0.35 - 0.65)
Z_RANGES = {
    'BTCUSDT': (0.2109, 0.309),
    'ETHUSDT': (0.372, 0.523),
    'SOLUSDT': (0.451, 0.622),
    'DOGEUSDT': (0.498, 0.698),
    'XRPUSDT': (0.397, 0.604),
}

Z_INDICATOR_PARAMS = {
    'atr_period': 14,
    'atr_multiplier': 1  # minimum z
}

# Quantity for Position Size
ROUND_NUMBERS = {
    'BTCUSDT': 3,
    'ETHUSDT': 2,
    'BNBUSDT': 2,
    'SOLUSDT': 1,
    '1000PEPEUSDT': -2,
    'ARBUSDT': 1,
    'SUIUSDT': -1,
    'DOGEUSDT': 0,
    'XRPUSDT': 0,
    'OPUSDT': 1,
}

TP_ROUND_NUMBERS = {
    'BTCUSDT': 2,
    'ETHUSDT': 2,
    'BNBUSDT': 2,
    'SOLUSDT': 3,
    '1000PEPEUSDT': 7,
    'ARBUSDT': 4,
    'SUIUSDT': 5,
    'DOGEUSDT': 5,
    'XRPUSDT': 4,
    'OPUSDT': 4,
}

# Risk Yönetimi
RISK_PER_TRADE_USDT = 10.0  # Per 10 USDT risk
LEVERAGE = 25  # (max 25x)
DEFAULT_LEVERAGE = 25

SYMBOL_SETTINGS = {
    'BTCUSDT': {'risk': 10.0, 'leverage': 25},
    'ETHUSDT': {'risk': 10.0, 'leverage': 25},
    'SOLUSDT': {'risk': 10.0, 'leverage': 25},
    'XRPUSDT': {'risk': 10.0, 'leverage': 25},
    'DOGEUSDT': {'risk': 10.0, 'leverage': 25}, # '1000PEPEUSDT': {'risk': 40.0, 'leverage': 20}
}

# Trading Mode
POSITION_MODE = "Hedge"  # default : OneWay (Hedge mode long/short)
