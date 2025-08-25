from typing import Dict, Optional, Any
from pybit.unified_trading import HTTP
from exit_strategies import ExitStrategy
import logging
from config import LEVERAGE, RISK_PER_TRADE_USDT

class PositionManager:
    def __init__(self, client: HTTP):
        self.client = client
        self.exit_strategy = ExitStrategy(client)
        self.active_positions: Dict[str, Dict] = {}  # {symbol: position_data}
        self.logger = logging.getLogger(__name__)

    def open_position(self, symbol: str, direction: str, entry_price: float, pct_atr: float) -> Optional[Dict]:
        """
        Yeni pozisyon açar ve TP/SL emirlerini yerleştirir (ByBit Futures)
        Args:
            symbol: İşlem çifti (Ör: 'SUIUSDT')
            direction: 'LONG' veya 'SHORT'
            entry_price: Giriş fiyatı
            pct_atr: Mevcut ATR'nin close price'a yüzdesi (örn: 2.0 = %2)
        Returns:
            Pozisyon bilgisi dict veya None (hata durumunda)
        """
        try:
            # Pozisyon büyüklüğünü hesapla
            quantity = self._calculate_position_size(entry_price, pct_atr, direction)

            # Market emri ile pozisyon aç
            order = self.client.place_order(
                category="linear",
                symbol=symbol,
                side="Buy" if direction == "LONG" else "Sell",
                orderType="Market",
                qty='0',  # 🟢 KRİTİK: qty=0 olmalı
                orderValue=str(risk_amount),  # 🟢 USDT cinsinden miktar (örn: '10')
                positionIdx=1 if direction == "LONG" else 2,
                reduceOnly=False
            )

            if order['retCode'] != 0:
                raise Exception(order['retMsg'])

            # Pozisyon bilgilerini oluştur
            position = {
                'symbol': symbol,
                'direction': direction,
                'entry_price': entry_price,
                'quantity': quantity,
                'current_pct_atr': pct_atr,
                'order_id': order['result']['orderId']
            }

            # TP/SL emirlerini yerleştir
            tp_price, sl_price = self.exit_strategy.calculate_levels(entry_price, pct_atr, direction)
            if self.exit_strategy._update_orders(position, tp_price, sl_price):
                self.active_positions[symbol] = position
                self.logger.info(f"{symbol} {direction} pozisyonu açıldı | Miktar: {quantity} | Risk: {RISK_PER_TRADE_USDT}$")
                return position

        except Exception as e:
            self.logger.error(f"{symbol} pozisyon açma hatası: {str(e)}")
            return None

    def _calculate_position_size(self, entry_price: float, pct_atr: float, direction: str) -> str:
        """Sadece sabit risk miktarını döndürür"""
        return str(RISK_PER_TRADE_USDT)

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
                positionIdx=1 if position['direction'] == "LONG" else 2,
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
