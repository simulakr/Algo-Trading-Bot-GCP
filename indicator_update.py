def atr_zigzag_two_columns(df, atr_col="atr", close_col="close", atr_mult=1): 
    closes = df[close_col].values
    atrs = df[atr_col].values

    high_pivot = [None] * len(df)
    low_pivot = [None] * len(df)
    high_pivot_atr = [None] * len(df)  # ATR değerini sakla
    low_pivot_atr = [None] * len(df)   # ATR değerini sakla
    high_pivot_confirmed = [0] * len(df)
    low_pivot_confirmed = [0] * len(df)
    pivot_bars_ago = [None] * len(df)

    last_pivot = closes[0]
    last_atr = atrs[0]
    last_pivot_idx = 0
    direction = None  # "up" veya "down"

    for i in range(1, len(df)):
        price = closes[i]
        atr = atrs[i] * atr_mult  # ATR çarpanı uygulanıyor

        if direction is None:
            if price >= last_pivot + atr:
                direction = "up"
                last_pivot = closes[last_pivot_idx]
                high_pivot[last_pivot_idx] = last_pivot
                high_pivot_atr[last_pivot_idx] = atrs[last_pivot_idx]  # ATR değerini kaydet
            elif price <= last_pivot - atr:
                direction = "down"
                last_pivot = closes[last_pivot_idx]
                low_pivot[last_pivot_idx] = last_pivot
                low_pivot_atr[last_pivot_idx] = atrs[last_pivot_idx]   # ATR değerini kaydet

        elif direction == "up":
            if price <= (last_pivot - atr):
                # ✅ Tepe teyit edildi
                high_pivot[last_pivot_idx] = last_pivot
                high_pivot_atr[last_pivot_idx] = atrs[last_pivot_idx]  # ATR değerini kaydet
                high_pivot_confirmed[i] = 1
                pivot_bars_ago[i] = i - last_pivot_idx

                direction = "down"
                last_pivot = price
                last_pivot_idx = i
            elif price > last_pivot:
                # Tepe güncelle, teyit etme
                last_pivot = price
                last_pivot_idx = i

        elif direction == "down":
            if price >= (last_pivot + atr):
                # ✅ Dip teyit edildi
                low_pivot[last_pivot_idx] = last_pivot
                low_pivot_atr[last_pivot_idx] = atrs[last_pivot_idx]   # ATR değerini kaydet
                low_pivot_confirmed[i] = 1
                pivot_bars_ago[i] = i - last_pivot_idx

                direction = "up"
                last_pivot = price
                last_pivot_idx = i
            elif price < last_pivot:
                # Dip güncelle, teyit etme
                last_pivot = price
                last_pivot_idx = i

    # Önce orijinal sütunları oluştur
    df["high_pivot"] = high_pivot
    df["low_pivot"] = low_pivot
    df["high_pivot_atr"] = high_pivot_atr
    df["low_pivot_atr"] = low_pivot_atr
    df["high_pivot_confirmed"] = high_pivot_confirmed
    df["low_pivot_confirmed"] = low_pivot_confirmed
    df["pivot_bars_ago"] = pivot_bars_ago

    # NaN değerleri doldurma işlemleri
    # high_pivot ve low_pivot için forward fill
    df["high_pivot_filled"] = df["high_pivot"].ffill()
    df["low_pivot_filled"] = df["low_pivot"].ffill()

    # ATR değerleri için de forward fill
    df["high_pivot_atr_filled"] = df["high_pivot_atr"].ffill()
    df["low_pivot_atr_filled"] = df["low_pivot_atr"].ffill()

    # High pivot - GÜVENLİ VERSİYON
    high_temp = df["high_pivot_confirmed"].replace(0, np.nan)  # pd.NA yerine np.nan kullan
    high_temp = high_temp.ffill()
    df["high_pivot_confirmed_filled"] = high_temp.fillna(0).astype(int)
    
    # Low pivot - GÜVENLİ VERSİYON  
    low_temp = df["low_pivot_confirmed"].replace(0, np.nan)  # pd.NA yerine np.nan kullan
    low_temp = low_temp.ffill()
    df["low_pivot_confirmed_filled"] = low_temp.fillna(0).astype(int)

    pivot_bars_filled = []
    last_valid_value = None
    last_valid_index = None

    for i, value in enumerate(pivot_bars_ago):
        if value is not None:
            last_valid_value = value
            last_valid_index = i
            pivot_bars_filled.append(value)
        elif last_valid_value is not None:
            # NaN değeri, son geçerli değer + (mevcut index - son geçerli index)
            new_value = last_valid_value + (i - last_valid_index)
            pivot_bars_filled.append(new_value)
        else:
            # İlk değerler için
            pivot_bars_filled.append(None)

    df["pivot_bars_ago_filled"] = pivot_bars_filled

    return df


# Usage
# 2x ATR için
df = atr_zigzag_two_columns(df, atr_col="atr", close_col="close", atr_mult=2, suffix="_2x")

# 3x ATR için
df = atr_zigzag_two_columns(df, atr_col="atr", close_col="close", atr_mult=3, suffix="_3x")

