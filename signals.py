import pandas as pd
import numpy as np

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
    Son window bar içinde tekrar eden sinyalleri filtreler.
    """
    return signal_series & (signal_series.shift(1).rolling(window=window).sum() == 0)


def generate_signals(df):
    """
    Tüm strateji sinyallerini DataFrame'e ekler.
    """

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

    return df
