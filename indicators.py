import numpy as np
import pandas as pd

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

# --- Toplu Hesaplama ---
def calculate_indicators(df):
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

    df['trend_50_200'] = determine_sma_trend(df, short_window=50, long_window=200)

    nw = calculate_nadaraya_watson_envelope_optimized(df)
    df[['nw', 'nw_upper', 'nw_lower']] = nw

    df['candle'] = df.apply(candle, axis=1)
    df['candle_body'] = abs(df['close'] - df['open'])
    df['candle_strength'] = df['candle_body'] / df['atr']
    df['candle_class'] = df.apply(classify_strength, axis=1)

    df = add_adx(df)
    df['pct_atr'] = df['atr'] / df['close'] * 100
    return df
