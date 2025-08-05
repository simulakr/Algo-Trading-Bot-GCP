# main.py
import time
import logging
from typing import Dict, Optional
from config import SYMBOLS, INTERVAL, LEVERAGE
from exchange import BinanceFuturesAPI
from indicators import calculate_indicators
from signals import generate_signals
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
        self.api = BinanceFuturesAPI(testnet=testnet)
        self.position_manager = PositionManager(self.api.client)
        self.symbols = SYMBOLS
        self.interval = INTERVAL
        self._initialize_account()

    def _initialize_account(self):
        """Hesap ayarlarını yapılandır"""
        try:
            for symbol in self.symbols:
                self.api.client.futures_change_leverage(
                    symbol=symbol,
                    leverage=LEVERAGE
                )
                self.api.client.futures_change_margin_type(
                    symbol=symbol,
                    marginType='ISOLATED'
                )
            logger.info(f"Hesap ayarları tamamlandı | Kaldıraç: {LEVERAGE}x")
        except Exception as e:
            logger.error(f"Hesap ayarlama hatası: {str(e)}")

    def _get_market_data(self, symbol: str) -> Optional[Dict]:
        """Tek sembol için veri işleme pipeline'ı"""
        try:
            df = self.api.get_ohlcv(symbol, self.interval)
            if df is None or df.empty:
                return None

            df = calculate_indicators(df)
            df = generate_signals(df)
            return df.iloc[-1].to_dict()
        except Exception as e:
            logger.error(f"{symbol} veri işleme hatası: {str(e)}")
            return None

    def _generate_signals(self) -> Dict[str, Optional[str]]:
        """Tüm semboller için sinyal oluştur"""
        signals = {}
        for symbol in self.symbols:
            data = self._get_market_data(symbol)
            if not data:
                signals[symbol] = None
                continue

            if check_long_entry(data, symbol):
                signals[symbol] = 'LONG'
            elif check_short_entry(data, symbol):
                signals[symbol] = 'SHORT'
            else:
                signals[symbol] = None
        return signals

    def _execute_trades(self, signals: Dict[str, Optional[str]]):
        """Sinyalleri işle ve pozisyon aç/kapa"""
        for symbol, signal in signals.items():
            if not signal:
                continue

            data = self._get_market_data(symbol)
            if not data:
                continue

            # Mevcut pozisyon kontrolü
            if self.position_manager.has_active_position(symbol):
                continue

            # Yeni pozisyon aç
            self.position_manager.open_position(
                symbol=symbol,
                direction=signal,
                entry_price=data['close'],
                atr=data['pct_atr']
            )

    def run(self):
        """Ana çalıştırma döngüsü"""
        logger.info(f"Bot başlatıldı | Semboller: {self.symbols} | Zaman Aralığı: {self.interval}")

        while True:
            try:
                start_time = time.time()

                # 1. Sinyal oluştur
                signals = self._generate_signals()

                # 2. Pozisyonları yönet
                self.position_manager.manage_positions(signals)

                # 3. Yeni işlemleri aç
                self._execute_trades(signals)

                # 4. Cycle süresi kontrolü
                elapsed = time.time() - start_time
                sleep_time = max(60 - elapsed, 5)  # En az 5 sn bekle
                time.sleep(sleep_time)

            except KeyboardInterrupt:
                logger.info("Bot manuel olarak durduruldu")
                break
            except Exception as e:
                logger.error(f"Beklenmeyen hata: {str(e)}", exc_info=True)
                time.sleep(60)

if __name__ == "__main__":
    # Testnet modunda çalıştır (prodüksiyonda False yapın)
    bot = TradingBot(testnet=True)
    bot.run()
