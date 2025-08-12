from exchange import BybitFuturesAPI
from position_manager import PositionManager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test fonksiyonu
def test_bybit_operations():
    api = BybitFuturesAPI(testnet=False)
    pm = PositionManager(api.session)
    
    # 1. Veri çekme testi
    data = api.get_ohlcv("SOLUSDT", "15")
    logger.info(f"SOL Verisi:\n{data.tail(2)}")
    
    # 2. 5$'lık 5x LONG pozisyon açma
    entry_price = float(data['close'].iloc[-1])
    pm.open_position(
        symbol="SOLUSDT",
        direction="LONG",
        entry_price=entry_price,
        pct_atr=1.0  # Basit test için sabit ATR
    )

if __name__ == "__main__":
    test_bybit_operations()
