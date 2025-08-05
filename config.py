import os
from dotenv import load_dotenv

load_dotenv()  # .env dosyasındaki API anahtarlarını yükle

# Sembol ve Zaman Aralığı Ayarları
SYMBOLS = ["SUIUSDT", "ETHUSDT" , "SOLUSDT"]  # İşlem yapılacak çiftler
INTERVAL = "15m"  # Zaman aralığı

# Risk Yönetimi
RISK_PER_TRADE_USDT = 10.0  # Her işlemde sabit 10 USDT risk
LEVERAGE = 80  # Varsayılan kaldıraç (sembol bazında değiştirilebilir)

# Binance API Ayarları
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
