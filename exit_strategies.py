from pybit.unified_trading import HTTP
from typing import Dict, Optional, Tuple
import logging
from config import TP_ROUND_NUMBERS, TP1, TP2, SL

logger = logging.getLogger(__name__)


class ExitStrategy:
    def __init__(self, bybit_client: HTTP):
        self.client = bybit_client
        self.logger = logging.getLogger(__name__)

    # ─── Seviye Hesaplama ─────────────────────────────────────────────────────

    def calculate_levels(
        self,
        entry_price: float,
        atr_value:   float,
        direction:   str,
        symbol:      str,
    ) -> Tuple[float, float, float]:
        """
        ATR değerine göre TP1, TP2, SL seviyelerini hesaplar.
        Döndürür: (tp1_price, tp2_price, sl_price)
        """
        round_to = TP_ROUND_NUMBERS.get(symbol, 3)

        if direction == "LONG":
            tp1 = round(entry_price + (TP1 * atr_value), round_to)
            tp2 = round(entry_price + (TP2 * atr_value), round_to)
            sl  = round(entry_price - (SL * atr_value), round_to)
        else:
            tp1 = round(entry_price - (TP1 * atr_value), round_to)
            tp2 = round(entry_price - (TP2 * atr_value), round_to)
            sl  = round(entry_price + (SL * atr_value), round_to)

        return tp1, tp2, sl

    # ─── Emir Gönderme ────────────────────────────────────────────────────────

    def set_limit_tp_sl(
        self,
        symbol:    str,
        direction: str,
        tp1_price: float,
        tp2_price: float,
        sl_price:  float,
        quantity:  str,
        half_only: bool = False,
    ) -> Dict:
        """
        TP/SL emirlerini gönderir.

        half_only=False (normal): 4 emir gönderir
            TP1 (yarı miktar, +3ATR limit)
            TP2 (yarı miktar, +6ATR limit)
            SL1 (yarı miktar, stop-market)
            SL2 (yarı miktar, stop-market)

        half_only=True (TP1 zaten tetiklendi): 2 emir gönderir
            TP2 (tam miktar = kalan yarı, limit)
            SL2 (tam miktar = kalan yarı, stop-market)
            tp1_order_id ve sl1_order_id None olarak döner.
        """
        try:
            tp_side           = "Sell" if direction == "LONG" else "Buy"
            trigger_direction = 2 if direction == "LONG" else 1

            qty = float(quantity)

            if half_only:
                # TP1 zaten tetiklendi — kalan yarı için sadece TP2 + SL2
                tp2_order = self._place_limit(symbol, tp_side, str(qty), tp2_price)
                sl2_order = self._place_stop_market(symbol, tp_side, str(qty), sl_price, trigger_direction)

                tp2_id = tp2_order['result']['orderId']
                sl2_id = sl2_order['result']['orderId']

                logger.info(f"{symbol} [half_only] TP2: {tp2_price} (ID: {tp2_id})")
                logger.info(f"{symbol} [half_only] SL2: {sl_price}  (ID: {sl2_id})")

                oco_pair = {
                    'symbol':        symbol,
                    'tp1_order_id':  None,
                    'tp2_order_id':  tp2_id,
                    'sl1_order_id':  None,
                    'sl2_order_id':  sl2_id,
                    'tp1_triggered': True,
                    'active':        True,
                }

            else:
                # Normal akış — pozisyonu ikiye böl
                half = round(qty / 2, 8)
                # Sembole göre doğru hassasiyette yuvarla
                half_str = str(half).rstrip('0').rstrip('.')

                tp1_order = self._place_limit(symbol, tp_side, half_str, tp1_price)
                tp2_order = self._place_limit(symbol, tp_side, half_str, tp2_price)
                sl1_order = self._place_stop_market(symbol, tp_side, half_str, sl_price, trigger_direction)
                sl2_order = self._place_stop_market(symbol, tp_side, half_str, sl_price, trigger_direction)

                tp1_id = tp1_order['result']['orderId']
                tp2_id = tp2_order['result']['orderId']
                sl1_id = sl1_order['result']['orderId']
                sl2_id = sl2_order['result']['orderId']

                logger.info(f"{symbol} TP1: {tp1_price} yarı miktar (ID: {tp1_id})")
                logger.info(f"{symbol} TP2: {tp2_price} yarı miktar (ID: {tp2_id})")
                logger.info(f"{symbol} SL1: {sl_price}  yarı miktar (ID: {sl1_id})")
                logger.info(f"{symbol} SL2: {sl_price}  yarı miktar (ID: {sl2_id})")

                oco_pair = {
                    'symbol':        symbol,
                    'tp1_order_id':  tp1_id,
                    'tp2_order_id':  tp2_id,
                    'sl1_order_id':  sl1_id,
                    'sl2_order_id':  sl2_id,
                    'tp1_triggered': False,
                    'active':        True,
                }

            return {'oco_pair': oco_pair, 'success': True}

        except Exception as e:
            self.logger.error(f"{symbol} set_limit_tp_sl hatası: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}

    def _place_limit(self, symbol: str, side: str, qty: str, price: float) -> Dict:
        """Limit emir gönderir (TP için)."""
        return self.client.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            orderType="Limit",
            qty=qty,
            price=str(price),
            reduceOnly=True,
            timeInForce="GTC",
        )

    def _place_stop_market(
        self,
        symbol:            str,
        side:              str,
        qty:               str,
        stop_price:        float,
        trigger_direction: int,
    ) -> Dict:
        """Stop-Market emir gönderir (SL için)."""
        return self.client.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            orderType="Market",
            qty=qty,
            triggerPrice=str(stop_price),
            triggerDirection=trigger_direction,
            triggerBy="LastPrice",
            reduceOnly=True,
        )

    # ─── OCO Kontrolü ─────────────────────────────────────────────────────────

    def check_and_cancel_oco(self, oco_pair: Dict) -> Dict:
        """
        TP1/TP2/SL1/SL2 tetiklenme kontrolü.

        Senaryolar:
          TP2 tetiklendi          → SL2 iptal, tamamen kapandı
          SL2 tetiklendi          → TP2 iptal, tamamen kapandı
          TP1 tetiklendi          → SL1 iptal, tp1_triggered=True, devam
          SL1 tetiklendi (TP1 öncesi) → TP1+TP2+SL2 iptal, tamamen kapandı
        """
        if not oco_pair.get('active'):
            return {'already_handled': True}

        try:
            symbol       = oco_pair['symbol']
            tp1_id       = oco_pair.get('tp1_order_id')
            tp2_id       = oco_pair.get('tp2_order_id')
            sl1_id       = oco_pair.get('sl1_order_id')
            sl2_id       = oco_pair.get('sl2_order_id')
            tp1_triggered = oco_pair.get('tp1_triggered', False)

            # Her zaman TP2 ve SL2'yi kontrol et
            tp2_status = self.get_order_status(symbol, tp2_id) if tp2_id else 'NotFound'
            sl2_status = self.get_order_status(symbol, sl2_id) if sl2_id else 'NotFound'

            # TP2 tetiklendi → pozisyon tamamen kapandı
            if tp2_status == 'Filled':
                if sl2_id:
                    self.cancel_order(symbol, sl2_id)
                oco_pair['active'] = False
                logger.info(f"{symbol} TP2 tetiklendi — pozisyon tamamen kapandı")
                return {'triggered': 'TP2'}

            # SL2 tetiklendi → pozisyon tamamen kapandı
            if sl2_status in ['Filled', 'Triggered']:
                if tp2_id:
                    self.cancel_order(symbol, tp2_id)
                if not tp1_triggered and tp1_id:
                    self.cancel_order(symbol, tp1_id)
                oco_pair['active'] = False
                logger.info(f"{symbol} SL2 tetiklendi — pozisyon tamamen kapandı")
                return {'triggered': 'SL2'}

            # TP1 henüz tetiklenmediyse kontrol et
            if not tp1_triggered:
                tp1_status = self.get_order_status(symbol, tp1_id) if tp1_id else 'NotFound'
                sl1_status = self.get_order_status(symbol, sl1_id) if sl1_id else 'NotFound'

                # TP1 tetiklendi → SL1 iptal, yarı kapandı, devam
                if tp1_status == 'Filled':
                    if sl1_id:
                        self.cancel_order(symbol, sl1_id)
                    oco_pair['tp1_triggered'] = True
                    logger.info(f"{symbol} TP1 tetiklendi — SL1 iptal, TP2/SL2 devam ediyor")
                    return {'triggered': 'TP1', 'partial': True}

                # SL1 tetiklendi → her şeyi iptal et, tamamen kapandı
                if sl1_status in ['Filled', 'Triggered']:
                    if tp1_id:
                        self.cancel_order(symbol, tp1_id)
                    if tp2_id:
                        self.cancel_order(symbol, tp2_id)
                    if sl2_id:
                        self.cancel_order(symbol, sl2_id)
                    oco_pair['active'] = False
                    logger.info(f"{symbol} SL1 tetiklendi — pozisyon tamamen kapandı")
                    return {'triggered': 'SL1'}

            return {'status': 'active'}

        except Exception as e:
            self.logger.error(f"{symbol} OCO kontrol hatası: {e}")
            return {'error': str(e)}

    # ─── Emir Sorgulama & İptal ───────────────────────────────────────────────

    def get_order_status(self, symbol: str, order_id: str) -> str:
        """Emir durumunu sorgular. Önce açık emirlere, sonra geçmişe bakar."""
        try:
            result = self.client.get_open_orders(
                category="linear",
                symbol=symbol,
                orderId=order_id,
            )
            orders = result['result']['list']
            if orders:
                return orders[0]['orderStatus']

            # Açık emirlerde yoksa geçmişe bak
            history = self.client.get_order_history(
                category="linear",
                symbol=symbol,
                orderId=order_id,
            )
            if history['result']['list']:
                return history['result']['list'][0]['orderStatus']

            return 'NotFound'

        except Exception as e:
            self.logger.error(f"Emir durum sorgu hatası ({symbol} / {order_id}): {e}")
            return 'Error'

    def cancel_order(self, symbol: str, order_id: Optional[str]) -> None:
        """Emri iptal eder. None gelirse sessizce geçer."""
        if not order_id:
            return
        try:
            self.client.cancel_order(
                category="linear",
                symbol=symbol,
                orderId=order_id,
            )
            logger.info(f"Emir iptal edildi: {symbol} / {order_id}")
        except Exception as e:
            logger.warning(f"İptal hatası (zaten kapanmış olabilir): {symbol} / {order_id} — {e}")
