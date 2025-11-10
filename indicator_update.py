    # OLD INDICATORS & STRATEGIES

    # --- Bollinger Bands ---
    def calculate_bollinger_bands(price_data, window=20, std_multiplier=2, price_col='close'):
        price = price_data[price_col]
        sma = price.rolling(window=window).mean()
        std = price.rolling(window=window).std()
        upper_band = sma + std_multiplier * std
        lower_band = sma - std_multiplier * std
        return pd.DataFrame({'bb_middle': sma, 'bb_upper': upper_band, 'bb_lower': lower_band})

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
    
    # Pivot Up-Down
    df['pivot_up'] = False
    df['pivot_down'] = False
    df.loc[(df['low_pivot_confirmed']) & (df['trend_13_50']== 'uptrend') & (atr_ranges[symbol][0] < df['pct_atr']) & (df['pct_atr'] < atr_ranges[symbol][1]), 'pivot_up'] = True
    df.loc[(df['high_pivot_confirmed']) & (df['trend_13_50']== 'downtrend') & (atr_ranges[symbol][0] < df['pct_atr']) & (df['pct_atr'] < atr_ranges[symbol][1]), 'pivot_down'] = True

    df['entry_atr_steps_l'] = np.nan
    df.loc[df['pivot_up'], 'entry_atr_steps_l'] = ((df.loc[df['pivot_up'], 'close'] - df.loc[df['pivot_up'], 'low_pivot_filled'] ) / df.loc[df['pivot_up'], 'atr'])
    
    df['entry_atr_steps_s'] = np.nan
    df.loc[df['pivot_down'], 'entry_atr_steps_s'] = ((df.loc[df['pivot_down'], 'high_pivot_filled'] - df.loc[df['pivot_down'], 'close']) / df.loc[df['pivot_down'], 'atr'])
    df.loc[(df['pivot_up']) & (df['dc_position_ratio_50'] > 60) & (df['close'] < df['nw_upper']), 'atr_steps'] = 'long'
    df.loc[(df['pivot_down']) & (df['dc_position_ratio_50'] < 40) & (df['close'] > df['nw_lower']), 'atr_steps'] = 'short' 
    df.loc[(df['low_pivot_confirmed']) & (df['close'] > df['sma_20']) & (df['close'] > df['sma_50']) & (df['close'] > df['sma_200']) & (df['close'] > df['sma_800']) & (atr_ranges[symbol][0] < df['pct_atr']) & (df['pct_atr'] < atr_ranges[symbol][1]), 'pivot_up_up'] = True
    df.loc[(df['high_pivot_confirmed']) & (df['close'] < df['sma_20']) & (df['close'] < df['sma_50']) & (df['close'] < df['sma_200']) & (df['close'] < df['sma_800']) & (atr_ranges[symbol][0] < df['pct_atr']) & (df['pct_atr'] < atr_ranges[symbol][1]), 'pivot_down_down'] = True

    df['dc_order'] = None

    df.loc[(df['dc_breakout_clean_50']) & (df['dc_position_ratio_20'] > 60) & (df['rsi'] > 50) & (df['close'] > df['nw']) &
           (df['close'] < df['nw_upper']) & (df['close'] > df['bb_middle']) & (df['adx'] > 25) & (df['adx'] < 60) & 
            (df['candle_class'].isin(['weak_bearish', 'weak_bullish', 'medium_bullish', 'strong_bullish'])) & 
             (atr_ranges[symbol][0] < df['pct_atr']) & (df['pct_atr'] < atr_ranges[symbol][1]), 'dc_order'] = 'long'
    
    df.loc[(df['dc_breakdown_clean_50']) & (df['dc_position_ratio_20'] < 40) & (df['rsi'] < 50) & (df['close'] < df['nw']) &
           (df['close'] > df['nw_lower']) & (df['close'] < df['bb_middle']) & (df['adx'] > 25) & (df['adx'] < 60) & 
            (df['candle_class'].isin(['weak_bullish', 'weak_bearish', 'medium_bearish', 'strong_bearish'])) & 
             (atr_ranges[symbol][0] < df['pct_atr']) & (df['pct_atr'] < atr_ranges[symbol][1]), 'dc_order'] = 'short'




# 2x ATR için
df = atr_zigzag_two_columns(df, atr_col="atr", close_col="close", atr_mult=2, suffix="_2x")
df['pivot_up_2x'] = False
df['pivot_down_2x'] = False
df.loc[(df['low_pivot_confirmed_2x']) & (df['trend_13_50']== 'uptrend') & (atr_ranges[symbol][0] < df['pct_atr']) & (df['pct_atr'] < atr_ranges[symbol][1]), 'pivot_up_2x'] = True
df.loc[(df['high_pivot_confirmed_2x']) & (df['trend_13_50']== 'downtrend') & (atr_ranges[symbol][0] < df['pct_atr']) & (df['pct_atr'] < atr_ranges[symbol][1]), 'pivot_down_2x'] = True


