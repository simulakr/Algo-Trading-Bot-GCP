from typing import Dict, Optional, Any
from binance.client import Client
from exit_strategies import ExitStrategy
import logging
from config import LEVERAGE, RISK_PER_TRADE_USDT

class PositionManager:
    def __init__(self, client: Client):
        self.client = client
        self.exit_strategy = ExitStrategy(client)
        self.active_positions: Dict[str, Dict] = {}  # {symbol: position_data}
        self.logger = logging.getLogger(__name__)

    def open_position(self, symbol: str, direction: str, entry_price: float, pct_atr: float) -> Optional[Dict]:
        """
        Yeni pozisyon açar ve TP/SL emirlerini yerleştirir
        Args:
            symbol: İşlem çifti (Ör: 'SUIUSDT')
            direction: 'LONG' veya 'SHORT'
            entry_price: Giriş fiyatı
            pct_atr: Mevcut ATR'nin close price'a yüzdesi (örn: 2.0 = %2)
        Returns:
            Pozisyon bilgisi dict veya None (hata durumunda)
        """
        try:
            # Pozisyon büyüklüğünü hesapla (pct_atr kullanarak)
            quantity = self._calculate_position_size(entry_price, pct_atr, direction)

            # Market emri ile pozisyon aç
            order = self.client.futures_create_order(
                symbol=symbol,
                side='BUY' if direction == 'LONG' else 'SELL',
                type='MARKET',
                quantity=quantity,
                positionSide=direction
            )

            # Pozisyon bilgilerini oluştur
            position = {
                'symbol': symbol,
                'direction': direction,
                'entry_price': entry_price,
                'quantity': quantity,
                'current_pct_atr': pct_atr,  # Artık pct_atr saklanıyor
                'order_id': order['orderId']
            }

            # TP/SL emirlerini yerleştir (exit_strategies de pct_atr kullanacak şekilde güncellenecek)
            if self.exit_strategy._update_orders(position, *self.exit_strategy.calculate_levels(entry_price, pct_atr, direction)):
                self.active_positions[symbol] = position
                self.logger.info(f"{symbol} {direction} pozisyonu açıldı | Miktar: {quantity} | Risk: {RISK_PER_TRADE_USDT}$")
                return position

        except Exception as e:
            self.logger.error(f"{symbol} pozisyon açma hatası: {str(e)}")
            return None

    def _calculate_position_size(self, entry_price: float, pct_atr: float, direction: str) -> float:
        """
        Risk yönetimli pozisyon büyüklüğü hesaplar (pct_atr kullanarak)
        Args:
            entry_price: Giriş fiyatı
            pct_atr: ATR'nin fiyata yüzdesi (örn: 2.0 = %2)
            direction: 'LONG' veya 'SHORT'
        Returns:
            float: Alınacak miktar
        """
        stop_pct = pct_atr * (1 if direction == 'LONG' else 2)  # Long:1x, Short:2x ATR
        risk_amount = RISK_PER_TRADE_USDT * LEVERAGE
        quantity = (risk_amount) / (entry_price * (stop_pct / 100))
        return round(quantity, 3)  # 3 ondalık basamak

    # Diğer fonksiyonlar aynı kalacak (close_position, manage_positions vb.)
    def close_position(self, symbol: str, reason: str = "MANUAL_CLOSE") -> bool:
        """Aktif pozisyonu kapatır"""
        if symbol not in self.active_positions:
            return False

        position = self.active_positions[symbol]
        if self.exit_strategy._close_position(position, reason):
            del self.active_positions[symbol]
            return True
        return False

    def manage_positions(self, signals: Dict[str, Optional[str]]) -> None:
        """Tüm aktif pozisyonları yönetir"""
        for symbol, position in list(self.active_positions.items()):
            result = self.exit_strategy.manage_position(position, signals.get(symbol))
            if "CLOSED" in result:
                del self.active_positions[symbol]

    def get_active_position(self, symbol: str) -> Optional[Dict]:
        """Sembolün aktif pozisyon bilgisini döndürür"""
        return self.active_positions.get(symbol)

    def has_active_position(self, symbol: str) -> bool:
        """Sembol için aktif pozisyon var mı?"""
        return symbol in self.active_positions
