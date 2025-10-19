from typing import Dict, Any, Tuple

def check_long_entry(row: Dict[str, Any]) -> bool:
    return row['atr_steps']=='long'

def check_short_entry(row: Dict[str, Any]) -> bool:
    return row['atr_steps']=='short'
