import os
import pandas as pd
from binance.client import Client
from dotenv import load_dotenv
from typing import List, Optional
import logging

# Log ayarı
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

class BinanceFuturesAPI:
    def __init__(self, testnet: bool = False):
        """Binance Futures API bağlantısını başlatır."""
        self.client = Client(
            api_key=os.getenv('BINANCE_API_KEY'),
            api_secret=os.getenv('BINANCE_API_SECRET'),
            testnet=testnet
        )
        logger.info("Binance Futures API bağlantısı başarılı (Testnet: %s)", testnet)

    def get_ohlcv(
        self,
        symbol: str = 'SUIUSDT',
        interval: str = '15m',
        limit: int = 500,
        convert_to_float: bool = True
    ) -> Optional[pd.DataFrame]:
        """
        Binance Futures'tan OHLCV verisi çeker.

        Args:
            symbol: İşlem çifti (Ör: 'SUIUSDT')
            interval: Zaman aralığı (Ör: '15m', '1h')
            limit: Veri sayısı (max 1500)
            convert_to_float: Sayısal değerleri float'a çevirsin mi?

        Returns:
            pd.DataFrame: OHLCV verisi veya None (hata durumunda)
        """
        try:
            klines = self.client.futures_klines(
                symbol=symbol,
                interval=interval,
                limit=limit
            )

            df = pd.DataFrame(klines, columns=[
                'time', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades',
                'taker_buy_base', 'taker_buy_quote', 'ignore'
            ])

            # Sadece ihtiyacımız olan sütunlar
            df = df[['time', 'open', 'high', 'low', 'close', 'volume']].copy()

            # Tip dönüşümleri
            df['time'] = pd.to_datetime(df['time'], unit='ms')
            if convert_to_float:
                df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)

            df.set_index('time', inplace=True)
            return df

        except Exception as e:
            logger.error("Veri çekme hatası (Sembol: %s): %s", symbol, str(e))
            return None

    def get_multiple_ohlcv(
        self,
        symbols: List[str],
        interval: str = '15m',
        limit: int = 500
    ) -> dict:
        """
        Birden fazla sembolün OHLCV verisini aynı anda çeker.

        Returns:
            {symbol: pd.DataFrame} formatında sözlük
        """
        return {sym: self.get_ohlcv(sym, interval, limit) for sym in symbols}


