python -c "
from main import TradingBot
bot = TradingBot(testnet=False)
print('SOLUSDT aktif mi:', bot.position_manager.has_active_position('SOLUSDT'))
print('Aktif pozisyonlar:', list(bot.position_manager.active_positions.keys()))
"
