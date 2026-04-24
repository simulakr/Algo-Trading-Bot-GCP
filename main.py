import time
import logging
import datetime
from typing import Dict, Optional
import pandas as pd

from config import SYMBOLS, INTERVAL, LEVERAGE
from exchange import BybitFuturesAPI
from indicators import calculate_indicators
from entry_strategies import check_long_entry, check_short_entry
from position_manager import PositionManager

# ─── Logging ──────────────────────────────────────────────────────────────────
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
        self.api              = BybitFuturesAPI(testnet=testnet)
        self.position_manager = PositionManager(self.api.session)
        self.symbols          = SYMBOLS
        self.interval         = INTERVAL
        self._initialize_account()
        self._load_existing_positions()

    # ─── Hesap Kurulumu ───────────────────────────────────────────────────────

    def _initialize_account(self) -> None:
        """Her sembol için kaldıraç ayarlar."""
        for symbol in self.symbols:
            try:
                self.api.session.set_leverage(
                    category="linear",
                    symbol=symbol,
                    buyLeverage=str(LEVERAGE),
                    sellLeverage=str(LEVERAGE),
                )
                logger.info(f"{symbol} kaldıraç ayarlandı: {LEVERAGE}x")
            except Exception as e:
                if "leverage not modified" in str(e):
                    logger.debug(f"{symbol} kaldıraç zaten {LEVERAGE}x")
                else:
                    logger.warning(f"{symbol} kaldıraç ayarlama uyarısı: {e}")

    # ─── Mevcut Pozisyonları Yükleme ──────────────────────────────────────────

    def _load_existing_positions(self) -> None:
        """Bot restart sonrası exchange'deki açık pozisyonları hafızaya yükler."""
        try:
            positions = self.api.session.get_positions(category='linear', settleCoin='USDT')
            if positions['retCode'] != 0:
                logger.error(f"Pozisyonlar alınamadı: {positions['retMsg']}")
                return

            for pos in positions['result']['list']:
                if float(pos.get('size', 0)) == 0:
                    continue

                symbol    = pos['symbol']
                direction = 'LONG' if pos['side'] == 'Buy' else 'SHORT'
                quantity  = float(pos['size'])

                oco_pair = self._find_tp_sl_orders(symbol, direction, quantity)

                position_data = {
                    'symbol':        symbol,
                    'direction':     direction,
                    'entry_price':   float(pos['avgPrice']),
                    'quantity':      quantity,
                    'take_profit1':  None,  # emir fiyatları oco_pair içinden takip ediliyor
                    'take_profit2':  None,
                    'stop_loss':     None,
                    'current_pct_atr': None,
                    'order_id':      None,
                }

                if oco_pair:
                    position_data['oco_pair'] = oco_pair
                    tp1_done = oco_pair.get('tp1_triggered', False)
                    logger.info(
                        f"{symbol} pozisyon yüklendi ({direction}) | "
                        f"TP1 tetiklendi: {tp1_done}"
                    )
                else:
                    logger.warning(f"{symbol} pozisyon yüklendi ama TP/SL emirleri bulunamadı")

                self.position_manager.active_positions[symbol] = position_data

        except Exception as e:
            logger.error(f"Mevcut pozisyonlar yüklenirken hata: {e}")

    def _find_tp_sl_orders(self, symbol: str, direction: str, quantity: float) -> Optional[Dict]:
        """
        Bot restart sonrası mevcut TP/SL emirlerini bulur.
        Yapı: TP1, TP2, SL1, SL2 (her biri yarı miktar)
        TP1 zaten tetiklendiyse: TP2 + SL2 (tam miktar = kalan yarı)
        """
        try:
            orders = self.api.session.get_open_orders(
                category='linear',
                symbol=symbol,
            )

            if orders['retCode'] != 0:
                return None

            expected_side = "Sell" if direction == "LONG" else "Buy"
            half_qty      = round(quantity / 2, 8)
            tolerance     = half_qty * 0.05  # %5 tolerans

            tp_ids = []
            sl_ids = []

            for order in orders['result']['list']:
                if order['side'] != expected_side:
                    continue

                order_qty = float(order['qty'])

                # Yarı miktar eşleşmesi
                if abs(order_qty - half_qty) > tolerance:
                    continue

                if order['orderType'] == 'Limit' and order.get('reduceOnly'):
                    tp_ids.append(order['orderId'])
                elif order['orderType'] == 'Market' and order.get('triggerPrice'):
                    sl_ids.append(order['orderId'])

            # TP fiyatlarına göre sırala → TP1 daha yakın, TP2 daha uzak
            if len(tp_ids) == 2:
                tp_orders = []
                for tid in tp_ids:
                    for o in orders['result']['list']:
                        if o['orderId'] == tid:
                            tp_orders.append((float(o['price']), tid))
                tp_orders.sort(key=lambda x: x[0])

                if direction == "LONG":
                    tp1_id = tp_orders[0][1]  # daha düşük fiyat
                    tp2_id = tp_orders[1][1]  # daha yüksek fiyat
                else:
                    tp1_id = tp_orders[1][1]  # daha yüksek fiyat
                    tp2_id = tp_orders[0][1]  # daha düşük fiyat
            else:
                tp1_id = tp_ids[0] if len(tp_ids) > 0 else None
                tp2_id = tp_ids[1] if len(tp_ids) > 1 else None

            sl1_id = sl_ids[0] if len(sl_ids) > 0 else None
            sl2_id = sl_ids[1] if len(sl_ids) > 1 else None

            # Normal durum: 4 emir de mevcut
            if tp1_id and tp2_id and sl1_id and sl2_id:
                logger.info(f"{symbol} TP1/TP2/SL1/SL2 emirleri bulundu")
                return {
                    'symbol':        symbol,
                    'tp1_order_id':  tp1_id,
                    'tp2_order_id':  tp2_id,
                    'sl1_order_id':  sl1_id,
                    'sl2_order_id':  sl2_id,
                    'tp1_triggered': False,
                    'active':        True,
                }

            # TP1 zaten tetiklenmişse: sadece TP2 + SL2 kaldı
            if tp2_id and sl2_id and not tp1_id and not sl1_id:
                logger.info(f"{symbol} TP1 zaten tetiklenmiş — TP2/SL2 bulundu")
                return {
                    'symbol':        symbol,
                    'tp1_order_id':  None,
                    'tp2_order_id':  tp2_id,
                    'sl1_order_id':  None,
                    'sl2_order_id':  sl2_id,
                    'tp1_triggered': True,
                    'active':        True,
                }

            logger.warning(
                f"{symbol} emirler eksik — "
                f"TP1: {tp1_id} | TP2: {tp2_id} | SL1: {sl1_id} | SL2: {sl2_id}"
            )
            return None

        except Exception as e:
            logger.error(f"{symbol} TP/SL emirleri aranırken hata: {e}")
            return None

    # ─── Hafta Sonu Kontrolü ──────────────────────────────────────────────────

    def _is_weekend_trading_blocked(self) -> bool:
        try:
            import pytz
            turkey_tz   = pytz.timezone('Europe/Istanbul')
            server_time = self.api.session.get_server_time()
            ts          = int(server_time['result']['timeSecond'])
            utc_time    = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
            turkey_time = utc_time.astimezone(turkey_tz)
            weekday     = turkey_time.weekday()
            hour        = turkey_time.hour
            minute      = turkey_time.minute

            if weekday == 4 and hour == 23 and minute >= 59:
                logger.info(f"Hafta sonu bloğu aktif: Cuma {turkey_time.strftime('%H:%M')} (TR)")
                return True
            if weekday in (5, 6):
                logger.info(f"Hafta sonu bloğu aktif: {turkey_time.strftime('%A %H:%M')} (TR)")
                return True
            return False

        except Exception as e:
            logger.error(f"Hafta sonu kontrol hatası: {e}")
            return False

    # ─── Zamanlama ────────────────────────────────────────────────────────────

    def _wait_until_next_candle(self) -> None:
        """Bybit sunucu saatiyle 15 dakikalık mum kapanışını bekler. Hedef: XX:15:01"""
        try:
            server_time = self.api.session.get_server_time()
            ts          = int(server_time['result']['timeSecond'])
            current     = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
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
                f"Bekleniyor | Şu an: {current.strftime('%H:%M:%S')} | "
                f"Hedef: {target_time.strftime('%H:%M:%S')} | Süre: {wait_seconds:.1f}s"
            )

            if wait_seconds > 0:
                time.sleep(wait_seconds)
            else:
                time.sleep(1)

            logger.info("Yeni mum başladı — veriler çekiliyor")

        except Exception as e:
            logger.error(f"Zamanlama hatası: {e}")
            time.sleep(60)

    # ─── Veri & Sinyal ────────────────────────────────────────────────────────

    def _get_market_data_batch(self) -> Dict[str, Optional[Dict]]:
        """Tüm semboller için OHLCV + indikatör hesaplar. Kapanmamış mumu atar."""
        all_data = self.api.get_multiple_ohlcv(self.symbols, self.interval)
        now      = pd.Timestamp.utcnow()
        results  = {}

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
                    logger.error(f"{symbol} indikatör hatası: {e}")
                    results[symbol] = None
            else:
                results[symbol] = None

        return results

    def _generate_signals(self, all_data: Dict[str, Optional[Dict]]) -> Dict[str, Optional[str]]:
        """Toplu veriden sinyal oluşturur."""
        signals = {}
        for symbol, data in all_data.items():
            if not data:
                signals[symbol] = None
            elif check_long_entry(data, symbol):
                signals[symbol] = 'LONG'
                logger.info(f"{symbol} LONG sinyali")
            elif check_short_entry(data, symbol):
                signals[symbol] = 'SHORT'
                logger.info(f"{symbol} SHORT sinyali")
            else:
                signals[symbol] = None
        return signals

    # ─── Emir Yürütme ─────────────────────────────────────────────────────────

    def _execute_trades(
        self,
        signals:  Dict[str, Optional[str]],
        all_data: Dict[str, Optional[Dict]],
    ) -> None:
        """Sinyallere göre pozisyon açar. PositionManager tüm senaryoları yönetir."""
        for symbol, signal in signals.items():
            if not signal or not all_data.get(symbol):
                continue

            data = all_data[symbol]
            self.position_manager.open_position(
                symbol=symbol,
                direction=signal,
                entry_price=data['close'],
                atr_value=data['z'],
                pct_atr=data['pct_z'],
            )

    # ─── Ana Döngü ────────────────────────────────────────────────────────────

    def run(self) -> None:
        logger.info(f"Bot başlatıldı | Semboller: {self.symbols} | Aralık: {self.interval}m")

        while True:
            try:
                self._wait_until_next_candle()

                if self._is_weekend_trading_blocked():
                    logger.info("Hafta sonu modu — işlem atlanıyor")
                    continue

                start_time = time.time()

                all_data = self._get_market_data_batch()
                signals  = self._generate_signals(all_data)

                # 1. Mevcut pozisyonları yönet (OCO kontrolü + TP/SL güncelleme)
                self.position_manager.manage_positions(signals, all_data)

                # 2. Yeni pozisyonları aç / ters pozisyonları tersine çevir
                self._execute_trades(signals, all_data)

                elapsed     = time.time() - start_time
                server_time = self.api.session.get_server_time()
                timestamp   = int(server_time['result']['timeSecond'])
                server_str  = datetime.datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")

                logger.info(f"Tur tamamlandı | Süre: {elapsed:.2f}s | Saat: {server_str}")

            except KeyboardInterrupt:
                logger.info("Bot manuel olarak durduruldu")
                break
            except Exception as e:
                logger.error(f"Beklenmeyen hata: {e}", exc_info=True)
                time.sleep(60)


if __name__ == "__main__":
    bot = TradingBot(testnet=False)
    bot.run()
