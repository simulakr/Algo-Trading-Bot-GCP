import os
from dotenv import load_dotenv

load_dotenv()  # .env dosyasındaki API anahtarlarını yükle

# ByBit API Ayarları
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")

# Sembol ve Zaman Aralığı Ayarları
SYMBOLS = ['BTCUSDT', 'ETHUSDT','XRPUSDT','DOGEUSDT',  "1000PEPEUSDT", "SOLUSDT"]  # ByBit'te mevcut çiftler "SUIUSDT"
INTERVAL = "15"  # ByBit formatında (15m için '15', 1h için '60')

# Sembol bazlı ATR aralıkları
atr_ranges = {'SOLUSDT':  (0.38, 1.05),
              '1000PEPEUSDT':  (0.64, 1.53),
              'BTCUSDT': (0.15, 0.57),
               'ETHUSDT':  (0.285, 0.88),
              'DOGEUSDT':  (0.41, 1.18),
              'XRPUSDT':  (0.32, 1.27), #'SUIUSDT': (0.61, 1.13)
              }

# Quantity Hesabı İçin Ondalık Sayıları
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
RISK_PER_TRADE_USDT = 40.0  # Her işlemde sabit 20 USDT risk
LEVERAGE = 25  # (ByBit'te max 25x genelde)
DEFAULT_LEVERAGE = 25

SYMBOL_SETTINGS = {
    'BTCUSDT': {'risk': 60.0, 'leverage': 25},
    'ETHUSDT': {'risk': 125.0, 'leverage': 25},
    'SOLUSDT': {'risk': 100.0, 'leverage': 25},
    'XRPUSDT': {'risk': 100.0, 'leverage': 25},
    'DOGEUSDT': {'risk': 90.0, 'leverage': 25},
    '1000PEPEUSDT': {'risk': 75.0, 'leverage': 25}
}

# Trading Ayarları
POSITION_MODE = "Hedge"  # Varsayılan: OneWay (Hedge modu long/short aynı anda)
