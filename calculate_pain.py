import os
import json
import requests
from datetime import datetime

# 1. API SETTINGS
BASE_URL = "https://www.deribit.com/api/v2/public/"
CURRENCY = "BTC" 

def get_live_data():
    """Fetches real data from Deribit API."""
    try:
        # Get Current Spot Price
        spot_res = requests.get(f"{BASE_URL}get_index_price?index_name=btc_usd").json()
        current_spot = spot_res['result']['index_price']

        # Get all expiries
        exp_res = requests.get(f"{BASE_URL}get_expirations?currency={CURRENCY}").json()
        all_dates = exp_res['result'][:6]  # Take the next 6 Fridays

        chain_data = []
        for date_str in all_dates:
            # Monthly Expiry Check (3rd Friday)
            d_obj = datetime.strptime(date_str, "%d%b%y")
            is_monthly = (15 <= d_obj.day <= 21)
            
            # Fetch Max Pain for this date (using CoinGlass or Deribit Summary)
            # For this script, we fetch the book summary to approximate
            params = {"currency": CURRENCY, "kind": "option"}
            summary = requests.get(f"{BASE_URL}get_book_summary_by_currency", params=params).json()
            
            # (In a full setup, you'd calculate Max Pain from the OI of each strike)
            # Here we use a placeholder that mimics the logic you need:
            chain_data.append({
                "date": d_obj.strftime("%Y-%m-%d"),
                "mstr_pain": 170.0, # Placeholder: Replace with your MSTR logic
                "btc_pain": 96500.0, # Placeholder: Replace with your BTC logic
                "is_monthly": is_monthly
            })
            
        return current_spot, chain_data
    except Exception as e:
        print(f"Error fetching: {e}")
        return None, None

def get_confidence():
    day = datetime.now().weekday()
    if day <= 1: return "Provisional (Low Confidence)"
    if day == 2: return "Sweet Spot (High Confidence)"
    return "Reactive (Maximum Gravity)"

def run_update():
    spot, chain = get_live_data()
    if not spot: return

    full_payload = {
        "last_update_utc": datetime.utcnow().isoformat(),
        "spot": spot,
        "confidence": get_confidence(),
        "data": chain
    }

    # Save live chart data
    os.makedirs('data', exist_ok=True)
    with open('data/history.json', 'w') as f:
        json.dump(full_payload, f, indent=4)

    # Save to table log
    log_path = 'data/history_log.json'
    log = json.load(open(log_path)) if os.path.exists(log_path) else []
    
    new_entry = {"date": datetime.now().strftime("%Y-%m-%d"), "spot": spot, "mstr_pain": chain[0]['mstr_pain'], "confidence": full_payload["confidence"]}
    if not log or log[-1]['date'] != new_entry['date']:
        log.append(new_entry)
        with open(log_path, 'w') as f: json.dump(log[-30:], f, indent=4)

if __name__ == "__main__":
    run_update()
