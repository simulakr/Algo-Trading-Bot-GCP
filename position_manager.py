from typing import Dict, Optional, Any
from pybit.unified_trading import HTTP
from exit_strategies import ExitStrategy
import logging
from config import LEVERAGE, RISK_PER_TRADE_USDT, ROUND_NUMBERS

logger = logging.getLogger(__name__)

class PositionManager:
    def __init__(self, client: HTTP):
        self.client = client
        self.exit_strategy = ExitStrategy(client)
        self.active_positions: Dict[str, Dict] = {}  # {symbol: position_data}
        self.logger = logging.getLogger(__name__)

    def open_position(self, symbol: str, direction: str, entry_price: float, atr_value: float, pct_atr: float) -> Optional[Dict]:
        """
        Yeni pozisyon açar ve limit TP/SL emirlerini yerleştirir (OCO mantığıyla)
        """
        try:
            # Eğer zaten pozisyon varsa kontrol et
            if symbol in self.active_positions:
                existing_direction = self.active_positions[symbol]['direction']
                
                # Aynı yönde sinyal (Senaryo 2a)
                if existing_direction == direction:
                    logger.info(f"{symbol} zaten {direction} pozisyonda - TP/SL güncelleniyor")
                    return self._update_tp_sl_only(symbol, direction, entry_price, atr_value, pct_atr)
                
                # Ters yönde sinyal (Senaryo 2b)
                else:
                    logger.info(f"{symbol} ters sinyal alındı ({existing_direction} → {direction}) - Pozisyon tersine dönüyor")
                    self.close_position(symbol, "REVERSE_SIGNAL")
                    # Devam et ve yeni pozisyon aç
            
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
            tp_price, sl_price = self.exit_strategy.calculate_levels(entry_price, atr_value, direction, symbol)
            logger.info(f"{symbol} TP/SL hesaplandı | TP: {tp_price} | SL: {sl_price}")
            
            # Limit TP/SL emirlerini gönder (YENİ)
            tp_sl_result = self.exit_strategy.set_limit_tp_sl(
                symbol=symbol,
                direction=direction,
                tp_price=tp_price,
                sl_price=sl_price,
                quantity=quantity
            )
    
            if tp_sl_result.get('success'):
                logger.info(f"{symbol} Limit TP/SL başarıyla ayarlandı")
                
                # Pozisyon bilgilerini kaydet (OCO pair dahil)
                position = {
                    'symbol': symbol,
                    'direction': direction,
                    'entry_price': entry_price,
                    'quantity': quantity,
                    'take_profit': tp_price,
                    'stop_loss': sl_price,
                    'current_pct_atr': pct_atr,
                    'order_id': order['result']['orderId'],
                    'oco_pair': tp_sl_result['oco_pair']  # YENİ: OCO tracking
                }
                self.active_positions[symbol] = position
                return position
            else:
                logger.warning(f"{symbol} TP/SL ayarlanamadı - Pozisyon kapatılıyor")
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

    def close_position(self, symbol: str, reason: str = "MANUAL") -> bool:
        """
        Pozisyonu kapatır ve TP/SL emirlerini iptal eder
        """
        try:
            if symbol not in self.active_positions:
                logger.warning(f"{symbol} kapatılacak pozisyon bulunamadı")
                return False
            
            position = self.active_positions[symbol]
            
            # TP/SL emirlerini iptal et
            if 'oco_pair' in position:
                logger.info(f"{symbol} TP/SL emirleri iptal ediliyor...")
                try:
                    self.exit_strategy.cancel_order(symbol, position['oco_pair']['tp_order_id'])
                    self.exit_strategy.cancel_order(symbol, position['oco_pair']['sl_order_id'])
                except Exception as e:
                    logger.warning(f"{symbol} TP/SL iptal hatası (zaten tetiklenmiş olabilir): {e}")
            
            # Pozisyonu market ile kapat
            close_side = "Sell" if position['direction'] == "LONG" else "Buy"
            
            order = self.client.place_order(
                category="linear",
                symbol=symbol,
                side=close_side,
                orderType="Market",
                qty=position['quantity'],
                reduceOnly=True
            )
            
            if order['retCode'] == 0:
                logger.info(f"{symbol} pozisyon kapatıldı | Sebep: {reason}")
                del self.active_positions[symbol]
                return True
            else:
                logger.error(f"{symbol} pozisyon kapatma hatası: {order['retMsg']}")
                return False
                
        except Exception as e:
            logger.error(f"{symbol} pozisyon kapatma hatası: {str(e)}")
            return False

    def _update_tp_sl_only(self, symbol: str, direction: str, entry_price: float, atr_value: float, pct_atr: float) -> Optional[Dict]:
        """
        Mevcut pozisyonun sadece TP/SL'sini günceller (Senaryo 2a)
        """
        try:
            position = self.active_positions[symbol]
            
            # Eski TP/SL emirlerini iptal et
            if 'oco_pair' in position:
                logger.info(f"{symbol} eski TP/SL emirleri iptal ediliyor...")
                self.exit_strategy.cancel_order(symbol, position['oco_pair']['tp_order_id'])
                self.exit_strategy.cancel_order(symbol, position['oco_pair']['sl_order_id'])
            
            # Yeni TP/SL seviyelerini hesapla
            tp_price, sl_price = self.exit_strategy.calculate_levels(entry_price, atr_value, direction, symbol)
            logger.info(f"{symbol} Yeni TP/SL hesaplandı | TP: {tp_price} | SL: {sl_price}")
            
            # Yeni limit TP/SL emirlerini gönder
            tp_sl_result = self.exit_strategy.set_limit_tp_sl(
                symbol=symbol,
                direction=direction,
                tp_price=tp_price,
                sl_price=sl_price,
                quantity=position['quantity']
            )
            
            if tp_sl_result.get('success'):
                # Pozisyon bilgilerini güncelle
                position['take_profit'] = tp_price
                position['stop_loss'] = sl_price
                position['current_pct_atr'] = pct_atr
                position['oco_pair'] = tp_sl_result['oco_pair']
                
                logger.info(f"{symbol} TP/SL başarıyla güncellendi")
                return position
            else:
                logger.error(f"{symbol} TP/SL güncellenemedi")
                return None
                
        except Exception as e:
            logger.error(f"{symbol} TP/SL güncelleme hatası: {str(e)}")
            return None
        
    # Requires OCO func.   
    def manage_positions(self, signals: Dict[str, Optional[str]], all_data: Dict[str, Optional[Dict]]) -> None:
        """Tüm aktif pozisyonları yönetir (Binance versiyonuyla aynı)"""
        for symbol, position in list(self.active_positions.items()):
            current_data = all_data.get(symbol)
            result = self.exit_strategy.manage_position(position, signals.get(symbol), current_data)
            if "CLOSED" in result:
                del self.active_positions[symbol]

    def get_active_position(self, symbol: str) -> Optional[Dict]:
        return self.active_positions.get(symbol)

    def has_active_position(self, symbol: str) -> bool:
        return symbol in self.active_positions

    def monitor_oco_orders(self):
        """
        Tüm aktif pozisyonların OCO emirlerini kontrol eder
        """
        for symbol, position in list(self.active_positions.items()):
            if 'oco_pair' in position and position['oco_pair']['active']:
                result = self.exit_strategy.check_and_cancel_oco(position['oco_pair'])
                
                if result.get('triggered'):
                    logger.info(f"{symbol} {result['triggered']} tetiklendi - Pozisyon kapatıldı")
                    # Pozisyonu listeden çıkar
                    del self.active_positions[symbol]
