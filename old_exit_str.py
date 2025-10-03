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
