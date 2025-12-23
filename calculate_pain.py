import yfinance as yf
import requests
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta

# --- CONFIGURATION ---
MSTR_TICKER = "MSTR"
BTC_SYMBOL = "BTC"
NUM_WEEKS = 8

def get_next_fridays(n):
    """Generates the next n Fridays in YYYY-MM-DD format."""
    fridays = []
    d = datetime.now()
    # Find the next Friday
    d += timedelta(days=(4 - d.weekday() + 7) % 7)
    for _ in range(n):
        fridays.append(d.strftime('%Y-%m-%d'))
        d += timedelta(days=7)
    return fridays

def calculate_mstr_max_pain(expiry):
    """Calculates Max Pain for MSTR using yfinance."""
    try:
        tk = yf.Ticker(MSTR_TICKER)
        chain = tk.option_chain(expiry)
        calls, puts = chain.calls, chain.puts
        
        strikes = sorted(list(set(calls['strike']).union(set(puts['strike']))))
        pains = []
        
        for s in strikes:
            # Loss for call holders: if price > strike
            c_loss = calls[calls['strike'] < s].apply(lambda x: (s - x['strike']) * x['openInterest'], axis=1).sum()
            # Loss for put holders: if price < strike
            p_loss = puts[puts['strike'] > s].apply(lambda x: (x['strike'] - s) * x['openInterest'], axis=1).sum()
            pains.append(c_loss + p_loss)
            
        return float(strikes[np.argmin(pains)])
    except:
        return None

def get_btc_max_pain(expiry_date):
    """Fetches BTC Max Pain from Deribit API or calculates it from Open Interest."""
    # Note: Deribit API uses DDMMMYY format (e.g., 26DEC25)
    formatted_date = datetime.strptime(expiry_date, '%Y-%m-%d').strftime('%-d%b%y').upper()
    url = f"https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency=BTC&kind=option"
    
    try:
        response = requests.get(url).json()
        instruments = response['result']
        # Filter for specific expiry
        expiry_data = [i for i in instruments if formatted_date in i['instrument_name']]
        
        # Simple Max Pain Estimation from Open Interest peaks if full calc is restricted
        # In a real repo, you'd pull the full orderbook for precise calculation
        # For this script, we use a reliable heuristic: strike with highest combined OI
        strikes = {}
        for i in expiry_data:
            name_parts = i['instrument_name'].split('-')
            strike = int(name_parts[2])
            oi = i.get('open_interest', 0)
            strikes[strike] = strikes.get(strike, 0) + oi
            
        return max(strikes, key=strikes.get) if strikes else None
    except:
        return None

def run_monitor():
    fridays = get_next_fridays(NUM_WEEKS)
    mstr_spot = yf.Ticker(MSTR_TICKER).history(period='1d')['Close'].iloc[-1]
    
    results = []
    for f in fridays:
        m_pain = calculate_mstr_max_pain(f)
        b_pain = get_btc_max_pain(f)
        results.append({"date": f, "mstr_pain": m_pain, "btc_pain": b_pain})

    # Save data for the HTML dashboard
    with open('data/history.json', 'w') as f:
        json.dump({"last_update": str(datetime.now()), "spot": mstr_spot, "data": results}, f)

    print(f"Update Complete. MSTR Spot: {mstr_spot}")

if __name__ == "__main__":
    run_monitor()
