from typing import Dict, Any, Tuple

def check_long_entry(row: Dict[str, Any]) -> bool:
    return row['bb_3_touch_long_clean']==True

def check_short_entry(row: Dict[str, Any]) -> bool:
    return row['bb_3_touch_short_clean']==True
