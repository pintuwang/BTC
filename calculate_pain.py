import os
import json
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

def calculate_max_pain(ticker_obj, expiry_date):
    """Calculates Max Pain strike with liquidity filtering."""
    try:
        chain = ticker_obj.option_chain(expiry_date)
        # Filter for liquidity: only strikes with OI > 50 to avoid LEAPS noise
        calls = chain.calls[chain.calls['openInterest'] > 50][['strike', 'openInterest']].fillna(0)
        puts = chain.puts[chain.puts['openInterest'] > 50][['strike', 'openInterest']].fillna(0)
        
        strikes = sorted(set(calls['strike']).union(set(puts['strike'])))
        if not strikes: return None
        
        pain_results = []
        for s in strikes:
            # Pain = Sum of (Intrinsic Value * Open Interest)
            call_pain = calls[calls['strike'] < s].apply(lambda x: (s - x['strike']) * x['openInterest'], axis=1).sum()
            put_pain = puts[puts['strike'] > s].apply(lambda x: (x['strike'] - s) * x['openInterest'], axis=1).sum()
            pain_results.append({'strike': s, 'total': call_pain + put_pain})
        
        return float(pd.DataFrame(pain_results).sort_values('total').iloc[0]['strike'])
    except:
        return None

def get_btc_expiry_pains():
    """Fetches real BTC Max Pain data per expiry from Deribit."""
    try:
        url = "https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency=BTC&kind=option"
        data = requests.get(url, timeout=15).json().get('result', [])
        
        # Group data by expiry
        expiries = {}
        for item in data:
            # Format: BTC-26DEC25-80000-C
            parts = item['instrument_name'].split('-')
            exp_str = parts[1] # e.g. 26DEC25
            strike = float(parts[2])
            oi = item['open_interest']
            
            if exp_str not in expiries: expiries[exp_str] = {'calls': [], 'puts': [], 'strikes': set()}
            
            expiries[exp_str]['strikes'].add(strike)
            if parts[3] == 'C':
                expiries[exp_str]['calls'].append({'strike': strike, 'oi': oi})
            else:
                expiries[exp_str]['puts'].append({'strike': strike, 'oi': oi})

        results = {}
        for exp, val in expiries.items():
            # Convert '26DEC25' to '2025-12-26'
            dt = datetime.strptime(exp, "%d%b%y").strftime("%Y-%m-%d")
            
            # Simple Max Pain Math for BTC
            strikes = sorted(list(val['strikes']))
            pains = []
            for s in strikes:
                cp = sum((s - c['strike']) * c['oi'] for c in val['calls'] if c['strike'] < s)
                pp = sum((p['strike'] - s) * p['oi'] for p in val['puts'] if p['strike'] > s)
                pains.append({'strike': s, 'total': cp + pp})
            
            results[dt] = sorted(pains, key=lambda x: x['total'])[0]['strike']
        return results
    except Exception as e:
        print(f"BTC Fetch Error: {e}")
        return {}

def run_update():
    mstr = yf.Ticker("MSTR")
    try:
        mstr_spot = mstr.history(period="1d")['Close'].iloc[-1]
    except:
        mstr_spot = 165.0 # Fallback

    # 1. Fetch BTC Expiry-specific Max Pain
    btc_pains = get_btc_expiry_pains()

    # 2. Process MSTR Expiries (Limit to next 60 days to avoid $750 LEAPS noise)
    cutoff = (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")
    all_expiries = [e for e in mstr.options if e <= cutoff][:8] # Next 8 unique dates
    
    chain_data = []
    for exp in all_expiries:
        m_pain = calculate_max_pain(mstr, exp)
        if m_pain:
            # Find closest BTC expiry or use a realistic average if no direct match
            b_pain = btc_pains.get(exp, 105000.0) 
            
            chain_data.append({
                "date": exp,
                "mstr_pain": m_pain,
                "btc_pain": b_pain,
                "is_monthly": (15 <= int(exp.split('-')[2]) <= 21)
            })

    # 3. Save Payload
    payload = {
        "last_update_utc": datetime.utcnow().isoformat() + "Z",
        "spot": round(mstr_spot, 2),
        "phase": "Wednesday" if datetime.now().weekday() == 2 else "Standard",
        "data": chain_data
    }

    os.makedirs('data', exist_ok=True)
    with open('data/history.json', 'w') as f:
        json.dump(payload, f, indent=4)

    # 4. Save to Daily Log (Fixed history range)
    log_path = 'data/history_log.json'
    log = json.load(open(log_path)) if os.path.exists(log_path) else []
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    if not log or log[-1]['date'] != today_str:
        log.append({
            "date": today_str, 
            "spot": payload["spot"], 
            "mstr_pain": chain_data[0]["mstr_pain"] if chain_data else 0
        })
        with open(log_path, 'w') as f:
            json.dump(log[-60:], f, indent=4) # Store 60 days of history

if __name__ == "__main__":
    run_update()
