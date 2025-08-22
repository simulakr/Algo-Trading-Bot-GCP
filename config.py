import os
from dotenv import load_dotenv

load_dotenv()  # .env dosyasındaki API anahtarlarını yükle

# ByBit API Ayarları
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")

# Sembol ve Zaman Aralığı Ayarları
SYMBOLS = ["SUIUSDT", "ETHUSDT", "SOLUSDT"]  # ByBit'te mevcut çiftler
INTERVAL = "15"  # ByBit formatında (15m için '15', 1h için '60')

# Sembol bazlı ATR aralıkları
atr_ranges = {'SOLUSDT':  (0.44, 0.84),
              'PEPEUSDT':  (0.74, 1.3),
              'SUIUSDT': (0.61, 1.13)}

# Risk Yönetimi
RISK_PER_TRADE_USDT = 5.0  # Her işlemde sabit 10 USDT risk
LEVERAGE = 10  # Daha güvenli başlangıç kaldıracı (ByBit'te max 25x genelde)

# Trading Ayarları
POSITION_MODE = "Hedge"  # Varsayılan: OneWay (Hedge modu long/short aynı anda)
