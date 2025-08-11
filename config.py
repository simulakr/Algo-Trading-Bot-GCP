import os
from dotenv import load_dotenv

load_dotenv()  # .env dosyasındaki API anahtarlarını yükle

# Sembol ve Zaman Aralığı Ayarları
SYMBOLS = ["SUIUSDT", "ETHUSDT", "SOLUSDT"]  # ByBit'te mevcut çiftler
INTERVAL = "15"  # ByBit formatında (15m için '15', 1h için '60')

# Risk Yönetimi
RISK_PER_TRADE_USDT = 5.0  # Her işlemde sabit 10 USDT risk
LEVERAGE = 10  # Daha güvenli başlangıç kaldıracı (ByBit'te max 25x genelde)

# ByBit API Ayarları
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")

# Trading Ayarları
POSITION_MODE = "Hedge"  # Varsayılan: OneWay (Hedge modu long/short aynı anda)
