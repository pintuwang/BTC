import os
import json
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

def calculate_max_pain(ticker_obj, expiry_date):
    """Calculates Max Pain strike with lower liquidity threshold."""
    try:
        chain = ticker_obj.option_chain(expiry_date)
        # Lowered filter to 10 to catch Weekly expiries
        calls = chain.calls[chain.calls['openInterest'] >= 10][['strike', 'openInterest']].fillna(0)
        puts = chain.puts[chain.puts['openInterest'] >= 10][['strike', 'openInterest']].fillna(0)
        
        strikes = sorted(set(calls['strike']).union(set(puts['strike'])))
        if not strikes: return None
        
        pain_results = []
        for s in strikes:
            # Calculate total loss for all holders if price settles at strike 's'
            call_loss = calls[calls['strike'] < s].apply(lambda x: (s - x['strike']) * x['openInterest'], axis=1).sum()
            put_loss = puts[puts['strike'] > s].apply(lambda x: (x['strike'] - s) * x['openInterest'], axis=1).sum()
            pain_results.append({'strike': s, 'total': call_loss + put_loss})
        
        # The strike price with the minimum total loss is the Max Pain point
        return float(pd.DataFrame(pain_results).sort_values('total').iloc[0]['strike'])
    except Exception as e:
        print(f"Error calculating MSTR pain for {expiry_date}: {e}")
        return None

def get_btc_expiry_pains():
    """Fetches real BTC Max Pain data from Deribit for all available expiries."""
    try:
        url = "https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency=BTC&kind=option"
        resp = requests.get(url, timeout=15).json()
        data = resp.get('result', [])
        
        exp_groups = {}
        for item in data:
            # Name format: BTC-26DEC25-95000-P
            parts = item['instrument_name'].split('-')
            exp_str = parts[1]
            strike = float(parts[2])
            oi = item['open_interest']
            side = parts[3] # C or P
            
            if exp_str not in exp_groups: 
                exp_groups[exp_str] = {'calls': [], 'puts': [], 'strikes': set()}
            
            exp_groups[exp_str]['strikes'].add(strike)
            if side == 'C':
                exp_groups[exp_str]['calls'].append({'strike': strike, 'oi': oi})
            else:
                exp_groups[exp_str]['puts'].append({'strike': strike, 'oi': oi})

        results = {}
        for exp, val in exp_groups.items():
            dt = datetime.strptime(exp, "%d%b%y").strftime("%Y-%m-%d")
            strikes = sorted(list(val['strikes']))
            pains = []
            for s in strikes:
                cl = sum((s - c['strike']) * c['oi'] for c in val['calls'] if c['strike'] < s)
                pl = sum((p['strike'] - s) * p['oi'] for p in val['puts'] if p['strike'] > s)
                pains.append({'strike': s, 'total': cl + pl})
            results[dt] = sorted(pains, key=lambda x: x['total'])[0]['strike']
        return results
    except Exception as e:
        print(f"BTC Data Fetch Error: {e}")
        return {}

def run_update():
    mstr = yf.Ticker("MSTR")
    try:
        mstr_spot = mstr.history(period="1d")['Close'].iloc[-1]
    except:
        mstr_spot = 165.0

    btc_dict = get_btc_expiry_pains()
    # Sort BTC dates to allow for "nearest neighbor" matching
    sorted_btc_dates = sorted(btc_dict.keys())

    # Get next 8 expiries within 90 days
    cutoff = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
    all_options = [e for e in mstr.options if e <= cutoff][:10]
    
    chain_data = []
    for exp in all_options:
        m_pain = calculate_max_pain(mstr, exp)
        if m_pain:
            # Find nearest BTC expiry date (Deribit doesn't always have matching Weeklies)
            # Default to 95000 if no data found
            b_pain = btc_dict.get(exp)
            if not b_pain and sorted_btc_dates:
                # Find the closest available BTC date
                closest_date = min(sorted_btc_dates, key=lambda d: abs(datetime.strptime(d, "%Y-%m-%d") - datetime.strptime(exp, "%Y-%m-%d")))
                b_pain = btc_dict[closest_date]
            
            chain_data.append({
                "date": exp,
                "mstr_pain": round(m_pain, 2),
                "btc_pain": round(b_pain or 95000.0, 2),
                "is_monthly": (15 <= int(exp.split('-')[2]) <= 21) # 3rd Friday logic
            })

    # Save current view
    payload = {
        "last_update_utc": datetime.utcnow().isoformat() + "Z",
        "spot": round(mstr_spot, 2),
        "data": chain_data[:8] # Keep top 8 for the 6-week chart
    }

    os.makedirs('data', exist_ok=True)
    with open('data/history.json', 'w') as f:
        json.dump(payload, f, indent=4)

    # Update Daily History Log
    log_path = 'data/history_log.json'
    log = json.load(open(log_path)) if os.path.exists(log_path) else []
    today = datetime.now().strftime("%Y-%m-%d")
    
    if not log or log[-1]['date'] != today:
        log.append({"date": today, "spot": payload["spot"]})
        with open(log_path, 'w') as f:
            json.dump(log[-60:], f, indent=4)

if __name__ == "__main__":
    run_update()
