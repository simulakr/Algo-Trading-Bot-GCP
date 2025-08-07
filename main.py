import time
import logging
from typing import Dict, Optional
from config import SYMBOLS, INTERVAL, LEVERAGE
from exchange import BybitFuturesAPI  # Değişti
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
        self.api = BybitFuturesAPI(testnet=testnet)  # Değişti
        self.position_manager = PositionManager(self.api.session)  # client -> session
        self.symbols = SYMBOLS
        self.interval = INTERVAL
        self._initialize_account()

    def _initialize_account(self):
        """ByBit için hesap ayarlarını yapılandır"""
        try:
            for symbol in self.symbols:
                # ByBit'te leverage ve margin type ayarları
                self.api.session.set_leverage(
                    category="linear",
                    symbol=symbol,
                    buyLeverage=str(LEVERAGE),
                    sellLeverage=str(LEVERAGE)
                )
            logger.info(f"Hesap ayarları tamamlandı | Kaldıraç: {LEVERAGE}x")
        except Exception as e:
            logger.error(f"Hesap ayarlama hatası: {str(e)}")

    def _get_market_data(self, symbol: str) -> Optional[Dict]:
        """Veri işleme pipeline'ı (Değişiklik yok)"""
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
        """Sinyal oluşturma (Değişiklik yok)"""
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
        """İşlem yürütme (Değişiklik yok)"""
        for symbol, signal in signals.items():
            if not signal:
                continue

            data = self._get_market_data(symbol)
            if not data:
                continue

            if self.position_manager.has_active_position(symbol):
                continue

            self.position_manager.open_position(
                symbol=symbol,
                direction=signal,
                entry_price=data['close'],
                pct_atr=data['pct_atr']  # atr -> pct_atr olarak güncellendi
            )

    def run(self):
        """Ana çalıştırma döngüsü (Değişiklik yok)"""
        logger.info(f"Bot başlatıldı | Semboller: {self.symbols} | Zaman Aralığı: {self.interval}")

        while True:
            try:
                start_time = time.time()
                signals = self._generate_signals()
                self.position_manager.manage_positions(signals)
                self._execute_trades(signals)

                elapsed = time.time() - start_time
                sleep_time = max(60 - elapsed, 5)
                time.sleep(sleep_time)

            except KeyboardInterrupt:
                logger.info("Bot manuel olarak durduruldu")
                break
            except Exception as e:
                logger.error(f"Beklenmeyen hata: {str(e)}", exc_info=True)
                time.sleep(60)

if __name__ == "__main__":
    bot = TradingBot(testnet=True)  # Prodüksiyonda False yapın
    bot.run()
