from pybit.unified_trading import HTTP
from typing import Dict, Any, Optional, Tuple
import logging
from config import TP_ROUND_NUMBERS

class ExitStrategy:
    def __init__(self, bybit_client: HTTP):
        self.client = bybit_client
        self.logger = logging.getLogger(__name__)

    def calculate_levels(self, entry_price: float, atr_value: float, direction: str, symbol: str) -> Tuple[float, float]:
        """ATR değerine göre TP/SL seviyelerini hesaplar"""
        if direction == "LONG":
            take_profit = entry_price + (4 * atr_value)  # 🟢 Direct ATR add
            stop_loss = entry_price - (1 * atr_value)
        else:
            take_profit = entry_price - (4 * atr_value)
            stop_loss = entry_price + (2 * atr_value)
                
        round_to = TP_ROUND_NUMBERS.get(symbol, 3)
        
        return (round(take_profit, round_to), round(stop_loss, round_to))

    def manage_position(self, position: Dict[str, Any], current_signal: Optional[str] = None, current_data: Optional[Dict] = None) -> str:
        """Binance versiyonuyla aynı (sinyal mantığı değişmez)"""
        current_direction = position['direction']
        if current_signal and current_signal != current_direction:
            self._close_position(position, "REVERSE_SIGNAL")
            return "CLOSED_FOR_REVERSE"
        if current_signal and current_data:
            new_tp, new_sl = self.calculate_levels(
                position['entry_price'],
                current_data['atr'],
                current_direction,
                position['symbol']
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
                takeProfit=str(new_tp),
                stopLoss=str(new_sl),
                tpTriggerBy="LastPrice",
                slTriggerBy="MarkPrice"
                # tpLimitPrice ve slOrderType parametrelerini KALDIR
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
            order = self.client.place_order(
                category="linear",
                symbol=symbol,
                side="Sell" if position['direction'] == "LONG" else "Buy",
                orderType="Market",
                qty=str(position['quantity']),
                # positionIdx KALDIR 👈
                reduceOnly=True
            )
    
            if order['retCode'] == 0:
                self.logger.info(f"{symbol} pozisyonu kapatıldı. Sebep: {reason}")
                return True
            return False
    
        except Exception as e:
            self.logger.error(f"{symbol} pozisyon kapatma hatası: {str(e)}")
            return False
    
    def set_take_profit_stop_loss(self, symbol: str, direction: str, quantity: float, take_profit: float, stop_loss: float) -> bool:
        """TP ve SL emirlerini ayrıca gönder"""
        try:
            order = self.client.set_trading_stop(
                category="linear",
                symbol=symbol,
                # side ve positionIdx KALDIR 👈
                takeProfit=str(take_profit),
                stopLoss=str(stop_loss),
                tpTriggerBy="MarkPrice",
                slTriggerBy="MarkPrice"
                # positionIdx KALDIR 👈
            )
            return order['retCode'] == 0
        except Exception as e:
            self.logger.error(f"{symbol} TP/SL ayarlama hatası: {str(e)}")
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
