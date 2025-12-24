import os
import json
import requests
from datetime import datetime

# --- CONFIGURATION ---
STRIKE_TARGET = 150  # Your default strike for the log

def get_data():
    # [Your existing data fetching code for MSTR and BTC goes here]
    # For this example, let's assume 'payload' is your final dictionary
    payload = {
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "spot": 165.50, # Example Spot
        "data": [
            {"date": "2025-12-26", "mstr_pain": 170, "btc_pain": 95000},
            {"date": "2026-01-16", "mstr_pain": 180, "btc_pain": 105000}
        ]
    }
    return payload

def calculate_score(spot, weekly_pain, strike):
    score = 0
    if spot > strike * 1.10: score += 4
    if weekly_pain > strike: score += 6
    return score

def update_history_log(current_payload):
    folder = 'data'
    filename = 'history_log.json'
    filepath = os.path.join(folder, filename)
    
    if not os.path.exists(folder):
        os.makedirs(folder)

    # Load existing
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            history = json.load(f)
    else:
        history = []

    # Prepare today's entry
    spot = current_payload['spot']
    weekly_pain = current_payload['data'][0]['mstr_pain']
    score = calculate_score(spot, weekly_pain, STRIKE_TARGET)
    
    log_entry = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "spot": spot,
        "mstr_pain": weekly_pain,
        "score": score
    }

    # Only add if date is new
    if not history or history[-1]['date'] != log_entry['date']:
        history.append(log_entry)

    # Save last 30 days
    with open(filepath, 'w') as f:
        json.dump(history[-30:], f, indent=4)

if __name__ == "__main__":
    data = get_data()
    # Save current state
    with open('data/history.json', 'w') as f:
        json.dump(data, f, indent=4)
    
    # Save to permanent log
    update_history_log(data)
    print("Data and History Log updated successfully.")
