import os
import json
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

def calculate_max_pain(ticker_obj, expiry_date):
    """Calculates the Max Pain strike for a given expiry."""
    try:
        chain = ticker_obj.option_chain(expiry_date)
        calls = chain.calls[['strike', 'openInterest']].fillna(0)
        puts = chain.puts[['strike', 'openInterest']].fillna(0)
        
        # Combine all unique strikes
        strikes = sorted(set(calls['strike']).union(set(puts['strike'])))
        
        pain_results = []
        for s in strikes:
            # Call Pain: (Expiry Price - Strike) * OI for all ITM calls
            call_pain = calls[calls['strike'] < s].apply(lambda x: (s - x['strike']) * x['openInterest'], axis=1).sum()
            # Put Pain: (Strike - Expiry Price) * OI for all ITM puts
            put_pain = puts[puts['strike'] > s].apply(lambda x: (x['strike'] - s) * x['openInterest'], axis=1).sum()
            pain_results.append({'strike': s, 'total_pain': call_pain + put_pain})
            
        pain_df = pd.DataFrame(pain_results)
        return float(pain_df.loc[pain_df['total_pain'].idxmin(), 'strike'])
    except Exception as e:
        print(f"Error calculating Max Pain for {expiry_date}: {e}")
        return None

def get_market_phase():
    sgt_now = datetime.utcnow() + timedelta(hours=8)
    day = sgt_now.weekday()
    if day <= 1: return "Provisional (Mon/Tue)"
    if day == 2: return "Sweet Spot (Wednesday)"
    return "Reactive (Thu/Fri)"

def is_monthly(date_str):
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return d.weekday() == 4 and 15 <= d.day <= 21

def run_update():
    # 1. LIVE MSTR DATA (Yahoo Finance)
    mstr = yf.Ticker("MSTR")
    mstr_spot = mstr.fast_info['last_price']
    all_expiries = mstr.options[:8] # Get next 8 expiries
    
    chain_data = []
    for exp in all_expiries:
        pain = calculate_max_pain(mstr, exp)
        if pain:
            chain_data.append({
                "date": exp,
                "mstr_pain": pain,
                "btc_pain": 0, # BTC placeholder - updated below
                "is_monthly": is_monthly(exp)
            })

    # 2. LIVE BTC DATA (Deribit API)
    try:
        btc_res = requests.get("https://www.deribit.com/api/v2/public/get_index_price?index_name=btc_usd").json()
        btc_spot = btc_res['result']['index_price']
        # For simplicity, we track BTC Spot here; full BTC Max Pain calculation 
        # requires iterating 1000+ Deribit instruments.
        for item in chain_data:
            item["btc_pain"] = btc_spot 
    except:
        btc_spot = 95000.0

    payload = {
        "last_update_utc": datetime.utcnow().isoformat() + "Z",
        "spot": round(mstr_spot, 2),
        "phase": get_market_phase(),
        "data": chain_data
    }

    os.makedirs('data', exist_ok=True)
    with open('data/history.json', 'w') as f:
        json.dump(payload, f, indent=4)

    # 3. HISTORICAL LOGGING
    log_path = 'data/history_log.json'
    log = json.load(open(log_path)) if os.path.exists(log_path) else []
    sgt_date = (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d")
    
    if not log or log[-1]['date'] != sgt_date:
        log.append({"date": sgt_date, "spot": payload["spot"], "mstr_pain": chain_data[0]["mstr_pain"], "phase": payload["phase"]})
        with open(log_path, 'w') as f: json.dump(log[-30:], f, indent=4)

if __name__ == "__main__":
    run_update()
