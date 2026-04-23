import time
import logging
import datetime
from typing import Dict, Optional
from config import SYMBOLS, INTERVAL, LEVERAGE
from exchange import BybitFuturesAPI
from indicators import calculate_indicators
from entry_strategies import check_long_entry, check_short_entry
from position_manager import PositionManager
import pandas as pd


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
        """Bybit'teki mevcut pozisyonları bot hafızasına yükle (TP/SL emirleri dahil)"""
        try:
            positions = self.api.session.get_positions(category='linear', settleCoin='USDT')
            if positions['retCode'] == 0:
                for pos in positions['result']['list']:
                    if float(pos.get('size', 0)) > 0:  # Açık pozisyon varsa
                        symbol = pos['symbol']
                        direction = 'LONG' if pos['side'] == 'Buy' else 'SHORT'
                        quantity = float(pos['size'])
                        
                        # Açık emirleri çek (TP/SL emirlerini bul)
                        oco_pair = self._find_tp_sl_orders(symbol, direction, quantity)
                        
                        # Bot hafızasına ekle
                        position_data = {
                            'symbol': symbol,
                            'direction': direction,
                            'entry_price': float(pos['avgPrice']),
                            'quantity': quantity,
                            'take_profit': float(pos['takeProfit']) if pos['takeProfit'] else None,
                            'stop_loss': float(pos['stopLoss']) if pos['stopLoss'] else None,
                            'order_id': None
                        }
                        
                        # OCO pair varsa ekle
                        if oco_pair:
                            position_data['oco_pair'] = oco_pair
                            logger.info(f"{symbol} pozisyon + TP/SL emirleri yüklendi: {direction}")
                        else:
                            logger.warning(f"{symbol} pozisyon yüklendi ama TP/SL emirleri bulunamadı")
                        
                        self.position_manager.active_positions[symbol] = position_data
                        
        except Exception as e:
            logger.error(f"Mevcut pozisyonlar yüklenirken hata: {e}")
    
    
    def _find_tp_sl_orders(self, symbol: str, direction: str, quantity: float) -> Optional[Dict]:
        """
        Bot restart sonrası mevcut TP/SL emirlerini bulur.
        Yeni yapı: TP1, TP2, SL1, SL2 (her biri yarı miktar)
        """
        try:
            orders = self.api.session.get_open_orders(
                category='linear',
                symbol=symbol
            )
    
            if orders['retCode'] != 0:
                return None
    
            expected_side = "Sell" if direction == "LONG" else "Buy"
            half_qty = round(quantity / 2, 8)
            tolerance = half_qty * 0.05  # %5 tolerans
    
            tp_ids = []
            sl_ids = []
    
            for order in orders['result']['list']:
                if order['side'] != expected_side:
                    continue
    
                order_qty = float(order['qty'])
    
                # Yarı miktar eşleşmesi
                if abs(order_qty - half_qty) > tolerance:
                    continue
    
                # Limit emir → TP
                if order['orderType'] == 'Limit' and order.get('reduceOnly'):
                    tp_ids.append(order['orderId'])
    
                # Stop-Market emir → SL
                elif order['orderType'] == 'Market' and order.get('triggerPrice'):
                    sl_ids.append(order['orderId'])
    
            # TP fiyatlarına göre sırala (TP1 daha yakın, TP2 daha uzak)
            if len(tp_ids) == 2:
                tp_orders = []
                for tid in tp_ids:
                    for o in orders['result']['list']:
                        if o['orderId'] == tid:
                            tp_orders.append((float(o['price']), tid))
                tp_orders.sort(key=lambda x: x[0])
    
                if direction == "LONG":
                    # LONG: TP1 daha düşük fiyat, TP2 daha yüksek
                    tp1_id = tp_orders[0][1]
                    tp2_id = tp_orders[1][1]
                else:
                    # SHORT: TP1 daha yüksek fiyat, TP2 daha düşük
                    tp1_id = tp_orders[1][1]
                    tp2_id = tp_orders[0][1]
            else:
                tp1_id = tp_ids[0] if len(tp_ids) > 0 else None
                tp2_id = tp_ids[1] if len(tp_ids) > 1 else None
    
            sl1_id = sl_ids[0] if len(sl_ids) > 0 else None
            sl2_id = sl_ids[1] if len(sl_ids) > 1 else None
    
            if tp1_id and tp2_id and sl1_id and sl2_id:
                logger.info(f"{symbol} TP1/TP2/SL1/SL2 emirleri bulundu")
                return {
                    'symbol':        symbol,
                    'tp1_order_id':  tp1_id,
                    'tp2_order_id':  tp2_id,
                    'sl1_order_id':  sl1_id,
                    'sl2_order_id':  sl2_id,
                    'tp1_triggered': False,
                    'active':        True
                }
    
            # TP1 zaten tetiklenmişse (restart sırasında) — TP2 + SL2 kaldı
            if tp2_id and sl2_id and not tp1_id and not sl1_id:
                logger.info(f"{symbol} TP1 zaten tetiklenmiş — TP2/SL2 bulundu")
                return {
                    'symbol':        symbol,
                    'tp1_order_id':  None,
                    'tp2_order_id':  tp2_id,
                    'sl1_order_id':  None,
                    'sl2_order_id':  sl2_id,
                    'tp1_triggered': True,
                    'active':        True
                }
    
            logger.warning(
                f"{symbol} emirler eksik — "
                f"TP1: {tp1_id} | TP2: {tp2_id} | SL1: {sl1_id} | SL2: {sl2_id}"
            )
            return None
    
        except Exception as e:
            logger.error(f"{symbol} TP/SL emirleri aranırken hata: {e}")
            return None
            
    def _is_weekend_trading_blocked(self) -> bool:
        try:
            import pytz
            
            turkey_tz = pytz.timezone('Europe/Istanbul')
            
            server_time = self.api.session.get_server_time()
            ts = int(server_time['result']['timeSecond'])
            utc_time = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
            turkey_time = utc_time.astimezone(turkey_tz)
            
            weekday = turkey_time.weekday()
            hour = turkey_time.hour
            minute = turkey_time.minute
            
            if weekday == 4 and hour == 23 and minute >= 59:
                logger.info(f"Hafta sonu bloğu aktif: Cuma {turkey_time.strftime('%H:%M')} (TR)")
                return True
            
            if weekday == 5 or weekday == 6:
                logger.info(f"Hafta sonu bloğu aktif: {turkey_time.strftime('%H:%M')} (TR)")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Hafta sonu kontrol hatası: {e}")
            return False
    
    def _wait_until_next_candle(self) -> None:
        try:
            server_ms   = self.client.get_server_time_ms()
            current     = datetime.datetime.fromtimestamp(server_ms / 1000, tz=datetime.timezone.utc)
            minute      = current.minute
    
            for target in [15, 30, 45, 0]:
                if target == 0:
                    target_time = current.replace(minute=0, second=1, microsecond=0) + datetime.timedelta(hours=1)
                    break
                if minute < target:
                    target_time = current.replace(minute=target, second=1, microsecond=0)
                    break
    
            if target_time <= current:
                target_time += datetime.timedelta(hours=1)
    
            wait_seconds = (target_time - current).total_seconds()
    
            logger.info(
                "Bekleniyor | Şu an: %s | Hedef: %s | Süre: %.1fs",
                current.strftime("%H:%M:%S"),
                target_time.strftime("%H:%M:%S"),
                wait_seconds,
            )
    
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            else:
                time.sleep(1)
    
            logger.info("Yeni mum başladı — veriler çekiliyor")
    
        except Exception as exc:
            logger.error("Zamanlama hatası: %s", exc)
            time.sleep(60)

    def _get_market_data_batch(self) -> Dict[str, Optional[Dict]]:
        all_data = self.api.get_multiple_ohlcv(self.symbols, self.interval)
        now = pd.Timestamp.utcnow()
        results = {}
        
        for symbol, df in all_data.items():
            if df is not None and not df.empty:
                try:
                    df = df[df.index < now]  # kapanmamış mumu at
                    if df.empty:
                        logger.warning(f"{symbol} filtre sonrası veri kalmadı")
                        results[symbol] = None
                        continue
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

            if check_long_entry(data, symbol):
                signals[symbol] = 'LONG'
            elif check_short_entry(data, symbol):
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
                atr_value=data['z'],
                pct_atr=data['pct_z']
            )
    
    
    def run(self):
        """Ana çalıştırma döngüsü"""
        
        logger.info(f"Bot başlatıldı | Semboller: {self.symbols} | Zaman Aralığı: {self.interval}m")
        
        while True:
            try:
                # 15 dakika senkronizasyonu
                self._wait_until_next_candle()

                # --- HAFTA SONU KONTROLÜ ---
                if self._is_weekend_trading_blocked():
                    logger.info("Hafta sonu modu: İşlem atlanıyor, sonraki muma geçiliyor.")
                    continue
                # ---------------------------
                
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
