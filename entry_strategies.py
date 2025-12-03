from typing import Dict, Any, Tuple

LONG_PAIRS_3X = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT','XRPUSDT']
SHORT_PAIRS_3X = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT','XRPUSDT','DOGEUSDT']

def check_long_entry(row: Dict[str, Any], symbol: str) -> bool:
    if symbol in LONG_PAIRS_3X:
        return row['pivot_go_up_3x'] == True
    return False

def check_short_entry(row: Dict[str, Any], symbol: str) -> bool:
    atr_steps_col = 'pivot_go_down_3x' if symbol in SHORT_PAIRS_3X else 'pivot_go_down_2x'
    return row[atr_steps_col] == True


