import numpy as np
import pandas as pd
from config import atr_ranges
import warnings
warnings.filterwarnings('ignore', category=FutureWarning)

# --- RSI ---
def calculate_rsi(price_data, window=14, price_col='close'):
    delta = price_data[price_col].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=window).mean()
    avg_loss = loss.rolling(window=window).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

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

# --- Bollinger Bands ---
def calculate_bollinger_bands(price_data, window=20, std_multiplier=2, price_col='close'):
    price = price_data[price_col]
    sma = price.rolling(window=window).mean()
    std = price.rolling(window=window).std()
    upper_band = sma + std_multiplier * std
    lower_band = sma - std_multiplier * std
    return pd.DataFrame({'bb_middle': sma, 'bb_upper': upper_band, 'bb_lower': lower_band})

# --- Donchian Channel ---
def calculate_donchian_channel(price_data, window=20):
    upper_band = price_data['high'].rolling(window=window).max()
    lower_band = price_data['low'].rolling(window=window).min()
    middle_band = (upper_band + lower_band) / 2
    return pd.DataFrame({'dc_upper': upper_band, 'dc_lower': lower_band, 'dc_middle': middle_band})

# --- SMA ---
def calculate_sma(price_data, window=50, price_col='close'):    
    sma = price_data[price_col].rolling(window=window).mean()
    return sma

# --- SMA Trend ---
def determine_sma_trend(price_data, short_window=50, long_window=200, price_col='close'):
    short_sma = price_data[price_col].rolling(window=short_window).mean()
    long_sma = price_data[price_col].rolling(window=long_window).mean()
    trend = np.where(short_sma > long_sma, 'uptrend', 'downtrend')
    return pd.Series(trend, index=price_data.index)

# --- Nadaraya-Watson Envelope ---
def calculate_nadaraya_watson_envelope_optimized(df, bandwidth=8.0, multiplier=3.0, source_col='close', window_size=50):
    n_bars = len(df)
    source_data = df[source_col].values
    def gauss(x, h): return np.exp(-(x**2) / (h * h * 2))
    weights = np.array([gauss(i, bandwidth) for i in range(window_size)])
    weights_sum = np.sum(weights)
    nw_out_arr = np.full(n_bars, np.nan)
    nw_lower_arr = np.full(n_bars, np.nan)
    nw_upper_arr = np.full(n_bars, np.nan)

    for i in range(n_bars):
        if i < window_size - 1:
            continue
        weighted_sum = np.dot(source_data[i - window_size + 1 : i + 1], weights[::-1])
        current_nw_out = weighted_sum / weights_sum
        nw_out_arr[i] = current_nw_out
        abs_diffs = np.abs(source_data[i - window_size + 1 : i + 1] - nw_out_arr[i - window_size + 1 : i + 1])
        current_mae = np.mean(abs_diffs) * multiplier
        nw_lower_arr[i] = current_nw_out - current_mae
        nw_upper_arr[i] = current_nw_out + current_mae

    return pd.DataFrame({'nw': nw_out_arr, 'nw_upper': nw_upper_arr, 'nw_lower': nw_lower_arr}, index=df.index)

# --- ADX ---
def add_adx(df, period=14):
    def _calculate_ema(series, p):
        ema_values = [np.nan] * len(series)
        if len(series) < p:
            return pd.Series(ema_values, index=series.index)
        ema_values[p - 1] = series.iloc[:p].mean()
        alpha = 2 / (p + 1)
        for i in range(p, len(series)):
            ema_values[i] = (series.iloc[i] * alpha) + (ema_values[i-1] * (1 - alpha))
        return pd.Series(ema_values, index=series.index)

    df = df.copy()
    df['prev_close'] = df['close'].shift(1)
    df['high_low'] = df['high'] - df['low']
    df['high_prev_close'] = abs(df['high'] - df['prev_close'])
    df['low_prev_close'] = abs(df['low'] - df['prev_close'])
    df['tr'] = df[['high_low', 'high_prev_close', 'low_prev_close']].max(axis=1)

    df['prev_high'] = df['high'].shift(1)
    df['prev_low'] = df['low'].shift(1)
    df['up_move'] = df['high'] - df['prev_high']
    df['down_move'] = df['prev_low'] - df['low']

    df['+dm'] = np.where((df['up_move'] > df['down_move']) & (df['up_move'] > 0), df['up_move'], 0)
    df['-dm'] = np.where((df['down_move'] > df['up_move']) & (df['down_move'] > 0), df['down_move'], 0)

    df['tr_ema'] = _calculate_ema(df['tr'], period)
    df['+dm_ema'] = _calculate_ema(df['+dm'], period)
    df['-dm_ema'] = _calculate_ema(df['-dm'], period)

    df['+di'] = (df['+dm_ema'] / df['tr_ema']) * 100
    df['-di'] = (df['-dm_ema'] / df['tr_ema']) * 100

    df['dx'] = (abs(df['+di'] - df['-di']) / (df['+di'] + df['-di'])) * 100
    df['adx'] = _calculate_ema(df['dx'], period)

    return df

# --- Candle Analysis ---
def candle(df):
    return 'green' if df['close'] > df['open'] else 'red'

def classify_strength(row):
    if row['close'] > row['open']:
        if row['candle_strength'] > 1.1:
            return 'strong_bullish'
        elif row['candle_strength'] > 0.7:
            return 'medium_bullish'
        else:
            return 'weak_bullish'
    else:
        if row['candle_strength'] > 1.1:
            return 'strong_bearish'
        elif row['candle_strength'] > 0.7:
            return 'medium_bearish'
        else:
            return 'weak_bearish'

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

def bb_touch_signal(df, touch_count=1, trend_filter=False, trend_col='trend_50_200', trend_direction='uptrend'):
    """
    Bollinger Band üst/alt temasına göre sinyal üretir.

    Returns:
        signal_long, signal_short: pd.Series
    """
    df['bb_touch_upper'] = df['high'] >= df['bb_upper']
    df['bb_touch_lower'] = df['low'] <= df['bb_lower']

    touch_upper = sum([df['bb_touch_upper'].shift(i + 1) for i in range(touch_count)])
    touch_lower = sum([df['bb_touch_lower'].shift(i + 1) for i in range(touch_count)])

    signal_long = touch_upper >= touch_count
    signal_short = touch_lower >= touch_count

    if trend_filter:
        signal_long &= df[trend_col] == trend_direction
        signal_short &= df[trend_col] != trend_direction

    return pd.Series(signal_long, index=df.index), pd.Series(signal_short, index=df.index)


def dc_breakout_signal(df, dc_upper='dc_upper_50', dc_lower='dc_lower_50',
                       trend_filter=False, trend_col='trend_50_200', trend_direction='uptrend'):
    """
    Donchian Channel breakout sinyali.

    Returns:
        signal_long, signal_short: pd.Series
    """
    breakout_upper = df['high'] > df[dc_upper].shift(1)
    breakout_lower = df['low'] < df[dc_lower].shift(1)

    signal_long = breakout_upper
    signal_short = breakout_lower

    if trend_filter:
        signal_long &= df[trend_col] == trend_direction
        signal_short &= df[trend_col] != trend_direction

    return pd.Series(signal_long, index=df.index), pd.Series(signal_short, index=df.index)


def clean_signals(signal_series, window=10):
    """
    Son window bar içinde sinyal varsa, yeni sinyali engeller
    """
    cleaned = signal_series.copy()
    
    for i in range(len(signal_series)):
        if signal_series.iloc[i]:  # Eğer sinyal varsa
            # Önceki window barda sinyal var mı kontrol et
            start_idx = max(0, i - window)
            if signal_series.iloc[start_idx:i].any():
                cleaned.iloc[i] = False  # Sinyali temizle
                
    return cleaned

# --- Toplu Hesaplama ---
def calculate_indicators(df, symbol):
    df['rsi'] = calculate_rsi(df)
    df['atr'] = calculate_atr(df)

    bb = calculate_bollinger_bands(df)
    df[['bb_middle', 'bb_upper', 'bb_lower']] = bb

    for w in [20, 50]:
        dc = calculate_donchian_channel(df, window=w)
        df[f'dc_upper_{w}'] = dc['dc_upper']
        df[f'dc_lower_{w}'] = dc['dc_lower']
        df[f'dc_middle_{w}'] = dc['dc_middle']
        df[f'dc_position_ratio_{w}'] = (df['close'] - df[f'dc_lower_{w}']) / (df[f'dc_upper_{w}'] - df[f'dc_lower_{w}']) * 100
        df[f'dc_breakout_{w}'] = df['high'] > df[f'dc_upper_{w}']
        df[f'dc_breakdown_{w}'] = df['low'] < df[f'dc_lower_{w}']
    
    df['sma_20'] = calculate_sma(df,window=20)
    df['sma_50'] = calculate_sma(df,window=50)
    df['sma_200'] = calculate_sma(df,window=200)
    df['sma_800'] = calculate_sma(df,window=799)
    
    df['trend_50_200'] = determine_sma_trend(df, short_window=50, long_window=200)
    df['trend_13_50'] = determine_sma_trend(df, short_window=13, long_window=50)

    nw = calculate_nadaraya_watson_envelope_optimized(df)
    df[['nw', 'nw_upper', 'nw_lower']] = nw

    df['candle'] = df.apply(candle, axis=1)
    df['candle_body'] = abs(df['close'] - df['open'])
    df['candle_strength'] = df['candle_body'] / df['atr']
    df['candle_class'] = df.apply(classify_strength, axis=1)

    df = add_adx(df)
    df['pct_atr'] = df['atr'] / df['close'] * 100

       
    # DC 50 breakout
    long_dc50, short_dc50 = dc_breakout_signal(df, 'dc_upper_50', 'dc_lower_50', trend_filter=True)
    df['dc_breakout_50'] = long_dc50
    df['dc_breakdown_50'] = short_dc50
    df['dc_breakout_clean_50'] = clean_signals(long_dc50)
    df['dc_breakdown_clean_50'] = clean_signals(short_dc50)

    # BB3 touch
    long3, short3 = bb_touch_signal(df, touch_count=3, trend_filter=True)
    df['bb_3_touch_long'] = long3
    df['bb_3_touch_short'] = short3
    df['bb_3_touch_long_clean'] = clean_signals(long3)
    df['bb_3_touch_short_clean'] = clean_signals(short3)
    
    df = atr_zigzag_two_columns(df, atr_col="atr", close_col="close", atr_mult=2, suffix='_2x')
    df = atr_zigzag_two_columns(df, atr_col="atr", close_col="close", atr_mult=3, suffix='_3x')

    df.loc[df['high_pivot_filled_2x'] < df['high_pivot_filled_2x'].shift(1), 'high_structure_2x'] = 'LH'
    df.loc[df['high_pivot_filled_2x'] > df['high_pivot_filled_2x'].shift(1), 'high_structure_2x'] = 'HH'
    df.loc[df['low_pivot_filled_2x'] < df['low_pivot_filled_2x'].shift(1), 'low_structure_2x'] = 'LL'
    df.loc[df['low_pivot_filled_2x'] > df['low_pivot_filled_2x'].shift(1), 'low_structure_2x'] = 'HL'
    
    df['high_structure_2x'] = df['high_structure_2x'].ffill().fillna('HH')
    df['low_structure_2x'] = df['low_structure_2x'].ffill().fillna('LL')
    
    df.loc[df['high_pivot_filled_3x'] < df['high_pivot_filled_3x'].shift(1), 'high_structure_3x'] = 'LH'
    df.loc[df['high_pivot_filled_3x'] > df['high_pivot_filled_3x'].shift(1), 'high_structure_3x'] = 'HH'
    df.loc[df['low_pivot_filled_3x'] < df['low_pivot_filled_3x'].shift(1), 'low_structure_3x'] = 'LL'
    df.loc[df['low_pivot_filled_3x'] > df['low_pivot_filled_3x'].shift(1), 'low_structure_3x'] = 'HL'
    
    df['high_structure_3x'] = df['high_structure_3x'].ffill().fillna('HH')
    df['low_structure_3x'] = df['low_structure_3x'].ffill().fillna('LL')
    
    df['pivot_go_up_2x'] = False
    df['pivot_go_down_2x'] = False
    df.loc[(df['low_pivot_confirmed_2x']) & (df['low_structure_2x']=='HL') & (df['high_structure_2x']=='HH') & (df['trend_50_200']== 'uptrend') & (df['close'] < df['nw_upper']) & (atr_ranges[symbol][0] < df['pct_atr']) & (df['pct_atr'] < atr_ranges[symbol][1]), 'pivot_go_up_2x'] = True
    df.loc[(df['high_pivot_confirmed_2x']) & (df['high_structure_2x']=='LH') & (df['low_structure_2x']=='LL') & (df['trend_50_200']== 'downtrend') & (df['close'] > df['nw_lower']) & (atr_ranges[symbol][0] < df['pct_atr']) & (df['pct_atr'] < atr_ranges[symbol][1]), 'pivot_go_down_2x'] = True
    
    df['pivot_go_up_3x'] = False
    df['pivot_go_down_3x'] = False
    df.loc[(df['low_pivot_confirmed_3x']) & (df['low_structure_3x']=='HL') & (df['high_structure_3x']=='HH') & (df['trend_50_200']== 'uptrend') & (df['close'] < df['nw_upper']) & (atr_ranges[symbol][0] < df['pct_atr']) & (df['pct_atr'] < atr_ranges[symbol][1]), 'pivot_go_up_3x'] = True
    df.loc[(df['high_pivot_confirmed_3x']) & (df['high_structure_3x']=='LH') & (df['low_structure_3x']=='LL') & (df['trend_50_200']== 'downtrend') & (df['close'] > df['nw_lower']) & (atr_ranges[symbol][0] < df['pct_atr']) & (df['pct_atr'] < atr_ranges[symbol][1]), 'pivot_go_down_3x'] = True
                 
    return df
