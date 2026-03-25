import requests
import pandas as pd
from datetime import datetime, timezone

RETAILERS = [
    "agl", "origin", "energyaustralia", "redenergy",
    "lumo", "alinta", "powershop", "dodo",
    "tango", "globird", "sumo", "momentum",
    "ovo", "covau", "1stenergy", "diamond",
    "engie", "amber", "nectr", "simply"
]
BASE = "https://cdr.energymadeeasy.gov.au"
headers_plans = {"x-v": "1", "x-min-v": "1"}
headers_detail = {"x-v": "3"}
POSTCODE = "3929"
NOW = datetime.now(timezone.utc)
EXCLUDE_KEYWORDS = ["demand", "controlled load", "dedicated circuit", "cl1", "cl2", " cl "]
MAX_PLANS_PER_RETAILER = 1
GST = 1.1

def tou_to_periods(tou_windows):
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
    if not periods:
        return []
    merged = [list(periods[0])]
    for start, end in periods[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
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
            resp = requests.get(url, headers=headers_plans, timeout=10)
            if resp.status_code != 200:
                print(f"{r}: not available (status {resp.status_code})")
                break
            data = resp.json()
            plans = data.get("data", {}).get("plans", [])
            if not plans:
                break
            for p in plans:
                if POSTCODE not in str(p.get("geography", {}).get("includedPostcodes", [])):
                    continue
                effective_to = p.get("effectiveTo")
                if effective_to:
                    expiry = datetime.fromisoformat(effective_to.replace("Z", "+00:00"))
                    if expiry < NOW:
                        continue
                if any(kw in p.get("displayName", "").lower() for kw in EXCLUDE_KEYWORDS):
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
                    if any(kw in plan_name.lower() for kw in EXCLUDE_KEYWORDS):
                        continue
                    fit_rate = 0.0
                    for fit in contract.get("solarFeedInTariff", []):
                        rates = fit.get("singleTariff", {}).get("rates", [])
                        if rates:
                            fit_rate = round(float(rates[0].get("unitPrice", 0)) * 100 * GST, 2)
                            break
                    if fit_rate <= 0:
                        continue
                    for period in contract.get("tariffPeriod", []):
                        if period.get("rateBlockUType") != "timeOfUseRates":
                            continue
                        daily = round(float(period.get("dailySupplyCharge", 0)) * 100 * GST, 2)
                        tou_rates = period.get("timeOfUseRates", [])
                        segments = []
                        peak_rate = float("inf")
                        for tou in tou_rates:
                            rate = round(float(tou.get("rates", [{}])[0].get("unitPrice", 0)) * 100 * GST, 2)
                            if tou.get("type") == "PEAK":
                                peak_rate = min(peak_rate, rate)
                            for start, end in merge_periods(tou_to_periods(tou.get("timeOfUse", []))):
                                segments.append((start, end, rate))
                        segments.sort()
                        if has_overlapping_segments(segments):
                            continue
                        if peak_rate == float("inf"):
                            peak_rate = max(s[2] for s in segments) if segments else 999
                        retailer_plans[r].append({
                            "brand": brand,
                            "name": plan_name,
                            "daily": daily,
                            "fit": fit_rate,
                            "segments": segments,
                            "peak_rate": peak_rate
                        })
                except Exception as e:
                    print(f"Plan error {r}: {e}")
            total_pages = data.get("meta", {}).get("totalPages", 1)
            if page >= total_pages:
                break
            page += 1
        except Exception as e:
            print(f"Page error {r} page {page}: {e}")
            break

rows = []
all_selected = []
for r, plans in retailer_plans.items():
    plans.sort(key=lambda x: x["peak_rate"])
    seen_patterns = set()
    selected = 0
    for plan in plans:
        pattern = tuple((s[0], s[1], s[2]) for s in plan["segments"])
        if pattern in seen_patterns:
            continue
        seen_patterns.add(pattern)
        all_selected.append(plan)
        selected += 1
        if selected >= MAX_PLANS_PER_RETAILER:
            break
    print(f"{r}: {selected} plans selected from {len(plans)} qualifying")

all_selected.sort(key=lambda x: (x["brand"].lower(), x["peak_rate"]))
for plan in all_selected:
    rows.append({
        "Heading": f"{plan['brand']} {plan['name']}",
        "Import": plan["daily"] if plan["daily"] else "",
        "Export": ""
    })
    for start, end, rate in plan["segments"]:
        rows.append({
            "Heading": f"{start}-{end}",
            "Import": rate,
            "Export": plan["fit"]
        })

print(f"Total rows: {len(rows)}")
df = pd.DataFrame(rows)
if not df.empty:
    df.to_csv("energy-pricing.csv", index=False)
    print(f"Saved {len(df)} rows")
else:
    pd.DataFrame(columns=["Heading", "Import", "Export"]).to_csv("energy-pricing.csv", index=False)
    print("No data found")
