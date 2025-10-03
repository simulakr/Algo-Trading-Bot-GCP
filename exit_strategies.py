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
            take_profit = entry_price + (3 * atr_value)  # 🟢 Direct ATR add
            stop_loss = entry_price - (3 * atr_value)
        else:
            take_profit = entry_price - (3 * atr_value)
            stop_loss = entry_price + (3 * atr_value)
                
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
                current_data['close'],
                current_data['atr'],
                current_direction,
                position['symbol']
                )
            position['entry_price'] = current_data['close']
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
                slTriggerBy="MarkPrice",
                #tpOrderType="Limit",
                #tpLimitPrice=str(new_tp)
                # slOrderType parametresi yok.
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
            # Önce gerçek pozisyonu kontrol et
            real_positions = self.client.get_positions(category='linear', symbol=symbol)
            if real_positions['retCode'] == 0:
                real_pos = real_positions['result']['list'][0]
                real_size = float(real_pos.get('size', 0))
                
                if real_size == 0:
                    self.logger.info(f"{symbol} pozisyon zaten kapalı - hafızadan siliniyor. Sebep: {reason}")
                    return True  # Pozisyon zaten kapalı, başarılı sayılır
            
            # Normal kapatma işlemi
            order = self.client.place_order(
                category="linear",
                symbol=symbol,
                side="Sell" if position['direction'] == "LONG" else "Buy",
                orderType="Market",
                qty=str(position['quantity']),
                reduceOnly=True
            )
    
            if order['retCode'] == 0:
                self.logger.info(f"{symbol} pozisyonu kapatıldı. Sebep: {reason}")
                return True
            return False
    
        except Exception as e:
            # Eğer hata "pozisyon yok" türündeyse başarılı sayılır
            if "current position is zero" in str(e) or "110017" in str(e):
                self.logger.info(f"{symbol} pozisyon zaten kapalı. Sebep: {reason}")
                return True
            
            self.logger.error(f"{symbol} pozisyon kapatma hatası: {str(e)}")
            return False
    
    def set_take_profit_stop_loss(self, symbol: str, direction: str, quantity: float, take_profit: float, stop_loss: float) -> bool:
        """TP ve SL emirlerini ayrıca gönder"""
        try:
            order = self.client.set_trading_stop(
                category="linear",
                symbol=symbol,
                takeProfit=str(take_profit),
                stopLoss=str(stop_loss),
                tpTriggerBy="LastPrice",
                slTriggerBy="MarkPrice"
                # tpOrderType ve tpLimitPrice kaldır
            )
            return order['retCode'] == 0
        except Exception as e:
            self.logger.error(f"{symbol} TP/SL ayarlama hatası: {str(e)}")
            return False

    def set_limit_tp_sl(self, symbol, direction, tp_price, sl_price, quantity):
        """Limit TP ve Stop-Market SL emirleri oluştur (OCO mantığı ile)"""
        try:
            tp_side = "Sell" if direction == "LONG" else "Buy"
            trigger_direction = 2 if direction == "LONG" else 1
            
            # TP için LIMIT emri
            tp_order = self.client.place_order(
                category="linear",
                symbol=symbol,
                side=tp_side,
                orderType="Limit",
                qty=str(quantity),
                price=str(tp_price),
                reduceOnly=True,
                timeInForce="GTC"
            )
            
            # SL için STOP-MARKET emri
            sl_order = self.client.place_order(
                category="linear", 
                symbol=symbol,
                side=tp_side,
                orderType="Market",
                qty=str(quantity),
                triggerPrice=str(sl_price),
                triggerDirection=trigger_direction,
                triggerBy="LastPrice",
                reduceOnly=True
            )
            
            tp_order_id = tp_order['result']['orderId']
            sl_order_id = sl_order['result']['orderId']
            
            print(f"✓ TP Limit: {tp_price} (ID: {tp_order_id})")
            print(f"✓ SL Stop: {sl_price} (ID: {sl_order_id})")
            
            # OCO mantığı için emirleri kaydet
            oco_pair = {
                'symbol': symbol,
                'tp_order_id': tp_order_id,
                'sl_order_id': sl_order_id,
                'active': True
            }
            
            return {
                'tp_order_id': tp_order_id,
                'sl_order_id': sl_order_id,
                'oco_pair': oco_pair,
                'success': True
            }
            
        except Exception as e:
            print(f"❌ Limit TP/SL hatası: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}
    
    
    def check_and_cancel_oco(self, oco_pair):
        """Bir emir tetiklenirse diğerini iptal et (OCO mantığı)"""
        if not oco_pair.get('active'):
            return {'already_handled': True}
        
        try:
            symbol = oco_pair['symbol']
            tp_id = oco_pair['tp_order_id']
            sl_id = oco_pair['sl_order_id']
            
            # Her iki emrin durumunu kontrol et
            tp_status = self.get_order_status(symbol, tp_id)
            sl_status = self.get_order_status(symbol, sl_id)
            
            # TP tetiklendi mi? (Filled)
            if tp_status == 'Filled':
                print(f"✓ TP tetiklendi! SL iptal ediliyor...")
                self.cancel_order(symbol, sl_id)
                oco_pair['active'] = False
                return {'triggered': 'TP', 'cancelled': 'SL'}
            
            # SL tetiklendi mi? (Filled veya Triggered)
            if sl_status in ['Filled', 'Triggered']:
                print(f"✓ SL tetiklendi! TP iptal ediliyor...")
                self.cancel_order(symbol, tp_id)
                oco_pair['active'] = False
                return {'triggered': 'SL', 'cancelled': 'TP'}
            
            return {'status': 'both_active'}
            
        except Exception as e:
            print(f"❌ OCO kontrol hatası: {e}")
            return {'error': str(e)}
    
    
    def get_order_status(self, symbol, order_id):
        """Emir durumunu sorgula"""
        try:
            result = self.client.get_open_orders(
                category="linear",
                symbol=symbol,
                orderId=order_id
            )
            
            orders = result['result']['list']
            if not orders:
                # Açık emirlerde yoksa, geçmiş emirleri kontrol et
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
            print(f"❌ Emir durum sorgu hatası: {e}")
            return 'Error'
    
    
    def cancel_order(self, symbol, order_id):
        """Emri iptal et"""
        try:
            result = self.client.cancel_order(
                category="linear",
                symbol=symbol,
                orderId=order_id
            )
            print(f"✓ Emir iptal edildi: {order_id}")
            return result
        except Exception as e:
            print(f"❌ İptal hatası: {e}")
            return None
    
    def _check_price_hit(self, position: Dict[str, Any]) -> bool:
        """ByBit'te fiyat kontrolü"""
        try:
            ticker = self.client.get_tickers(
                category="linear",
                symbol=position['symbol']
            )
            current_price = float(ticker['result']['list'][0]['lastPrice'])
            
            tp = position.get('take_profit')
            sl = position.get('stop_loss')
            
            # None kontrolü
            if tp is None and sl is None:
                return False
            
            if position['direction'] == 'LONG':
                # TP kontrolü
                if tp is not None and current_price >= tp:
                    return True
                # SL kontrolü  
                if sl is not None and current_price <= sl:
                    return True
            else:  # SHORT
                # TP kontrolü
                if tp is not None and current_price <= tp:
                    return True
                # SL kontrolü
                if sl is not None and current_price >= sl:
                    return True
                    
            return False
        except Exception as e:
            self.logger.error(f"{position['symbol']} fiyat kontrol hatası: {str(e)}")
            return False
