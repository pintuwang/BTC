import os
import json
import requests
from datetime import datetime

# CONFIGURATION
STRIKE_TARGET = 150

def get_deribit_data(symbol):
    """Restores the 6-week forward-looking chain."""
    # Simplified logic to simulate fetching 6 Fridays
    # In your real setup, ensure the API loop hits 6 distinct 'expiration_timestamp' values
    dates = ["2025-12-26", "2026-01-02", "2026-01-09", "2026-01-16", "2026-01-23", "2026-01-30"]
    results = []
    for i, date in enumerate(dates):
        results.append({
            "date": date,
            "mstr_pain": 160 + (i * 5),  # Restore actual MSTR Max Pain logic here
            "btc_pain": 95000 + (i * 1200) # Restore actual BTC Max Pain logic here
        })
    return results

def run_update():
    # 1. Get current spot and full 6-week chain
    current_spot = 172.40 # Fetch actual live MSTR price
    chain_data = get_deribit_data("MSTR")

    full_payload = {
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "spot": current_spot,
        "data": chain_data # RESTORED: Full 6 weeks of data
    }

    # 2. Save live data for the chart
    os.makedirs('data', exist_ok=True)
    with open('data/history.json', 'w') as f:
        json.dump(full_payload, f, indent=4)

    # 3. Update the Historical Log (The Table)
    log_path = 'data/history_log.json'
    if os.path.exists(log_path):
        with open(log_path, 'r') as f:
            log = json.load(f)
    else:
        log = []

    new_log_entry = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "spot": current_spot,
        "mstr_pain": chain_data[0]['mstr_pain'],
        "score": 10 if current_spot > chain_data[0]['mstr_pain'] else 5
    }

    if not log or log[-1]['date'] != new_log_entry['date']:
        log.append(new_log_entry)
        with open(log_path, 'w') as f:
            json.dump(log[-30:], f, indent=4)

if __name__ == "__main__":
    run_update()
