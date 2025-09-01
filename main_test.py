from pybit.unified_trading import HTTP
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('BYBIT_API_KEY')
api_secret = os.getenv('BYBIT_API_SECRET')

session = HTTP(testnet=False, api_key=api_key, api_secret=api_secret)

# Coin miktarı ile deneyelim (1000PEPE)
session.place_order(
    category='linear',
    symbol='1000PEPEUSDT',
    side='Buy',
    orderType='Market',
    qty='10000',  # 100,000 PEPE (yaklaşık 1$)
    reduceOnly=False
)
print('10,000 1000PEPE long işlem gönderildi!')
