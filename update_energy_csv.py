import requests
import pandas as pd
from datetime import datetime, timezone

# Expanded list to include more Victorian-active retailers
RETAILERS = [
    "agl", "origin", "energyaustralia", "energy-locals", "redenergy",
    "lumo", "alinta", "powershop", "dodo", "tango", "globird", "sumo", 
    "momentum", "ovo", "covau", "1stenergy", "diamond", "engie", 
    "amber", "nectr", "simply", "arcline", "kogan"
]

BASE = "https://cdr.energymadeeasy.gov.au"
headers_plans = {"x-v": "1", "x-min-v": "1"}
headers_detail = {"x-v": "3"}
POSTCODE = "3929" # Flinders / Mornington Peninsula
NOW = datetime.now(timezone.utc)
EXCLUDE_KEYWORDS = ["demand", "controlled load", "dedicated circuit", "cl1", "cl2", "cl"]
MAX_PLANS_PER_RETAILER = 1
GST = 1.1

def tou_to_periods(tou_windows):
    periods = []
    for w in tou_windows:
        try:
            start = int(w["startTime"].split(":")[0])
            end = int(w["endTime"].split(":")[0])
            if end == 0: end = 24
            periods.append((start, end))
        except: continue
    periods.sort()
    return periods

def merge_periods(periods):
    if not periods: return []
    merged = [list(periods[0])]
    for start, end in periods[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([list((start, end))])
    return [(s, e) for s, e in merged]

def has_overlapping_segments(segments):
    for i in range(len(segments) - 1):
        if segments[i][1] > segments[i+1][0]:
            return True
    return False

retailer_plans = {}

for r in RETAILERS:
    retailer_plans[r] = []
    page = 1
    while True:
        try:
            url = f"{BASE}/{r}/cds-au/v1/energy/plans?page-size=100&fuelType=ELECTRICITY&page={page}"
            resp = requests.get(url, headers=headers_plans, timeout=15)
            if resp.status_code != 200:
                print(f"DEBUG {r}: API Not Available (Status {resp.status_code})")
                break
            
            data = resp.json()
            plans = data.get("data", {}).get("plans", [])
            if not plans: break

            for p in plans:
                p_name = p.get("displayName", "Unnamed Plan")
                
                # Check Postcode
                postcodes = str(p.get("geography", {}).get("includedPostcodes", []))
                if POSTCODE not in postcodes:
                    continue # Silent skip for postcodes to keep log clean

                # Check Expiry
                effective_to = p.get("effectiveTo")
                if effective_to:
                    expiry = datetime.fromisoformat(effective_to.replace("Z", "+00:00"))
                    if expiry < NOW:
                        print(f"DEBUG {r}: Skipping {p_name} (Expired)")
                        continue

                # Check Keywords
                if any(kw in p_name.lower() for kw in EXCLUDE_KEYWORDS):
                    print(f"DEBUG {r}: Skipping {p_name} (Excluded Keyword)")
                    continue

                try:
                    plan_id = p.get("planId")
                    detail_resp = requests.get(f"{BASE}/{r}/cds-au/v1/energy/plans/{plan_id}", headers=headers_detail, timeout=15)
                    if detail_resp.status_code != 200: continue
                    
                    detail = detail_resp.json().get("data", {})
                    contract = detail.get("electricityContract", {})
                    brand = detail.get("brandName", r.upper())
                    
                    # Feed-in Tariff (Now optional)
                    fit_rate = 0.0
                    for fit in contract.get("solarFeedInTariff", []):
                        rates = fit.get("singleTariff", {}).get("rates", [])
                        if rates:
                            fit_rate = round(float(rates[0].get("unitPrice", 0)) * 100 * GST, 2)
                            break
                    
                    # Process Tariffs
                    found_valid_tariff = False
                    for period in contract.get("tariffPeriod", []):
                        daily = round(float(period.get("dailySupplyCharge", 0)) * 100 * GST, 2)
                        segments = []
                        peak_rate = 0.0

                        # CASE 1: Time of Use
                        if period.get("rateBlockUType") == "timeOfUseRates":
                            tou_rates = period.get("timeOfUseRates", [])
                            peak_rate = float("inf")
                            for tou in tou_rates:
                                rate = round(float(tou.get("rates", [{}])[0].get("unitPrice", 0)) * 100 * GST, 2)
                                if tou.get("type") == "PEAK":
                                    peak_rate = min(peak_rate, rate)
                                for start, end in tou_to_periods(tou.get("timeOfUse", [])):
                                    segments.append((start, end, rate))
                            
                            segments.sort()
                            if not has_overlapping_segments(segments) and segments:
                                found_valid_tariff = True

                        # CASE 2: Single Rate (Fallback)
                        elif period.get("rateBlockUType") == "singleRate":
                            rate = round(float(period.get("singleRate", {}).get("rates", [{}])[0].get("unitPrice", 0)) * 100 * GST, 2)
                            segments = [(0, 24, rate)]
                            peak_rate = rate
                            found_valid_tariff = True

                        if found_valid_tariff:
                            retailer_plans[r].append({
                                "brand": brand, "name": p_name, "daily": daily,
                                "fit": fit_rate, "segments": segments, "peak_rate": peak_rate
                            })
                            break 
                    
                    if not found_valid_tariff:
                        print(f"DEBUG {r}: Skipping {p_name} (No valid Rate blocks found)")

                except Exception as e:
                    print(f"DEBUG {r}: Error processing {p_name}: {e}")

            total_pages = data.get("meta", {}).get("totalPages", 1)
            if page >= total_pages: break
            page += 1
        except Exception as e:
            print(f"DEBUG {r}: Page Error: {e}")
            break

# ... (Rest of your CSV saving logic remains the same)
rows = [
    {"Heading": "Manual Reference 1", "Import": 139.7, "Export": ""},
]

all_selected = []
for r, plans in retailer_plans.items():
    plans.sort(key=lambda x: x["peak_rate"])
    selected = 0
    seen_patterns = set()
    for plan in plans:
        pattern = tuple((s[0], s[1], s[2]) for s in plan["segments"])
        if pattern in seen_patterns: continue
        seen_patterns.add(pattern)
        all_selected.append(plan)
        selected += 1
        if selected >= MAX_PLANS_PER_RETAILER: break
    print(f"RESULT: {r}: {selected} plans selected from {len(plans)} qualifying")

# Build rows and Save
for plan in all_selected:
    rows.append({"Heading": f"{plan['brand']} {plan['name']}", "Import": plan['daily'], "Export": ""})
    for start, end, rate in plan["segments"]:
        rows.append({"Heading": f"{start}-{end}", "Import": rate, "Export": plan["fit"]})

df = pd.DataFrame(rows)
df.to_csv("energy-pricing.csv", index=False)
print(f"Saved {len(df)} rows to energy-pricing.csv")
