import numpy as np
import pandas as pd

""" Relative Strength Index (RSI)"""

def calculate_rsi(price_data, window=14, price_col='close'):
    """
    Correct RSI calculation.
    """
    delta = price_data[price_col].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(window=window).mean()
    avg_loss = loss.rolling(window=window).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi

""" Categorical RSI  """

def categorize_rsi(rsi_series):
    """
    Categorize RSI values into bins:
    0-30, 30-50, 50-70, 70-100

    Args:
        rsi_series (pd.Series): RSI values

    Returns:
        pd.Series: Categorical RSI bins
    """
    bins = [0, 30, 50, 70, 100]
    labels = ['oversold', 'below_avg', 'above_avg', 'overbought']
    return pd.cut(rsi_series, bins=bins, labels=labels, include_lowest=True)

""" Average True Range (ATR)"""

def calculate_atr(price_data, window=14):
    """
    Calculate ATR (Average True Range) using Wilder's RMA.

    Args:
        price_data (pd.DataFrame): DataFrame containing columns 'high', 'low', 'close'
        window (int): Lookback period (default: 14)

    Returns:
        pd.Series: ATR values
    """
    high = price_data['high']
    low = price_data['low']
    close = price_data['close']

    # Calculate True Range (TR)
    previous_close = close.shift(1)
    tr1 = high - low
    tr2 = abs(high - previous_close)
    tr3 = abs(low - previous_close)
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # ATR = RMA of True Range
    atr = true_range.ewm(alpha=1/window, adjust=False).mean()

    return atr

""" Bollinger Bands"""

def calculate_bollinger_bands(price_data, window=20, std_multiplier=2, price_col='close'):
    """
    Calculate Bollinger Bands.

    Args:
        price_data (pd.DataFrame): DataFrame containing OHLC prices
        window (int): Lookback period for SMA (default: 20)
        std_multiplier (float): Standard deviation multiplier (default: 2)
        price_col (str): Column name for price (default: 'close')

    Returns:
        pd.DataFrame: DataFrame with 'bb_middle', 'bb_upper', 'bb_lower' columns
    """
    price = price_data[price_col]

    # Middle Band: SMA
    sma = price.rolling(window=window).mean()

    # Standard Deviation
    std = price.rolling(window=window).std()

    # Upper and Lower Bands
    upper_band = sma + std_multiplier * std
    lower_band = sma - std_multiplier * std

    # Return as DataFrame
    bb = pd.DataFrame({
        'bb_middle': sma,
        'bb_upper': upper_band,
        'bb_lower': lower_band
    })

    return bb

""" Donchain Channels"""

#USE 20, 50 OR 55

def calculate_donchian_channel(price_data, window=20):
    """
    Calculate Donchian Channel.

    Args:
        price_data (pd.DataFrame): DataFrame with 'high' and 'low' columns
        window (int): Lookback period (default: 20)

    Returns:
        pd.DataFrame: DataFrame with 'dc_upper', 'dc_lower', 'dc_middle'
    """
    upper_band = price_data['high'].rolling(window=window).max()
    lower_band = price_data['low'].rolling(window=window).min()
    middle_band = (upper_band + lower_band) / 2

    dc = pd.DataFrame({
        'dc_upper': upper_band,
        'dc_lower': lower_band,
        'dc_middle': middle_band
    })

    return dc

""" Simple Moving Average - SMA"""

# USE 13, 50, 100 OR 200

def calculate_sma(price_data, window=50, price_col='close'):
    """
    Calculate Simple Moving Average (SMA).

    Args:
        price_data (pd.DataFrame): DataFrame containing price data
        window (int): Lookback period for SMA (default: 50)
        price_col (str): Column name for price (default: 'close')

    Returns:
        pd.Series: SMA values
    """
    sma = price_data[price_col].rolling(window=window).mean()
    return sma

""" Trend"""

def determine_sma_trend(price_data, short_window=13, long_window=50, price_col='close'):
    """
    Determine trend based on SMA crossover.

    Args:
        price_data (pd.DataFrame): DataFrame containing price data
        short_window (int): Short SMA period (default: 13)
        long_window (int): Long SMA period (default: 50)
        price_col (str): Column name for price (default: 'close')

    Returns:
        pd.Series: Trend labels ('uptrend' or 'downtrend')
    """
    short_sma = price_data[price_col].rolling(window=short_window).mean()
    long_sma = price_data[price_col].rolling(window=long_window).mean()

    trend = np.where(short_sma > long_sma, 'uptrend', 'downtrend')

    return pd.Series(trend, index=price_data.index)

""" Nadaraya Watson Envelope"""

def calculate_nadaraya_watson_envelope(price_data, window=20, bandwidth=3, deviation_window=20, deviation_multiplier=1.0, price_col='close'):
    """
    Calculate non-repainting Nadaraya-Watson estimator with envelope bands.

    Args:
        price_data (pd.DataFrame): DataFrame containing price data
        window (int): Lookback period for smoothing (default: 20)
        bandwidth (float): Bandwidth for kernel (default: 3)
        deviation_window (int): Window for deviation average (default: 20)
        deviation_multiplier (float): Multiplier for envelope (default: 1.0)
        price_col (str): Column name for price (default: 'close')

    Returns:
        pd.DataFrame: DataFrame with 'nw', 'nw_upper', 'nw_lower'
    """
    prices = price_data[price_col].values
    smoothed = np.full(len(prices), np.nan)

    for i in range(window, len(prices)):
        y = prices[i - window:i]
        x = np.arange(window)
        weights = np.exp(-0.5 * ((x - (window - 1)) / bandwidth) ** 2)
        weights /= weights.sum()
        smoothed[i] = np.dot(weights, y)

    smoothed_series = pd.Series(smoothed, index=price_data.index)

    # Deviation: abs(price - smoothed)
    deviation = np.abs(price_data[price_col] - smoothed_series)

    # Average deviation
    avg_deviation = deviation.rolling(window=deviation_window).mean()

    upper_band = smoothed_series + deviation_multiplier * avg_deviation
    lower_band = smoothed_series - deviation_multiplier * avg_deviation

    bands = pd.DataFrame({
        'nw': smoothed_series,
        'nw_upper': upper_band,
        'nw_lower': lower_band
    })

    return bands

""" Supertrend"""

def calculate_supertrend(price_data, atr_period=10, multiplier=3):
    """
    Calculate SuperTrend indicator.

    Args:
        price_data (pd.DataFrame): DataFrame containing 'high', 'low', 'close'
        atr_period (int): ATR lookback period (default: 10)
        multiplier (float): ATR multiplier (default: 3)

    Returns:
        pd.DataFrame: DataFrame with 'supertrend', 'supertrend_direction', 'supertrend_signal'
    """
    high = price_data['high']
    low = price_data['low']
    close = price_data['close']

    # ATR
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(atr_period).mean()

    # Basic Bands
    hl2 = (high + low) / 2
    upper_band = hl2 + multiplier * atr
    lower_band = hl2 - multiplier * atr

    # Final Bands & Trend
    supertrend = np.full(len(close), np.nan)
    direction = np.full(len(close), True)  # True: uptrend, False: downtrend

    for i in range(atr_period, len(close)):
        if close[i] > upper_band[i-1]:
            direction[i] = True
        elif close[i] < lower_band[i-1]:
            direction[i] = False
        else:
            direction[i] = direction[i-1]

            if direction[i] and lower_band[i] < lower_band[i-1]:
                lower_band[i] = lower_band[i-1]
            if not direction[i] and upper_band[i] > upper_band[i-1]:
                upper_band[i] = upper_band[i-1]

        supertrend[i] = lower_band[i] if direction[i] else upper_band[i]

    trend_label = np.where(direction, 'uptrend', 'downtrend')

    # Signal: True if trend changes this bar
    signal = np.full(len(close), np.nan)
    signal[atr_period:] = direction[atr_period:] != direction[atr_period-1:-1]

    result = pd.DataFrame({
        'supertrend': supertrend,
        'supertrend_direction': trend_label,
        'supertrend_signal': signal
    }, index=price_data.index)

    return result



