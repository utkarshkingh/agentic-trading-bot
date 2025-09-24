import logging
import os
from kiteconnect import KiteConnect
import pandas as pd
from dotenv import load_dotenv
logging.basicConfig(level=logging.DEBUG)

load_dotenv()

api_key = os.getenv('KITE_API_KEY')
access_token = os.getenv('KITE_ACCESS_TOKEN')

kite = KiteConnect(api_key=api_key)
kite.set_access_token(access_token)

print("Kite Connect session established successfully.")

# Get profile details
profile_info = kite.profile()
print("\n=== PROFILE DETAILS ===")
print(f"User ID: {profile_info.get('user_id', 'N/A')}")
print(f"User Name: {profile_info.get('user_name', 'N/A')}")
print(f"Email: {profile_info.get('email', 'N/A')}")
print(f"Broker: {profile_info.get('broker', 'N/A')}")
print(f"User Type: {profile_info.get('user_type', 'N/A')}")
print(f"Exchanges: {profile_info.get('exchanges', [])}")
print(f"Products: {profile_info.get('products', [])}")
print(f"Order Types: {profile_info.get('order_types', [])}")

# Get holdings info
holdings_info = kite.holdings()
print("\n=== HOLDINGS INFORMATION ===")

if holdings_info:
    for holding in holdings_info:
        print(f"\nStock: {holding.get('tradingsymbol', 'N/A')}")
        print(f"Exchange: {holding.get('exchange', 'N/A')}")
        print(f"ISIN: {holding.get('isin', 'N/A')}")
        print(f"Quantity: {holding.get('quantity', 0)}")
        print(f"Average Price: ₹{holding.get('average_price', 0)}")
        print(f"Last Price: ₹{holding.get('last_price', 0)}")
        print(f"PnL: ₹{holding.get('pnl', 0)}")
        print(f"Day Change: {holding.get('day_change_percentage', 0):.2f}%")
        print("-" * 40)
else:
    print("No holdings found.")

# HARDCODED MARKET ORDER FUNCTION
def place_market_order(tradingsymbol,quantity,transaction_type):
    """Place a market order with hardcoded values"""
    try:
        order_id = kite.place_order(
            variety="amo",
            exchange="NSE",
            tradingsymbol=None,
            transaction_type=None,
            quantity=None,
            product="CNC",
            order_type="MARKET",
            validity="DAY"  # Added required validity parameter
        )
        print(f"Market order placed successfully. Order ID: {order_id}")
        return order_id
    except Exception as e:
        print(f"Order placement failed: {e}")
        return None

# CALL THE FUNCTION (moved outside the function definition)
place_market_order()
