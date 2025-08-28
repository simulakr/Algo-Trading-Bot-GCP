from typing import Dict, Optional, Any
from pybit.unified_trading import HTTP
from exit_strategies import ExitStrategy
import logging
from config import LEVERAGE, RISK_PER_TRADE_USDT, ROUND_NUMBERS

class PositionManager:
    def __init__(self, client: HTTP):
        self.client = client
        self.exit_strategy = ExitStrategy(client)
        self.active_positions: Dict[str, Dict] = {}  # {symbol: position_data}
        self.logger = logging.getLogger(__name__)

    def open_position(self, symbol: str, direction: str, entry_price: float, pct_atr: float) -> Optional[Dict]:
        """
        Yeni pozisyon açar ve TP/SL emirlerini yerleştirir
        """
        try:
            # Pozisyon büyüklüğünü hesapla
            quantity = self._calculate_position_size(symbol, entry_price)
            logger.info(f"{symbol} {direction} pozisyon hesaplandı | Miktar: {quantity}")
            
            # Market emri ile pozisyon aç
            order = self.client.place_order(
                category="linear",
                symbol=symbol,
                side="Buy" if direction == "LONG" else "Sell",
                orderType="Market",
                qty=quantity,
                reduceOnly=False
            )
    
            if order['retCode'] != 0:
                raise Exception(f"Pozisyon açma hatası: {order['retMsg']}")
    
            logger.info(f"{symbol} {direction} pozisyon açıldı | Miktar: {quantity} | Entry: {entry_price}")
    
            # TP/SL seviyelerini hesapla
            tp_price, sl_price = self.exit_strategy.calculate_levels(entry_price, df['atr'].iloc[-1], direction)
            logger.info(f"{symbol} TP/SL hesaplandı | TP: {tp_price} | SL: {sl_price} | Risk: {pct_atr}%")
            
            # TP/SL emirlerini gönder
            tp_sl_success = self.exit_strategy.set_take_profit_stop_loss(
                symbol=symbol,
                direction=direction,
                quantity=quantity,
                take_profit=tp_price,
                stop_loss=sl_price
            )
    
            if tp_sl_success:
                logger.info(f"{symbol} TP/SL başarıyla ayarlandı")
                # Pozisyon bilgilerini kaydet
                position = {
                    'symbol': symbol,
                    'direction': direction,
                    'entry_price': entry_price,
                    'quantity': quantity,
                    'take_profit': tp_price,
                    'stop_loss': sl_price,
                    'current_pct_atr': pct_atr,
                    'order_id': order['result']['orderId']
                }
                self.active_positions[symbol] = position
                return position
            else:
                logger.warning(f"{symbol} TP/SL ayarlanamadı - Pozisyon kapatılıyor")
                # TP/SL ayarlanamazsa pozisyonu kapat
                self.close_position(symbol, "TP_SL_FAILED")
                return None
    
        except Exception as e:
            logger.error(f"{symbol} pozisyon açma hatası: {str(e)}")
            return None

    def _calculate_position_size(self, symbol: str, entry_price: float) -> str:
        """Sabit risk miktarına göre her sembol için quantity döndürür"""
        raw_quantity = RISK_PER_TRADE_USDT * LEVERAGE / entry_price
        quantity = round(raw_quantity, ROUND_NUMBERS[symbol])
        return str(quantity)

    def close_position(self, symbol: str, reason: str = "MANUAL_CLOSE") -> bool:
        """Aktif pozisyonu kapatır (ByBit)"""
        if symbol not in self.active_positions:
            return False

        position = self.active_positions[symbol]
        try:
            # Market emriyle pozisyon kapat
            order = self.client.place_order(
                category="linear",
                symbol=symbol,
                side="Sell" if position['direction'] == "LONG" else "Buy",
                orderType="Market",
                qty=str(position['quantity']),
                # positionIdx=1 if position['direction'] == "LONG" else 2,
                reduceOnly=True
            )

            if order['retCode'] == 0:
                del self.active_positions[symbol]
                self.logger.info(f"{symbol} pozisyonu kapatıldı | Sebep: {reason}")
                return True
            return False

        except Exception as e:
            self.logger.error(f"{symbol} pozisyon kapatma hatası: {str(e)}")
            return False

    def update_existing_position(self, symbol: str, data: Dict):
        """Mevcut pozisyonun TP/SL seviyelerini güncelle"""
        position = self.get_active_position(symbol)
        if position:
            new_tp, new_sl = self.exit_strategy.calculate_levels(
                position['entry_price'],
                data['pct_atr'],
                position['direction']
            )
            self.exit_strategy._update_orders(position, new_tp, new_sl)
        
    def manage_positions(self, signals: Dict[str, Optional[str]]) -> None:
        """Tüm aktif pozisyonları yönetir (Binance versiyonuyla aynı)"""
        for symbol, position in list(self.active_positions.items()):
            result = self.exit_strategy.manage_position(position, signals.get(symbol))
            if "CLOSED" in result:
                del self.active_positions[symbol]

    def get_active_position(self, symbol: str) -> Optional[Dict]:
        return self.active_positions.get(symbol)

    def has_active_position(self, symbol: str) -> bool:
        return symbol in self.active_positions
