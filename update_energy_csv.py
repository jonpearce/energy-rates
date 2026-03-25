import requests
import pandas as pd
from datetime import datetime, timezone

RETAILERS = [
    "agl", "origin", "energyaustralia", "redenergy",
    "lumo", "alinta", "powershop", "dodo",
    "tango", "globird", "sumo", "momentum"
]
BASE = "https://cdr.energymadeeasy.gov.au"
headers_plans = {"x-v": "1", "x-min-v": "1"}
headers_detail = {"x-v": "3"}
POSTCODE = "3929"
NOW = datetime.now(timezone.utc)
EXCLUDE_KEYWORDS = ["demand", "controlled load", "dedicated circuit", "cl1", "cl2"]

rows = []

def time_to_hour(t):
    h = int(t.split(":")[0])
    return 24 if h == 0 and t != "00:00" else h

def tou_to_periods(tou_windows):
    """Convert list of startTime/endTime windows into sorted (start, end) hour pairs."""
    periods = []
    for w in tou_windows:
        start = int(w["startTime"].split(":")[0])
        end = int(w["endTime"].split(":")[0])
        if end == 0:
            end = 24
        periods.append((start, end))
    periods.sort()
    return periods

def merge_periods(periods):
    """Merge overlapping or adjacent periods."""
    if not periods:
        return []
    merged = [periods[0]]
    for start, end in periods[1:]:
        if start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged

for r in RETAILERS:
    try:
        page = 1
        while True:
            url = f"{BASE}/{r}/cds-au/v1/energy/plans?page-size=100&fuelType=ELECTRICITY&page={page}"
            resp = requests.get(url, headers=headers_plans, timeout=10)
            if resp.status_code != 200:
                break
            data = resp.json()
            plans = data.get("data", {}).get("plans", [])
            if not plans:
                break

            for p in plans:
                # Filter by postcode
                if POSTCODE not in str(p.get("geography", {}).get("includedPostcodes", [])):
                    continue
                # Filter out expired plans
                effective_to = p.get("effectiveTo")
                if effective_to:
                    expiry = datetime.fromisoformat(effective_to.replace("Z", "+00:00"))
                    if expiry < NOW:
                        continue
                # Filter out excluded plan types by name
                name = p.get("displayName", "").lower()
                if any(kw in name for kw in EXCLUDE_KEYWORDS):
                    continue

                try:
                    plan_id = p.get("planId")
                    detail_resp = requests.get(f"{BASE}/{r}/cds-au/v1/energy/plans/{plan_id}", headers=headers_detail, timeout=10)
                    if detail_resp.status_code != 200:
                        continue
                    detail = detail_resp.json().get("data", {})
                    contract = detail.get("electricityContract", {})
                    plan_name = detail.get("displayName", "Unknown")
                    brand = detail.get("brandName", r.upper())

                    # Skip excluded types in full name too
                    if any(kw in plan_name.lower() for kw in EXCLUDE_KEYWORDS):
                        continue

                    # Get feed-in tariff
                    fit_rate = 0.0
                    for fit in contract.get("solarFeedInTariff", []):
                        rates = fit.get("singleTariff", {}).get("rates", [])
                        if rates:
                            fit_rate = round(float(rates[0].get("unitPrice", 0)) * 100, 2)
                            break

                    for period in contract.get("tariffPeriod", []):
                        daily = round(float(period.get("dailySupplyCharge", 0)) * 100, 2)
                        rate_type = period.get("rateBlockUType", "")

                        # Add plan header row
                        rows.append({
                            "Heading": f"{brand} {plan_name}",
                            "Import": daily if daily else "",
                            "Export": ""
                        })

                        if rate_type == "singleRate":
                            rates = period.get("singleRate", {}).get("rates", [])
                            if rates:
                                rate = round(float(rates[0].get("unitPrice", 0)) * 100, 2)
                                rows.append({
                                    "Heading": "0-24",
                                    "Import": rate,
                                    "Export": fit_rate if fit_rate else ""
                                })

                        elif rate_type == "timeOfUseRates":
                            tou_rates = period.get("timeOfUseRates", [])
                            # Build list of (start, end, rate) sorted by start hour
                            segments = []
                            for tou in tou_rates:
                                rate = round(float(tou.get("rates", [{}])[0].get("unitPrice", 0)) * 100, 2)
                                windows = tou.get("timeOfUse", [])
                                periods_hours = tou_to_periods(windows)
                                merged = merge_periods(periods_hours)
                                for start, end in merged:
                                    segments.append((start, end, rate))
                            segments.sort()
                            for start, end, rate in segments:
                                rows.append({
                                    "Heading": f"{start}-{end}",
                                    "Import": rate,
                                    "Export": fit_rate if fit_rate else ""
                                })

                except Exception as e:
                    print(f"Plan error {r}: {e}")

            total_pages = data.get("meta", {}).get("totalPages", 1)
            if page >= total_pages:
                break
            page += 1
    except Exception as e:
        print(f"Retailer error {r}: {e}")

print(f"Total rows: {len(rows)}")
df = pd.DataFrame(rows)
if not df.empty:
    df.to_csv("energy-pricing.csv", index=False)
    print(f"Saved {len(df)} rows")
else:
    pd.DataFrame(columns=["Heading", "Import", "Export"]).to_csv("energy-pricing.csv", index=False)
    print("No data found")
