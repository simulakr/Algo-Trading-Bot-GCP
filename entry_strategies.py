from typing import Dict, Any, Tuple

# Sembol bazlı ATR aralıkları (ByBit için de aynı kalabilir)
SYMBOL_ATR_RANGES = {
    'SOLUSDT': {
        'long': (0.44, 0.84),
        'short': (0.44, 0.84)
    },
    'PEPEUSDT': {
        'long': (0.74, 1.3),
        'short': (0.74, 1.3)
    },
    'SUIUSDT': {
        'long': (0.61, 1.13),
        'short': (0.61, 1.13)
    }
}

VALID_CANDLE_TYPES = {
    'long': ['weak_bearish', 'weak_bullish', 'medium_bullish', 'strong_bullish'],
    'short': ['weak_bullish', 'weak_bearish', 'medium_bearish', 'strong_bearish']
}

def _get_atr_range(symbol: str, direction: str) -> Tuple[float, float]:
    """Sembole ve yöne göre ATR aralığını döndürür (ByBit için değişiklik yok)"""
    return SYMBOL_ATR_RANGES.get(symbol, {}).get(direction, (0, 0))

def check_long_entry(row: Dict[str, Any], symbol: str) -> bool:
    """Long giriş koşullarını kontrol eder (ByBit için değişiklik yok)"""
    min_pct_atr, max_pct_atr = _get_atr_range(symbol, 'long')

    conditions = (
        row['dc_breakout_clean_50'] and
        (row['dc_position_ratio_20'] > 60) and
        (row['rsi'] > 50) and
        (row['close'] > row['nw']) and
        (row['close'] < row['nw_upper']) and
        (row['close'] > row['bb_middle']) and
        (row['adx'] > 25) and
        (row['adx'] < 60) and
        (row['candle_class'] in VALID_CANDLE_TYPES['long']) and
        (min_pct_atr < row['pct_atr'] < max_pct_atr)
    )

    return conditions

def check_short_entry(row: Dict[str, Any], symbol: str) -> bool:
    """Short giriş koşullarını kontrol eder (ByBit için değişiklik yok)"""
    min_pct_atr, max_pct_atr = _get_atr_range(symbol, 'short')

    conditions = (
        row['dc_breakdown_clean_50'] and
        (row['dc_position_ratio_20'] < 40) and
        (row['rsi'] < 50) and
        (row['close'] < row['bb_middle']) and
        (row['close'] < row['nw']) and
        (row['close'] > row['nw_lower']) and
        (row['adx'] > 25) and
        (row['adx'] < 60) and
        (row['candle_class'] in VALID_CANDLE_TYPES['short']) and
        (min_pct_atr < row['pct_atr'] < max_pct_atr)
    )

    return conditions
