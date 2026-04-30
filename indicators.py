import numpy as np
import pandas as pd
from config import atr_ranges,Z_INDICATOR_PARAMS, Z_RANGES
import warnings
warnings.filterwarnings('ignore', category=FutureWarning)

# --- ATR ---
def calculate_atr(price_data, window=14):
    high = price_data['high']
    low = price_data['low']
    close = price_data['close']
    previous_close = close.shift(1)
    tr1 = high - low
    tr2 = abs(high - previous_close)
    tr3 = abs(low - previous_close)
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.ewm(alpha=1/window, adjust=False).mean()
    return atr

def atr_zigzag_two_columns(df, atr_col="atr", close_col="close", atr_mult=1, suffix=""): 
    closes = df[close_col].values
    atrs = df[atr_col].values

    high_pivot = [None] * len(df)
    low_pivot = [None] * len(df)
    high_pivot_atr = [None] * len(df)
    low_pivot_atr = [None] * len(df)
    high_pivot_confirmed = [0] * len(df)
    low_pivot_confirmed = [0] * len(df)
    pivot_bars_ago = [None] * len(df)

    last_pivot = closes[0]
    last_atr = atrs[0]
    last_pivot_idx = 0
    direction = None

    for i in range(1, len(df)):
        price = closes[i]
        atr = atrs[i] * atr_mult

        if direction is None:
            if price >= last_pivot + atr:
                direction = "up"
                last_pivot = closes[last_pivot_idx]
                high_pivot[last_pivot_idx] = last_pivot
                high_pivot_atr[last_pivot_idx] = atrs[last_pivot_idx]
            elif price <= last_pivot - atr:
                direction = "down"
                last_pivot = closes[last_pivot_idx]
                low_pivot[last_pivot_idx] = last_pivot
                low_pivot_atr[last_pivot_idx] = atrs[last_pivot_idx]

        elif direction == "up":
            if price <= (last_pivot - atr):
                high_pivot[last_pivot_idx] = last_pivot
                high_pivot_atr[last_pivot_idx] = atrs[last_pivot_idx]
                high_pivot_confirmed[i] = 1
                pivot_bars_ago[i] = i - last_pivot_idx

                direction = "down"
                last_pivot = price
                last_pivot_idx = i
            elif price > last_pivot:
                last_pivot = price
                last_pivot_idx = i

        elif direction == "down":
            if price >= (last_pivot + atr):
                low_pivot[last_pivot_idx] = last_pivot
                low_pivot_atr[last_pivot_idx] = atrs[last_pivot_idx]
                low_pivot_confirmed[i] = 1
                pivot_bars_ago[i] = i - last_pivot_idx

                direction = "up"
                last_pivot = price
                last_pivot_idx = i
            elif price < last_pivot:
                last_pivot = price
                last_pivot_idx = i

    # Sütun isimlerine suffix ekle
    df[f"high_pivot{suffix}"] = high_pivot
    df[f"low_pivot{suffix}"] = low_pivot
    df[f"high_pivot_atr{suffix}"] = high_pivot_atr
    df[f"low_pivot_atr{suffix}"] = low_pivot_atr
    df[f"high_pivot_confirmed{suffix}"] = high_pivot_confirmed
    df[f"low_pivot_confirmed{suffix}"] = low_pivot_confirmed
    df[f"pivot_bars_ago{suffix}"] = pivot_bars_ago

    # Forward fill işlemleri - suffix eklenmiş isimlerle
    df[f"high_pivot_filled{suffix}"] = df[f"high_pivot{suffix}"].ffill()
    df[f"low_pivot_filled{suffix}"] = df[f"low_pivot{suffix}"].ffill()
    df[f"high_pivot_atr_filled{suffix}"] = df[f"high_pivot_atr{suffix}"].ffill()
    df[f"low_pivot_atr_filled{suffix}"] = df[f"low_pivot_atr{suffix}"].ffill()

    # High pivot confirmed - suffix ile
    high_temp = df[f"high_pivot_confirmed{suffix}"].replace(0, np.nan)
    high_temp = high_temp.ffill()
    df[f"high_pivot_confirmed_filled{suffix}"] = high_temp.fillna(0).astype(int)
    
    # Low pivot confirmed - suffix ile
    low_temp = df[f"low_pivot_confirmed{suffix}"].replace(0, np.nan)
    low_temp = low_temp.ffill()
    df[f"low_pivot_confirmed_filled{suffix}"] = low_temp.fillna(0).astype(int)

    # Pivot bars ago filled
    pivot_bars_filled = []
    last_valid_value = None
    last_valid_index = None

    for i, value in enumerate(pivot_bars_ago):
        if value is not None:
            last_valid_value = value
            last_valid_index = i
            pivot_bars_filled.append(value)
        elif last_valid_value is not None:
            new_value = last_valid_value + (i - last_valid_index)
            pivot_bars_filled.append(new_value)
        else:
            pivot_bars_filled.append(None)

    df[f"pivot_bars_ago_filled{suffix}"] = pivot_bars_filled

    return df

def calculate_z(df, symbol):
    
    if symbol not in Z_RANGES:
        raise ValueError(f"Z_RANGES'de {symbol} için değer tanımlanmamış!")
  
    pct_min, pct_max = Z_RANGES[symbol]  
    atr_mult = Z_INDICATOR_PARAMS['atr_multiplier']

    z = np.minimum(
        np.maximum(
            df['close'] * pct_min / 100,
            atr_mult * df['atr']
        ),
        df['close'] * pct_max / 100
    )
    
    return z

# --- Calculations ---
def calculate_indicators(df, symbol):
    df['atr'] = calculate_atr(df)
    df['pct_atr'] = (df['atr'] / df['close']) * 100
    
    df['z'] = calculate_z(df, symbol=symbol)
    df['pct_z'] = (df['z'] / df['close']) * 100
    

    df = atr_zigzag_two_columns(df, atr_col="z", close_col="close", atr_mult=2, suffix='_2x')
    #df = atr_zigzag_two_columns(df, atr_col="z", close_col="close", atr_mult=3, suffix='_3x')

    df.loc[df['high_pivot_filled_2x'] < df['high_pivot_filled_2x'].shift(1), 'high_structure_2x'] = 'LH'
    df.loc[df['high_pivot_filled_2x'] > df['high_pivot_filled_2x'].shift(1), 'high_structure_2x'] = 'HH'
    df.loc[df['low_pivot_filled_2x'] < df['low_pivot_filled_2x'].shift(1), 'low_structure_2x'] = 'LL'
    df.loc[df['low_pivot_filled_2x'] > df['low_pivot_filled_2x'].shift(1), 'low_structure_2x'] = 'HL'
    
    df['high_structure_2x'] = df['high_structure_2x'].ffill().fillna('HH')
    df['low_structure_2x'] = df['low_structure_2x'].ffill().fillna('LL')
    
    df['pivot_go_breakout_2x'] = False
    df['pivot_go_breakdown_2x'] = False

    long_break_condition = (df['high_pivot_filled_2x'] + 0.1*df['z'])
    short_break_condition = (df['low_pivot_filled_2x'] - 0.1*df['z']) 
    
    df.loc[(df['low_pivot_confirmed_2x']) & 
           (df['low_structure_2x']=='HL') & 
           (df['high_structure_2x']!='HH') & 
           (df['high_pivot_filled_2x'].notna()) &  
           (df['close'] > long_break_condition) & 
           (atr_ranges[symbol][0] < df['pct_atr']) & 
           (df['pct_atr'] < atr_ranges[symbol][1]), 'pivot_go_breakout_2x'] = True
    
    df.loc[(df['high_pivot_confirmed_2x']) & 
           (df['high_structure_2x']=='LH') & 
           (df['low_structure_2x']!='LL') & 
           (df['low_pivot_filled_2x'].notna()) &  
           (df['close'] < short_break_condition) & 
           (atr_ranges[symbol][0] < df['pct_atr']) & 
           (df['pct_atr'] < atr_ranges[symbol][1]), 'pivot_go_breakdown_2x'] = True
    
    low_atr = atr_ranges[symbol][0]
    high_atr = atr_ranges[symbol][1]
    
    # NaN Control long conditions
    long_shift_condition = pd.Series(True, index=df.index)
    for i in range(1, 6):
        long_shift_condition &= (df['close'].shift(i) < long_break_condition)
    
    short_shift_condition = pd.Series(True, index=df.index)
    for i in range(1, 6):
        short_shift_condition &= (df['close'].shift(i) > short_break_condition)
    
    second_long_condition = (
        (df['low_structure_2x'] == 'HL') & 
        long_shift_condition & 
        (df['high_structure_2x'] != 'HH') & 
        (df['high_pivot_filled_2x'].notna()) & 
        (df['close'] > long_break_condition) & 
        (low_atr < df['pct_atr']) & 
        (df['pct_atr'] < high_atr) & 
        (df['pivot_go_breakout_2x'] == False)
    )   
    
    second_short_condition = (
        (df['low_structure_2x'] != 'LL') & 
        short_shift_condition & 
        (df['high_structure_2x'] == 'LH') & 
        (df['low_pivot_filled_2x'].notna()) & 
        (df['close'] < short_break_condition) & 
        (low_atr < df['pct_atr']) & 
        (df['pct_atr'] < high_atr) & 
        (df['pivot_go_breakdown_2x'] == False)
    )
    
    df.loc[second_long_condition,'pivot_go_breakout_2x'] = True
    df.loc[second_short_condition,'pivot_go_breakdown_2x'] = True
    
    return df
