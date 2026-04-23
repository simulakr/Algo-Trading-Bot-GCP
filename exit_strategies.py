from pybit.unified_trading import HTTP
from typing import Dict, Any, Optional, Tuple
import logging
from config import TP_ROUND_NUMBERS

class ExitStrategy:
    def __init__(self, bybit_client: HTTP):
        self.client = bybit_client
        self.logger = logging.getLogger(__name__)

    def calculate_levels(self, entry_price: float, atr_value: float, direction: str, symbol: str) -> Tuple[float, float, float]:
        """ATR değerine göre TP1, TP2, SL seviyelerini hesaplar"""
        round_to = TP_ROUND_NUMBERS.get(symbol, 3)

        if direction == "LONG":
            tp1 = round(entry_price + (3 * atr_value), round_to)
            tp2 = round(entry_price + (6 * atr_value), round_to)
            sl  = round(entry_price - (3 * atr_value), round_to)
        else:
            tp1 = round(entry_price - (3 * atr_value), round_to)
            tp2 = round(entry_price - (6 * atr_value), round_to)
            sl  = round(entry_price + (3 * atr_value), round_to)

        return tp1, tp2, sl

    def set_limit_tp_sl(self, symbol, direction, tp1_price, tp2_price, sl_price, quantity):
        """
        4 emir gönderir:
        - TP1: yarı miktar, limit
        - TP2: yarı miktar, limit
        - SL1: yarı miktar, stop-market
        - SL2: yarı miktar, stop-market
        """
        try:
            tp_side = "Sell" if direction == "LONG" else "Buy"
            trigger_direction = 2 if direction == "LONG" else 1

            # Miktarı ikiye böl
            half_qty = str(round(float(quantity) / 2, 8)).rstrip('0').rstrip('.')

            # TP1 — yarı miktar, +3ATR
            tp1_order = self.client.place_order(
                category="linear",
                symbol=symbol,
                side=tp_side,
                orderType="Limit",
                qty=half_qty,
                price=str(tp1_price),
                reduceOnly=True,
                timeInForce="GTC"
            )

            # TP2 — yarı miktar, +6ATR
            tp2_order = self.client.place_order(
                category="linear",
                symbol=symbol,
                side=tp_side,
                orderType="Limit",
                qty=half_qty,
                price=str(tp2_price),
                reduceOnly=True,
                timeInForce="GTC"
            )

            # SL1 — yarı miktar
            sl1_order = self.client.place_order(
                category="linear",
                symbol=symbol,
                side=tp_side,
                orderType="Market",
                qty=half_qty,
                triggerPrice=str(sl_price),
                triggerDirection=trigger_direction,
                triggerBy="LastPrice",
                reduceOnly=True
            )

            # SL2 — yarı miktar
            sl2_order = self.client.place_order(
                category="linear",
                symbol=symbol,
                side=tp_side,
                orderType="Market",
                qty=half_qty,
                triggerPrice=str(sl_price),
                triggerDirection=trigger_direction,
                triggerBy="LastPrice",
                reduceOnly=True
            )

            tp1_id = tp1_order['result']['orderId']
            tp2_id = tp2_order['result']['orderId']
            sl1_id = sl1_order['result']['orderId']
            sl2_id = sl2_order['result']['orderId']

            logger.info(f"✓ TP1 Limit: {tp1_price} yarı miktar (ID: {tp1_id})")
            logger.info(f"✓ TP2 Limit: {tp2_price} yarı miktar (ID: {tp2_id})")
            logger.info(f"✓ SL1 Stop:  {sl_price}  yarı miktar (ID: {sl1_id})")
            logger.info(f"✓ SL2 Stop:  {sl_price}  yarı miktar (ID: {sl2_id})")

            oco_pair = {
                'symbol':       symbol,
                'tp1_order_id': tp1_id,
                'tp2_order_id': tp2_id,
                'sl1_order_id': sl1_id,
                'sl2_order_id': sl2_id,
                'tp1_triggered': False,
                'active':       True
            }

            return {'oco_pair': oco_pair, 'success': True}

        except Exception as e:
            self.logger.error(f"❌ Limit TP/SL hatası: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}

    def check_and_cancel_oco(self, oco_pair: Dict) -> Dict:
        """
        TP1/TP2/SL1/SL2 tetiklenme kontrolü.

        Senaryolar:
        - TP1 tetiklendi → SL1 iptal, tp1_triggered=True, devam
        - TP2 tetiklendi → SL2 iptal, pozisyon tamamen kapandı
        - SL1 tetiklendi (TP1 öncesi) → TP1+TP2+SL2 iptal, tamamen kapandı
        - SL2 tetiklendi (TP1 sonrası) → TP2 iptal, tamamen kapandı
        """
        if not oco_pair.get('active'):
            return {'already_handled': True}

        try:
            symbol       = oco_pair['symbol']
            tp1_id       = oco_pair['tp1_order_id']
            tp2_id       = oco_pair['tp2_order_id']
            sl1_id       = oco_pair['sl1_order_id']
            sl2_id       = oco_pair['sl2_order_id']
            tp1_triggered = oco_pair.get('tp1_triggered', False)

            tp2_status = self.get_order_status(symbol, tp2_id)
            sl2_status = self.get_order_status(symbol, sl2_id)

            # TP2 tetiklendi → tamamen kapandı
            if tp2_status == 'Filled':
                self.cancel_order(symbol, sl2_id)
                oco_pair['active'] = False
                self.logger.info(f"{symbol} TP2 tetiklendi — pozisyon tamamen kapandı")
                return {'triggered': 'TP2'}

            # SL2 tetiklendi → tamamen kapandı (TP1 sonrası veya SL1 ile birlikte)
            if sl2_status in ['Filled', 'Triggered']:
                self.cancel_order(symbol, tp2_id)
                if not tp1_triggered:
                    self.cancel_order(symbol, tp1_id)
                oco_pair['active'] = False
                self.logger.info(f"{symbol} SL2 tetiklendi — pozisyon tamamen kapandı")
                return {'triggered': 'SL2'}

            # TP1 henüz tetiklenmediyse kontrol et
            if not tp1_triggered:
                tp1_status = self.get_order_status(symbol, tp1_id)
                sl1_status = self.get_order_status(symbol, sl1_id)

                # TP1 tetiklendi → SL1 iptal, devam
                if tp1_status == 'Filled':
                    self.cancel_order(symbol, sl1_id)
                    oco_pair['tp1_triggered'] = True
                    self.logger.info(f"{symbol} TP1 tetiklendi — SL1 iptal, TP2/SL2 devam ediyor")
                    return {'triggered': 'TP1', 'partial': True}

                # SL1 tetiklendi → her şeyi iptal et
                if sl1_status in ['Filled', 'Triggered']:
                    self.cancel_order(symbol, tp1_id)
                    self.cancel_order(symbol, tp2_id)
                    self.cancel_order(symbol, sl2_id)
                    oco_pair['active'] = False
                    self.logger.info(f"{symbol} SL1 tetiklendi — pozisyon tamamen kapandı")
                    return {'triggered': 'SL1'}

            return {'status': 'active'}

        except Exception as e:
            self.logger.error(f"OCO kontrol hatası: {e}")
            return {'error': str(e)}

    def get_order_status(self, symbol: str, order_id: str) -> str:
        """Emir durumunu sorgula"""
        try:
            result = self.client.get_open_orders(
                category="linear",
                symbol=symbol,
                orderId=order_id
            )
            orders = result['result']['list']
            if not orders:
                history = self.client.get_order_history(
                    category="linear",
                    symbol=symbol,
                    orderId=order_id
                )
                if history['result']['list']:
                    return history['result']['list'][0]['orderStatus']
                return 'NotFound'
            return orders[0]['orderStatus']
        except Exception as e:
            self.logger.error(f"Emir durum sorgu hatası: {e}")
            return 'Error'

    def cancel_order(self, symbol: str, order_id: str) -> None:
        """Emri iptal et"""
        try:
            self.client.cancel_order(
                category="linear",
                symbol=symbol,
                orderId=order_id
            )
            self.logger.info(f"Emir iptal edildi: {order_id}")
        except Exception as e:
            self.logger.warning(f"İptal hatası (zaten kapanmış olabilir): {e}")
