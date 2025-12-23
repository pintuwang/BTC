import yfinance as yf
import requests
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta

# --- CONFIGURATION ---
MSTR_TICKER = "MSTR"
NUM_WEEKS = 8

def get_next_fridays(n):
    fridays = []
    d = datetime.now()
    d += timedelta(days=(4 - d.weekday() + 7) % 7)
    for _ in range(n):
        fridays.append(d.strftime('%Y-%m-%d'))
        d += timedelta(days=7)
    return fridays

def calculate_mstr_max_pain(expiry):
    try:
        tk = yf.Ticker(MSTR_TICKER)
        # Fetch spot to filter out junk strikes
        spot = tk.history(period='1d')['Close'].iloc[-1]
        chain = tk.option_chain(expiry)
        calls, puts = chain.calls, chain.puts
        
        # FILTER: Only consider strikes within 50% of the current price
        # This prevents the $21.00 and $85.00 "ghost strikes"
        valid_calls = calls[(calls['strike'] > spot * 0.5) & (calls['strike'] < spot * 1.5)]
        valid_puts = puts[(puts['strike'] > spot * 0.5) & (puts['strike'] < spot * 1.5)]
        
        strikes = sorted(list(set(valid_calls['strike']).union(set(valid_puts['strike']))))
        pains = []
        
        for s in strikes:
            c_loss = valid_calls[valid_calls['strike'] < s].apply(lambda x: (s - x['strike']) * x['openInterest'], axis=1).sum()
            p_loss = valid_puts[valid_puts['strike'] > s].apply(lambda x: (x['strike'] - s) * x['openInterest'], axis=1).sum()
            pains.append(c_loss + p_loss)
            
        return float(strikes[np.argmin(pains)])
    except Exception as e:
        print(f"Error: {e}")
        return None

def get_btc_max_pain(expiry_date):
    formatted_date = datetime.strptime(expiry_date, '%Y-%m-%d').strftime('%-d%b%y').upper()
    url = "https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency=BTC&kind=option"
    try:
        response = requests.get(url).json()
        instruments = response['result']
        expiry_data = [i for i in instruments if formatted_date in i['instrument_name']]
        strikes = {}
        for i in expiry_data:
            strike = int(i['instrument_name'].split('-')[2])
            oi = i.get('open_interest', 0)
            strikes[strike] = strikes.get(strike, 0) + oi
        return max(strikes, key=strikes.get) if strikes else None
    except Exception as e:
        print(f"Error fetching BTC for {expiry_date}: {e}")
        return None

def run_monitor():
    # 1. Ensure data directory exists
    if not os.path.exists('data'):
        os.makedirs('data')

    fridays = get_next_fridays(NUM_WEEKS)
    mstr_spot = yf.Ticker(MSTR_TICKER).history(period='1d')['Close'].iloc[-1]
    
    results = []
    for f in fridays:
        m_pain = calculate_mstr_max_pain(f)
        b_pain = get_btc_max_pain(f)
        results.append({"date": f, "mstr_pain": m_pain, "btc_pain": b_pain})

    # 2. Save data
    output = {"last_update": str(datetime.now()), "spot": float(mstr_spot), "data": results}
    with open('data/history.json', 'w') as f:
        json.dump(output, f, indent=4)

    print(f"Update Complete. MSTR Spot: {mstr_spot}")

if __name__ == "__main__":
    run_monitor()
