import time
import logging
import datetime
from typing import Dict, Optional
from config import SYMBOLS, INTERVAL, LEVERAGE
from exchange import BybitFuturesAPI
from indicators import calculate_indicators
from entry_strategies import check_long_entry, check_short_entry
from position_manager import PositionManager

# Log ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TradingBot:
    def __init__(self, testnet: bool = False):
        self.api = BybitFuturesAPI(testnet=testnet)
        self.position_manager = PositionManager(self.api.session)
        self.symbols = SYMBOLS
        self.interval = INTERVAL
        self._initialize_account()

    def _initialize_account(self):
        """ByBit için hesap ayarlarını yapılandır"""
        for symbol in self.symbols:
            try:
                self.api.session.set_leverage(
                category="linear",
                symbol=symbol,
                buyLeverage=str(LEVERAGE),
                sellLeverage=str(LEVERAGE)
                )
                logger.info(f"{symbol} kaldıraç ayarlandı: {LEVERAGE}x")
            except Exception as e:
                if "leverage not modified" in str(e):
                    logger.debug(f"{symbol} kaldıraç zaten {LEVERAGE}x olarak ayarlı")
                else:
                    logger.warning(f"{symbol} kaldıraç ayarlama uyarısı: {str(e)}")

    def _wait_until_next_candle(self):
        """15 dakikalık mum sonuna kadar bekler"""
        now = datetime.datetime.now()
        next_candle = now.replace(second=0, microsecond=0) + datetime.timedelta(minutes=15)
        wait_seconds = (next_candle - now).total_seconds() + 2  # 2 saniye buffer
        time.sleep(max(wait_seconds, 1))
        logger.info("Yeni mum başladı - Veriler çekiliyor...")

    def _get_market_data_batch(self) -> Dict[str, Optional[Dict]]:
        """Tüm sembollerin verilerini tek seferde al"""
        all_data = self.api.get_multiple_ohlcv(self.symbols, self.interval)
        results = {}
        
        for symbol, df in all_data.items():
            if df is not None and not df.empty:
                try:
                    df = calculate_indicators(df, symbol)
                    results[symbol] = df.iloc[-1].to_dict()
                except Exception as e:
                    logger.error(f"{symbol} indicator hatası: {str(e)}")
                    results[symbol] = None
            else:
                results[symbol] = None
        return results

    def _generate_signals(self, all_data: Dict[str, Optional[Dict]]) -> Dict[str, Optional[str]]:
        """Toplu veriden sinyal oluştur"""
        signals = {}
        for symbol, data in all_data.items():
            if not data:
                signals[symbol] = None
                continue

            if check_long_entry(data):
                signals[symbol] = 'LONG'
            elif check_short_entry(data):
                signals[symbol] = 'SHORT'
            else:
                signals[symbol] = None
        return signals

    def _execute_trades(self, signals: Dict[str, Optional[str]], all_data: Dict[str, Optional[Dict]]):
        """Sinyallere göre işlem aç"""
        for symbol, signal in signals.items():
            if not signal or not all_data.get(symbol):
                continue

            if self.position_manager.has_active_position(symbol):
                continue

            data = all_data[symbol]
            self.position_manager.open_position(
                symbol=symbol,
                direction=signal,
                entry_price=data['close'],
                pct_atr=data['pct_atr']
            )

    def run(self):
        """Ana çalıştırma döngüsü"""
        logger.info(f"Bot başlatıldı | Semboller: {self.symbols} | Zaman Aralığı: {self.interval}m")

        while True:
            try:
                # 15 dakika senkronizasyonu
                self._wait_until_next_candle()
                
                start_time = time.time()
                
                # Toplu veri çekme ve işleme
                all_data = self._get_market_data_batch()
                signals = self._generate_signals(all_data)
                
                # Pozisyon yönetimi ve işlemler
                self.position_manager.manage_positions(signals)
                self._execute_trades(signals, all_data)

                elapsed = time.time() - start_time
                logger.info(f"İşlem turu tamamlandı | Süre: {elapsed:.2f}s")
                
            except KeyboardInterrupt:
                logger.info("Bot manuel olarak durduruldu")
                break
            except Exception as e:
                logger.error(f"Beklenmeyen hata: {str(e)}", exc_info=True)
                time.sleep(60)

if __name__ == "__main__":
    bot = TradingBot(testnet=False)
    bot.run()
