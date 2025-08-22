from typing import Dict, Any, Tuple

def check_long_entry(row: Dict[str, Any]) -> bool:
    return row['dc_order']=='long'

def check_short_entry(row: Dict[str, Any]) -> bool:
    return row['dc_order']=='short'
