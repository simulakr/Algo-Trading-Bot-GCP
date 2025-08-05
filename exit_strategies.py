from binance.client import Client
from typing import Dict, Any, Optional, Tuple
import logging

class ExitStrategy:
    def __init__(self, binance_client: Client):
        self.client = binance_client
        self.logger = logging.getLogger(__name__)

    def calculate_levels(self, entry_price: float, pct_atr: float, direction: str) -> Tuple[float, float]:
        if direction == "LONG":
            take_profit = entry_price * (1 + (4 * pct_atr / 100))  # % cinsinden TP
            stop_loss = entry_price * (1 - (1 * pct_atr / 100))    # % cinsinden SL
        else:
            take_profit = entry_price * (1 - (4 * pct_atr / 100))
            stop_loss = entry_price * (1 + (2 * pct_atr / 100))
        return (round(take_profit, 4), round(stop_loss, 4))

    def manage_position(self, position: Dict[str, Any], current_signal: Optional[str] = None) -> str:
        """
        Pozisyon yönetimi (TP/SL güncelleme veya kapatma)
        Args:
            position: Aktif pozisyon bilgisi
            current_signal: Mevcut sinyal ('LONG'/'SHORT'/None)
        Returns:
            Durum mesajı ('UPDATED', 'CLOSED_FOR_REVERSE', vb.)
        """
        current_direction = position['direction']

        # Ters sinyal durumu
        if current_signal and current_signal != current_direction:
            self._close_position(position, "REVERSE_SIGNAL")
            return "CLOSED_FOR_REVERSE"

        # Aynı yönlü sinyalde TP/SL güncelleme
        if current_signal:
            new_tp, new_sl = self.calculate_levels(
                position['entry_price'],
                position['current_atr'],
                current_direction
            )
            self._update_orders(position, new_tp, new_sl)
            return "UPDATED"

        # Normal TP/SL kontrolü
        if self._check_price_hit(position):
            self._close_position(position, "TP/SL_HIT")
            return "CLOSED_FOR_TP_SL"

        return "NO_ACTION"

    def _update_orders(self, position: Dict[str, Any], new_tp: float, new_sl: float) -> bool:
        """Emirleri günceller"""
        symbol = position['symbol']
        try:
            # Önceki emirleri iptal et
            self.client.futures_cancel_order(
                symbol=symbol,
                orderId=position['tp_order_id']
            )
            self.client.futures_cancel_order(
                symbol=symbol,
                orderId=position['sl_order_id']
            )

            # Yeni TP emri (LIMIT)
            tp_order = self.client.futures_create_order(
                symbol=symbol,
                side='SELL' if position['direction'] == 'LONG' else 'BUY',
                type='LIMIT',
                quantity=position['quantity'],
                price=new_tp,
                timeInForce='GTC',
                positionSide=position['direction']
            )

            # Yeni SL emri (STOP_MARKET)
            sl_order = self.client.futures_create_order(
                symbol=symbol,
                side='SELL' if position['direction'] == 'LONG' else 'BUY',
                type='STOP_MARKET',
                quantity=position['quantity'],
                stopPrice=new_sl,
                positionSide=position['direction']
            )

            position.update({
                'take_profit': new_tp,
                'stop_loss': new_sl,
                'tp_order_id': tp_order['orderId'],
                'sl_order_id': sl_order['orderId']
            })
            return True

        except Exception as e:
            self.logger.error(f"{symbol} emir güncelleme hatası: {str(e)}")
            return False

    def _close_position(self, position: Dict[str, Any], reason: str) -> bool:
        """Pozisyonu tamamen kapatır"""
        symbol = position['symbol']
        try:
            # Emirleri iptal et
            self.client.futures_cancel_order(symbol=symbol, orderId=position['tp_order_id'])

            # Pozisyonu kapat
            self.client.futures_create_order(
                symbol=symbol,
                side='SELL' if position['direction'] == 'LONG' else 'BUY',
                type='MARKET',
                quantity=position['quantity'],
                positionSide=position['direction']
            )
            self.logger.info(f"{symbol} pozisyonu kapatıldı. Sebep: {reason}")
            return True

        except Exception as e:
            self.logger.error(f"{symbol} pozisyon kapatma hatası: {str(e)}")
            return False

    def _check_price_hit(self, position: Dict[str, Any]) -> bool:
        """TP/SL tetiklenme kontrolü"""
        ticker = self.client.futures_symbol_ticker(symbol=position['symbol'])
        current_price = float(ticker['price'])

        if position['direction'] == 'LONG':
            return current_price >= position['take_profit'] or current_price <= position['stop_loss']
        return current_price <= position['take_profit'] or current_price >= position['stop_loss']
