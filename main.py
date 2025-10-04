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
    
    def wait_until_next_candle(self):
        """Bybit sunucu saati ile 15 dakikalık mum sonunu bekle - Saatin çeyreklerinden 1 saniye önce"""
        try:
            # Bybit sunucu zamanını al
            server_time = self.api.session.get_server_time()
            ts = int(server_time['result']['timeSecond']) * 1000  # Unix timestamp milisaniye
            
            # Mevcut zamanı datetime'a çevir
            from datetime import datetime, timezone, timedelta
            current_time = datetime.fromtimestamp(ts / 1000, timezone.utc)
            
            # Bir sonraki çeyrek dakikayı hesapla (XX:14, XX:29, XX:44, XX:59)
            minute = current_time.minute
            
            if minute < 14:
                target_minute = 14
                target_hour = current_time.hour
            elif minute < 29:
                target_minute = 29
                target_hour = current_time.hour
            elif minute < 44:
                target_minute = 44
                target_hour = current_time.hour
            elif minute < 59:
                target_minute = 59
                target_hour = current_time.hour
            else:  # minute >= 59
                # Bir sonraki saatin 14. dakikası
                target_minute = 14
                target_hour = current_time.hour + 1
                # Saat 23'ten 0'a geçiş kontrolü
                if target_hour >= 24:
                    target_hour = 0
            
            # Target time'ı oluştur
            target_time = current_time.replace(
                hour=target_hour,
                minute=target_minute, 
                second=59, 
                microsecond=0
            )
            
            # Gün değişimi kontrolü (23:59 sonrası 00:14'e geçiş)
            if target_hour == 0 and current_time.hour == 23:
                target_time = target_time + timedelta(days=1)
            
            # Bekleme süresini hesapla
            wait_seconds = (target_time.timestamp() - current_time.timestamp())
            
            # DEBUG log
            logger.info(f"DEBUG: minute={minute}, target_minute={target_minute}, current={current_time.strftime('%H:%M:%S')}, target={target_time.strftime('%H:%M:%S')}, wait_seconds={wait_seconds:.2f}")
            
            # Güvenli bekleme (minimum 1 saniye)
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            else:
                logger.warning(f"UYARI: wait_seconds negatif ({wait_seconds:.2f}s)! 1 saniye bekleniyor...")
                time.sleep(1)
            
            logger.info("Yeni mum başladı - Veriler çekiliyor...")
            
        except Exception as e:
            logger.error(f"Zamanlama hatası: {e}")
            time.sleep(60)  # Hata durumunda 1 dakika bekle

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
        """
        Sinyallere göre işlem aç
        NOT: TP/SL güncellemesi artık manage_positions() içinde yapılıyor
        """
        for symbol, signal in signals.items():
            if not signal or not all_data.get(symbol):
                continue
    
            data = all_data[symbol]
            
            # Yeni pozisyon veya ters sinyal durumunda open_position çağır
            # open_position içinde zaten tüm senaryolar yönetiliyor:
            # - Pozisyon yoksa: Yeni açar (Senaryo 1)
            # - Aynı yön: TP/SL günceller (Senaryo 2a)
            # - Ters yön: Eski kapatır, yeni açar (Senaryo 2b)
            
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
                
                # 1. Pozisyon yönetimi (OCO kontrol + TP/SL güncelleme)
                self.position_manager.manage_positions(signals, all_data)
                
                # 2. Yeni pozisyonlar veya pozisyon güncellemeleri
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
