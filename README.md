# Algo-Trading-Backtest

# 📈 Algo Trading Backtest — Bollinger Band Strategy

## 🎯 Amaç
Bu proje, Binance API üzerinden kripto fiyat verilerini çekerek Bollinger Band temelli bir strateji kurar ve geçmiş performansını test eder.

## 🧩 Adımlar
1. 📡 **Veri Çekimi:** Binance API üzerinden 15m, 1h, 4h, 1D OHLCV veri.
2. 🧮 **İndikatörler:** Bollinger Band, ATR, ADX hesaplama.
3. 📊 **Strateji:** BB üzerine/altına 3 defa değme kuralı, trend filtresi.
4. 🔁 **Backtest:** Kümülatif PnL, Win Rate, Sharpe Ratio, Drawdown.
5. 📈 **Görselleştirme:** Trade giriş-çıkış noktaları ve equity curve.

## 🛠️ Kullanılan Teknolojiler
- Python, ccxt, pandas, numpy, matplotlib, seaborn


## ⚙️ Kurulum
```bash
pip install -r requirements.txt

--Target Structure--

Algo_Bollinger_Backtest/
│
├── data/
│   └── raw/           # Orijinal çekilen CSV veya pickle dosyaları
│   └── processed/     # Temizlenmiş & birleşmiş dataset
│
├── notebooks/
│   └── 01_fetch_data.ipynb   # Binance API ile veri çekimi
│   └── 02_indicators.ipynb   # BB, ATR, ADX hesaplama
│   └── 03_strategy.ipynb     # Strateji kuralları ve sinyal üretimi
│   └── 04_backtest.ipynb     # Backtest + performans metrikleri
│   └── 05_visualize.ipynb    # Sonuç grafikleri, equity curve
│
├── src/
│   ├── data_loader.py   # API veri çekme fonksiyonu
│   ├── indicators.py    # BB, ATR, ADX hesaplama fonksiyonları
│   ├── strategy.py      # Sinyal üretim kuralları
│   ├── backtester.py    # Backtest fonksiyonları
│
├── requirements.txt     # Gerekli paketler (ccxt, pandas, matplotlib vs)
├── README.md            # Proje açıklaması (amaç, veri kaynağı, sonuçlar)
├── LICENSE              # (MIT veya GPL)
└── .gitignore           # .ipynb_checkpoints, .DS_Store vs.



