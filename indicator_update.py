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


# Usage
# 3x ATR için
df = atr_zigzag_two_columns(df, atr_col="atr", close_col="close", atr_mult=3, suffix="_3x")

df['pivot_up_3x'] = False
df['pivot_down_3x'] = False
df.loc[(df['low_pivot_confirmed_3x']) & (df['trend_13_50']== 'uptrend') & (atr_ranges[symbol][0] < df['pct_atr']) & (df['pct_atr'] < atr_ranges[symbol][1]), 'pivot_up_3x'] = True
df.loc[(df['high_pivot_confirmed_3x']) & (df['trend_13_50']== 'downtrend') & (atr_ranges[symbol][0] < df['pct_atr']) & (df['pct_atr'] < atr_ranges[symbol][1]), 'pivot_down_3x'] = True

df['entry_atr_steps_l'] = np.nan
df.loc[df['pivot_up_3x'], 'entry_atr_steps_l'] = ((df.loc[df['pivot_up_3x'], 'close'] - df.loc[df['pivot_up_3x'], 'low_pivot_filled_3x'] ) / df.loc[df['pivot_up_3x'], 'atr'])
    
df['entry_atr_steps_s'] = np.nan
df.loc[df['pivot_down_3x'], 'entry_atr_steps_s'] = ((df.loc[df['pivot_down_3x'], 'high_pivot_filled_3x'] - df.loc[df['pivot_down_3x'], 'close']) / df.loc[df['pivot_down'], 'atr'])

    
df.loc[(df['pivot_up_3x']) & (df['entry_atr_steps_l'] < 3.75), 'atr_steps_3x'] = 'long'
df.loc[(df['pivot_down_3x']) & (df['entry_atr_steps_s'] < 3.75), 'atr_steps_3x'] = 'short' 

# 2x ATR için
df = atr_zigzag_two_columns(df, atr_col="atr", close_col="close", atr_mult=2, suffix="_2x")
df['pivot_up_2x'] = False
df['pivot_down_2x'] = False
df.loc[(df['low_pivot_confirmed_2x']) & (df['trend_13_50']== 'uptrend') & (atr_ranges[symbol][0] < df['pct_atr']) & (df['pct_atr'] < atr_ranges[symbol][1]), 'pivot_up_2x'] = True
df.loc[(df['high_pivot_confirmed_2x']) & (df['trend_13_50']== 'downtrend') & (atr_ranges[symbol][0] < df['pct_atr']) & (df['pct_atr'] < atr_ranges[symbol][1]), 'pivot_down_2x'] = True

# For Entry 
# Dosyanın başına ekle
MAJOR_PAIRS_3X = ['BTCUSDT', 'ETHUSDT', 'XRPUSDT', 'DOGEUSDT', '1000PEPEUSDT', 'SOLUSDT']

def check_long_entry(row: Dict[str, Any], symbol: str) -> bool:
    atr_steps_col = 'atr_steps_3x' if symbol in MAJOR_PAIRS_3X else 'atr_steps_2x'
    return row[atr_steps_col] == 'long'

def check_short_entry(row: Dict[str, Any], symbol: str) -> bool:
    atr_steps_col = 'atr_steps_3x' if symbol in MAJOR_PAIRS_3X else 'atr_steps_2x'
    return row[atr_steps_col] == 'short'

def check_long_entry(row: Dict[str, Any], symbol: str) -> bool:
    # Sadece major pariteler long alabilir (3x ATR ile)
    if symbol in MAJOR_PAIRS_3X:
        return row['atr_steps_3x'] == 'long'
    else:
        return False  


