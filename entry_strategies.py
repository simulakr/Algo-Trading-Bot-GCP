from typing import Dict, Any, Tuple

MAJOR_PAIRS_3X = ['BTCUSDT']

def check_long_entry(row: Dict[str, Any], symbol: str) -> bool:
    atr_steps_col = 'pivot_go_up_3x' if symbol in MAJOR_PAIRS_3X else 'pivot_go_up_2x'
    return row[atr_steps_col] == True

def check_short_entry(row: Dict[str, Any], symbol: str) -> bool:
    atr_steps_col = 'pivot_go_down_3x' if symbol in MAJOR_PAIRS_3X else 'pivot_go_down_2x'
    return row[atr_steps_col] == True


