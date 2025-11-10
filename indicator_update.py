    # OLD INDICATORS & STRATEGIES

    # --- Bollinger Bands ---
    def calculate_bollinger_bands(price_data, window=20, std_multiplier=2, price_col='close'):
        price = price_data[price_col]
        sma = price.rolling(window=window).mean()
        std = price.rolling(window=window).std()
        upper_band = sma + std_multiplier * std
        lower_band = sma - std_multiplier * std
        return pd.DataFrame({'bb_middle': sma, 'bb_upper': upper_band, 'bb_lower': lower_band})
        
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


