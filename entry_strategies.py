from typing import Dict, Any, Tuple

def check_long_entry(row: Dict[str, Any]) -> bool:
    return row['low_pivot_confirmed']==True

def check_short_entry(row: Dict[str, Any]) -> bool:
    return row['high_pivot_confirmed']==True
