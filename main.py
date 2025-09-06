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
        self._load_existing_positions()

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

    def _load_existing_positions(self):
        """Bybit'teki mevcut pozisyonları bot hafızasına yükle"""
        try:
            positions = self.api.session.get_positions(category='linear', settleCoin='USDT')
            if positions['retCode'] == 0:
                for pos in positions['result']['list']:
                    if float(pos.get('size', 0)) > 0:  # Açık pozisyon varsa
                        symbol = pos['symbol']
                        direction = 'LONG' if pos['side'] == 'Buy' else 'SHORT'
                        
                        # Bot hafızasına ekle
                        self.position_manager.active_positions[symbol] = {
                            'symbol': symbol,
                            'direction': direction,
                            'entry_price': float(pos['avgPrice']),
                            'quantity': float(pos['size']),
                            'take_profit': float(pos['takeProfit']) if pos['takeProfit'] else None,
                            'stop_loss': float(pos['stopLoss']) if pos['stopLoss'] else None,
                            'order_id': None  # API'den alınamadığı için None
                        }
                        logger.info(f"{symbol} mevcut pozisyon hafızaya yüklendi: {direction}")
        except Exception as e:
            logger.error(f"Mevcut pozisyonlar yüklenirken hata: {e}")
    
    def _wait_until_next_candle(self):
        """Bybit sunucu saati ile 15 dakikalık mum sonunu bekle"""
        try:
            # Bybit sunucu zamanını al
            server_time = self.api.session.get_server_time()
            ts = int(server_time['result']['timeSecond']) * 1000  # Unix timestamp milisaniye
        
            # Bybit zamanına göre next candle hesapla
            current_candle_ts = ((ts // 900000 + 1) * 900000) -1000
            next_candle_ts = current_candle_ts + 900000
            wait_ms = next_candle_ts - ts
            
            # next_candle_ts = (((ts // 900000) + 1) * 900000) - 2000  # 15 dakika = 900000 ms
            # wait_ms = next_candle_ts - ts + 800  # 1 saniye buffer
        
            time.sleep(max(wait_ms / 1000, 1)) 
            logger.info("Yeni mum başladı - Veriler çekiliyor...")
        
        except Exception as e:
            # Fallback: local zaman
            now = datetime.datetime.now()
            next_candle = now.replace(second=0, microsecond=0) + datetime.timedelta(minutes=15)
            wait_seconds = (next_candle - now).total_seconds() + 1
            time.sleep(max(wait_seconds, 1))

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
        """Sinyallere göre işlem aç veya güncelle"""
        for symbol, signal in signals.items():
            if not signal or not all_data.get(symbol):
                continue
    
            data = all_data[symbol]
            
            if self.position_manager.has_active_position(symbol):
                current_pos = self.position_manager.get_active_position(symbol)
                
                if current_pos['direction'] == signal:
                    # AYNI YÖNDE sinyal - TP/SL güncelle
                    self.position_manager.update_existing_position(symbol, data)
                else:
                    # TERS YÖNDE sinyal - Öncekini kapat, yeniyi aç
                    self.position_manager.close_position(symbol, "REVERSE_SIGNAL")
                    time.sleep(1)  # 1 saniye bekle
                    self.position_manager.open_position(
                        symbol=symbol,
                        direction=signal,
                        entry_price=data['close'],
                        atr_value=data['atr'],
                        pct_atr=data['pct_atr']
                    )
            else:
                # YENİ işlem aç
                self.position_manager.open_position(
                    symbol=symbol,
                    direction=signal,
                    entry_price=data['close'],
                    atr_value=data['atr'],
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
                self.position_manager.manage_positions(signals, all_data)
                self._execute_trades(signals, all_data)

                elapsed = time.time() - start_time
                server_time_response = self.api.session.get_server_time()
                timestamp = int(server_time_response['result']['timeSecond'])
                server_time = datetime.datetime.fromtimestamp(timestamp).strftime("%H:%M:%S.%f")[:-4]
                logger.info(f"İşlem turu tamamlandı | Süre: {elapsed:.2f}s | Tamamlanma Saati: {server_time}")
                
            except KeyboardInterrupt:
                logger.info("Bot manuel olarak durduruldu")
                break
            except Exception as e:
                logger.error(f"Beklenmeyen hata: {str(e)}", exc_info=True)
                time.sleep(60)

if __name__ == "__main__":
    bot = TradingBot(testnet=False)
    bot.run()
