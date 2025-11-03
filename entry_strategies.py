from typing import Dict, Any, Tuple

def check_long_entry(row: Dict[str, Any]) -> bool:
    return row['pivot_up_up']==True

def check_short_entry(row: Dict[str, Any]) -> bool:
    return row['pivot_down_down']==True
