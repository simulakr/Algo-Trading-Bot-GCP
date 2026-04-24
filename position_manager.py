from typing import Dict, Optional, Any
from pybit.unified_trading import HTTP
from exit_strategies import ExitStrategy
import logging
from config import LEVERAGE, RISK_PER_TRADE_USDT, ROUND_NUMBERS, DEFAULT_LEVERAGE, SYMBOL_SETTINGS, SL
import time

logger = logging.getLogger(__name__)


class PositionManager:
    def __init__(self, client: HTTP):
        self.client = client
        self.exit_strategy = ExitStrategy(client)
        self.active_positions: Dict[str, Dict] = {}
        self.logger = logging.getLogger(__name__)

    # ─── Ana Giriş Noktası ────────────────────────────────────────────────────

    def open_position(
        self,
        symbol:      str,
        direction:   str,
        entry_price: float,
        atr_value:   float,
        pct_atr:     float,
    ) -> Optional[Dict]:
        """
        Senaryo 1  → Pozisyon yok: yeni aç
        Senaryo 2a → Aynı yön: TP/SL güncelle
        Senaryo 2b → Ters yön: kapat + yeni aç
        """
        try:
            if symbol in self.active_positions:
                existing_direction = self.active_positions[symbol]['direction']

                if existing_direction == direction:
                    logger.info(f"{symbol} zaten {direction} pozisyonda — TP/SL güncelleniyor")
                    return self._update_tp_sl_only(symbol, direction, entry_price, atr_value, pct_atr)
                else:
                    logger.info(f"{symbol} ters sinyal ({existing_direction} → {direction}) — pozisyon kapatılıp yeni açılıyor")
                    self.close_position(symbol, "REVERSE_SIGNAL")

            return self._open_new_position(symbol, direction, entry_price, atr_value, pct_atr)

        except Exception as e:
            logger.error(f"{symbol} open_position hatası: {e}")
            return None

    # ─── Yeni Pozisyon ────────────────────────────────────────────────────────

    def _open_new_position(
        self,
        symbol:      str,
        direction:   str,
        entry_price: float,
        atr_value:   float,
        pct_atr:     float,
    ) -> Optional[Dict]:
        quantity = self._calculate_position_size(symbol, atr_value, entry_price)

        order = self.client.place_order(
            category="linear",
            symbol=symbol,
            side="Buy" if direction == "LONG" else "Sell",
            orderType="Market",
            qty=quantity,
            reduceOnly=False,
        )

        if order['retCode'] != 0:
            logger.error(f"{symbol} market emri hatası: {order['retMsg']}")
            return None

        logger.info(f"{symbol} {direction} pozisyon açıldı | Miktar: {quantity} | Entry: {entry_price}")

        time.sleep(1)
        if not self._verify_position_opened(symbol, direction, float(quantity)):
            logger.warning(f"{symbol} pozisyon doğrulanamadı — TP/SL ayarlanamayacak")
            return None

        tp1_price, tp2_price, sl_price = self.exit_strategy.calculate_levels(
            entry_price, atr_value, direction, symbol
        )
        logger.info(f"{symbol} TP1: {tp1_price} | TP2: {tp2_price} | SL: {sl_price}")

        tp_sl_result = self.exit_strategy.set_limit_tp_sl(
            symbol=symbol,
            direction=direction,
            tp1_price=tp1_price,
            tp2_price=tp2_price,
            sl_price=sl_price,
            quantity=quantity,
        )

        if not tp_sl_result.get('success'):
            logger.warning(f"{symbol} TP/SL ayarlanamadı — pozisyon kapatılıyor")
            self._emergency_close(symbol, direction, float(quantity))
            return None

        position = {
            'symbol':        symbol,
            'direction':     direction,
            'entry_price':   entry_price,
            'quantity':      quantity,
            'take_profit1':  tp1_price,
            'take_profit2':  tp2_price,
            'stop_loss':     sl_price,
            'current_pct_atr': pct_atr,
            'order_id':      order['result']['orderId'],
            'oco_pair':      tp_sl_result['oco_pair'],
        }
        self.active_positions[symbol] = position
        logger.info(f"{symbol} pozisyon kaydedildi | TP1: {tp1_price} | TP2: {tp2_price} | SL: {sl_price}")
        return position

    # ─── TP/SL Güncelleme ─────────────────────────────────────────────────────

    def _update_tp_sl_only(
        self,
        symbol:      str,
        direction:   str,
        entry_price: float,
        atr_value:   float,
        pct_atr:     float,
    ) -> Optional[Dict]:
        """
        Mevcut pozisyonun TP/SL'sini günceller.
        TP1 zaten tetiklenmişse sadece yarı miktar için yeni emir gönderir.
        """
        try:
            position  = self.active_positions[symbol]
            oco_pair  = position.get('oco_pair', {})
            tp1_done  = oco_pair.get('tp1_triggered', False)

            # Mevcut emirleri iptal et
            if oco_pair:
                logger.info(f"{symbol} eski TP/SL emirleri iptal ediliyor...")
                if not tp1_done:
                    self.exit_strategy.cancel_order(symbol, oco_pair.get('tp1_order_id'))
                    self.exit_strategy.cancel_order(symbol, oco_pair.get('sl1_order_id'))
                self.exit_strategy.cancel_order(symbol, oco_pair.get('tp2_order_id'))
                self.exit_strategy.cancel_order(symbol, oco_pair.get('sl2_order_id'))

            tp1_price, tp2_price, sl_price = self.exit_strategy.calculate_levels(
                entry_price, atr_value, direction, symbol
            )
            logger.info(f"{symbol} yeni TP1: {tp1_price} | TP2: {tp2_price} | SL: {sl_price}")

            # TP1 tetiklenmişse sadece yarı miktar kaldı
            if tp1_done:
                half_qty = str(round(float(position['quantity']) / 2, 8)).rstrip('0').rstrip('.')
                tp_sl_result = self.exit_strategy.set_limit_tp_sl(
                    symbol=symbol,
                    direction=direction,
                    tp1_price=tp1_price,   # bu aslında yeni TP2 görevi görüyor
                    tp2_price=tp2_price,   # kullanılmayacak ama imza için gerekli
                    sl_price=sl_price,
                    quantity=half_qty,
                    half_only=True,        # sadece TP2+SL2 gönder
                )
            else:
                tp_sl_result = self.exit_strategy.set_limit_tp_sl(
                    symbol=symbol,
                    direction=direction,
                    tp1_price=tp1_price,
                    tp2_price=tp2_price,
                    sl_price=sl_price,
                    quantity=position['quantity'],
                )

            if not tp_sl_result.get('success'):
                logger.error(f"{symbol} TP/SL güncellenemedi")
                return None

            position.update({
                'entry_price':     entry_price,
                'take_profit1':    tp1_price,
                'take_profit2':    tp2_price,
                'stop_loss':       sl_price,
                'current_pct_atr': pct_atr,
                'oco_pair':        tp_sl_result['oco_pair'],
            })
            logger.info(f"{symbol} TP/SL güncellendi")
            return position

        except Exception as e:
            logger.error(f"{symbol} TP/SL güncelleme hatası: {e}")
            return None

    # ─── Pozisyon Kapatma ─────────────────────────────────────────────────────

    def close_position(self, symbol: str, reason: str = "MANUAL") -> bool:
        """Pozisyonu market emriyle kapatır, tüm OCO emirlerini iptal eder."""
        try:
            if symbol not in self.active_positions:
                logger.warning(f"{symbol} kapatılacak pozisyon bulunamadı")
                return False

            position = self.active_positions[symbol]
            oco_pair = position.get('oco_pair', {})
            tp1_done = oco_pair.get('tp1_triggered', False)

            # Tüm açık emirleri iptal et
            if oco_pair:
                try:
                    if not tp1_done:
                        self.exit_strategy.cancel_order(symbol, oco_pair.get('tp1_order_id'))
                        self.exit_strategy.cancel_order(symbol, oco_pair.get('sl1_order_id'))
                    self.exit_strategy.cancel_order(symbol, oco_pair.get('tp2_order_id'))
                    self.exit_strategy.cancel_order(symbol, oco_pair.get('sl2_order_id'))
                except Exception as e:
                    logger.warning(f"{symbol} TP/SL iptal hatası (zaten tetiklenmiş olabilir): {e}")

            # TP1 tetiklendiyse kalan miktar yarı
            close_qty = position['quantity']
            if tp1_done:
                close_qty = str(round(float(position['quantity']) / 2, 8)).rstrip('0').rstrip('.')

            close_side = "Sell" if position['direction'] == "LONG" else "Buy"
            order = self.client.place_order(
                category="linear",
                symbol=symbol,
                side=close_side,
                orderType="Market",
                qty=close_qty,
                reduceOnly=True,
            )

            if order['retCode'] == 0:
                logger.info(f"{symbol} pozisyon kapatıldı | Sebep: {reason}")
                del self.active_positions[symbol]
                return True
            else:
                logger.error(f"{symbol} pozisyon kapatma hatası: {order['retMsg']}")
                return False

        except Exception as e:
            logger.error(f"{symbol} pozisyon kapatma hatası: {e}")
            return False

    # ─── Pozisyon Yönetim Döngüsü ─────────────────────────────────────────────

    def manage_positions(
        self,
        signals:  Dict[str, Optional[str]],
        all_data: Dict[str, Optional[Dict]],
    ) -> None:
        """
        Her mum sonunda çalışır:
        1. OCO kontrolü (TP/SL tetiklenme)
        2. Ters sinyal → kapat (yeni açılış main loop'ta)
        3. Aynı yön sinyali → TP/SL güncelle
        """
        # 1. OCO kontrolü
        self.monitor_oco_orders()

        # 2-3. Sinyal bazlı kontroller
        for symbol, position in list(self.active_positions.items()):
            current_signal    = signals.get(symbol)
            current_data      = all_data.get(symbol)
            current_direction = position['direction']

            if not current_signal:
                continue

            # Ters sinyal — sadece logla, kapatma main loop'ta open_position içinde olacak
            if current_signal != current_direction:
                logger.info(f"{symbol} ters sinyal ({current_direction} → {current_signal})")
                continue

            # Aynı yön sinyali → TP/SL güncelle
            if current_data:
                logger.info(f"{symbol} aynı yönde sinyal — TP/SL güncelleniyor")
                oco_pair = position.get('oco_pair', {})
                tp1_done = oco_pair.get('tp1_triggered', False)

                new_tp1, new_tp2, new_sl = self.exit_strategy.calculate_levels(
                    current_data['close'], current_data['z'], current_direction, symbol
                )

                # Mevcut emirleri iptal et
                if oco_pair:
                    if not tp1_done:
                        self.exit_strategy.cancel_order(symbol, oco_pair.get('tp1_order_id'))
                        self.exit_strategy.cancel_order(symbol, oco_pair.get('sl1_order_id'))
                    self.exit_strategy.cancel_order(symbol, oco_pair.get('tp2_order_id'))
                    self.exit_strategy.cancel_order(symbol, oco_pair.get('sl2_order_id'))

                # TP1 tetiklenmişse sadece yarı miktar için emir gönder
                if tp1_done:
                    half_qty = str(round(float(position['quantity']) / 2, 8)).rstrip('0').rstrip('.')
                    tp_sl_result = self.exit_strategy.set_limit_tp_sl(
                        symbol=symbol,
                        direction=current_direction,
                        tp1_price=new_tp1,
                        tp2_price=new_tp2,
                        sl_price=new_sl,
                        quantity=half_qty,
                        half_only=True,
                    )
                else:
                    tp_sl_result = self.exit_strategy.set_limit_tp_sl(
                        symbol=symbol,
                        direction=current_direction,
                        tp1_price=new_tp1,
                        tp2_price=new_tp2,
                        sl_price=new_sl,
                        quantity=position['quantity'],
                    )

                if tp_sl_result.get('success'):
                    position.update({
                        'entry_price':  current_data['close'],
                        'take_profit1': new_tp1,
                        'take_profit2': new_tp2,
                        'stop_loss':    new_sl,
                        'oco_pair':     tp_sl_result['oco_pair'],
                    })
                    logger.info(f"{symbol} TP/SL güncellendi | TP1: {new_tp1} | TP2: {new_tp2} | SL: {new_sl}")

    # ─── OCO Takibi ───────────────────────────────────────────────────────────

    def monitor_oco_orders(self) -> None:
        """
        Tüm aktif pozisyonların OCO emirlerini kontrol eder.
        TP1 kısmi tetiklenme durumunu yönetir.
        """
        logger.debug(f"monitor_oco_orders çalışıyor — Pozisyon sayısı: {len(self.active_positions)}")

        for symbol, position in list(self.active_positions.items()):
            if 'oco_pair' not in position:
                logger.debug(f"{symbol} — oco_pair yok, atlandı")
                continue

            oco_pair = position['oco_pair']

            if not oco_pair.get('active'):
                logger.debug(f"{symbol} — oco_pair aktif değil, atlandı")
                continue

            result = self.exit_strategy.check_and_cancel_oco(oco_pair)
            logger.debug(f"{symbol} — OCO sonuç: {result}")

            if result.get('triggered') == 'TP1':
                # Yarı pozisyon kapandı, devam ediyor
                # tp1_triggered=True zaten check_and_cancel_oco içinde set edildi
                logger.info(f"{symbol} TP1 tetiklendi — yarı pozisyon kapandı, TP2/SL2 devam ediyor")

            elif result.get('triggered') in ['TP2', 'SL1', 'SL2']:
                logger.info(f"{symbol} {result['triggered']} tetiklendi — pozisyon tamamen kapandı")
                del self.active_positions[symbol]

    # ─── Yardımcılar ──────────────────────────────────────────────────────────

    def _calculate_position_size(
        self,
        symbol:        str,
        atr_value:     float,
        entry_price:   float,
        sl_multiplier: int = SL,
    ) -> str:
        symbol_config = SYMBOL_SETTINGS.get(symbol, {})
        risk_amount   = symbol_config.get('risk', RISK_PER_TRADE_USDT)
        leverage      = symbol_config.get('leverage', DEFAULT_LEVERAGE)

        raw_quantity = risk_amount / (sl_multiplier * atr_value)
        quantity     = round(raw_quantity, ROUND_NUMBERS[symbol])

        self.logger.info(
            f"{symbol} pozisyon hesaplandı | "
            f"Risk: ${risk_amount} | Leverage: {leverage}x | "
            f"Entry: ${entry_price:.2f} | Quantity: {quantity}"
        )
        return str(quantity)

    def _verify_position_opened(
        self,
        symbol:       str,
        direction:    str,
        expected_qty: float,
        timeout:      float = 5.0,
    ) -> bool:
        """Pozisyonun exchange'e yansımasını bekler. Maks 5 saniye, 0.5s aralıklarla."""
        expected_side = 'Buy' if direction == 'LONG' else 'Sell'
        attempts      = int(timeout / 0.5)

        for attempt in range(attempts):
            positions = self.client.get_positions(category='linear', symbol=symbol)
            if positions['retCode'] == 0:
                for pos in positions['result']['list']:
                    pos_size = float(pos.get('size', 0))
                    pos_side = pos.get('side', '')
                    if pos_size > 0 and pos_side == expected_side:
                        if abs(pos_size - expected_qty) < expected_qty * 0.05:
                            logger.info(f"{symbol} pozisyon doğrulandı (deneme {attempt + 1}/{attempts})")
                            return True
            time.sleep(0.5)

        logger.error(f"{symbol} pozisyon {timeout}s içinde doğrulanamadı")
        return False

    def _emergency_close(self, symbol: str, direction: str, quantity: float) -> None:
        """TP/SL ayarlanamadığında pozisyonu acil kapatır."""
        close_side = "Sell" if direction == "LONG" else "Buy"
        self.client.place_order(
            category="linear",
            symbol=symbol,
            side=close_side,
            orderType="Market",
            qty=str(quantity),
            reduceOnly=True,
        )
        logger.warning(f"{symbol} acil kapatma yapıldı")

    # ─── Sorgular ─────────────────────────────────────────────────────────────

    def get_active_position(self, symbol: str) -> Optional[Dict]:
        return self.active_positions.get(symbol)

    def has_active_position(self, symbol: str) -> bool:
        return symbol in self.active_positions
