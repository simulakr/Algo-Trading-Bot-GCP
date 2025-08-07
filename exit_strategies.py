from pybit.unified_trading import HTTP
from typing import Dict, Any, Optional, Tuple
import logging

class ExitStrategy:
    def __init__(self, bybit_client: HTTP):
        self.client = bybit_client
        self.logger = logging.getLogger(__name__)

    def calculate_levels(self, entry_price: float, pct_atr: float, direction: str) -> Tuple[float, float]:
        """Binance versiyonuyla tamamen aynı (seviye hesaplama değişmez)"""
        if direction == "LONG":
            take_profit = entry_price * (1 + (4 * pct_atr / 100))
            stop_loss = entry_price * (1 - (1 * pct_atr / 100))
        else:
            take_profit = entry_price * (1 - (4 * pct_atr / 100))
            stop_loss = entry_price * (1 + (2 * pct_atr / 100))
        return (round(take_profit, 4), round(stop_loss, 4))

    def manage_position(self, position: Dict[str, Any], current_signal: Optional[str] = None) -> str:
        """Binance versiyonuyla aynı (sinyal mantığı değişmez)"""
        current_direction = position['direction']

        if current_signal and current_signal != current_direction:
            self._close_position(position, "REVERSE_SIGNAL")
            return "CLOSED_FOR_REVERSE"

        if current_signal:
            new_tp, new_sl = self.calculate_levels(
                position['entry_price'],
                position['current_pct_atr'],
                current_direction
            )
            self._update_orders(position, new_tp, new_sl)
            return "UPDATED"

        if self._check_price_hit(position):
            self._close_position(position, "TP/SL_HIT")
            return "CLOSED_FOR_TP_SL"

        return "NO_ACTION"

    def _update_orders(self, position: Dict[str, Any], new_tp: float, new_sl: float) -> bool:
        """ByBit'e özel TP/SL emir güncelleme"""
        symbol = position['symbol']
        try:
            # ByBit'te TP/SL aynı anda gönderilebilir
            order = self.client.set_trading_stop(
                category="linear",
                symbol=symbol,
                positionIdx=1 if position['direction'] == "LONG" else 2,
                takeProfit=str(new_tp),
                stopLoss=str(new_sl),
                tpTriggerBy="MarkPrice" if position['direction'] == "LONG" else "LastPrice",
                slTriggerBy="MarkPrice" if position['direction'] == "LONG" else "LastPrice",
                tpLimitPrice=str(new_tp),  # Limit fiyatı TP için
                slOrderType="Market"  # SL her zaman marketle
            )

            if order['retCode'] != 0:
                raise Exception(order['retMsg'])

            position.update({
                'take_profit': new_tp,
                'stop_loss': new_sl
            })
            return True

        except Exception as e:
            self.logger.error(f"{symbol} TP/SL güncelleme hatası: {str(e)}")
            return False

    def _close_position(self, position: Dict[str, Any], reason: str) -> bool:
        """ByBit'e özel pozisyon kapatma"""
        symbol = position['symbol']
        try:
            # ByBit'te TP/SL otomatik iptal olur, ayrıca iptal etmeye gerek yok
            order = self.client.place_order(
                category="linear",
                symbol=symbol,
                side="Sell" if position['direction'] == "LONG" else "Buy",
                orderType="Market",
                qty=str(position['quantity']),
                positionIdx=1 if position['direction'] == "LONG" else 2,
                reduceOnly=True
            )

            if order['retCode'] == 0:
                self.logger.info(f"{symbol} pozisyonu kapatıldı. Sebep: {reason}")
                return True
            return False

        except Exception as e:
            self.logger.error(f"{symbol} pozisyon kapatma hatası: {str(e)}")
            return False

    def _check_price_hit(self, position: Dict[str, Any]) -> bool:
        """ByBit'te fiyat kontrolü"""
        try:
            ticker = self.client.get_tickers(
                category="linear",
                symbol=position['symbol']
            )
            current_price = float(ticker['result']['list'][0]['lastPrice'])

            if position['direction'] == 'LONG':
                return current_price >= position['take_profit'] or current_price <= position['stop_loss']
            return current_price <= position['take_profit'] or current_price >= position['stop_loss']

        except Exception as e:
            self.logger.error(f"{position['symbol']} fiyat kontrol hatası: {str(e)}")
            return False
