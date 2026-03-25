import requests
import pandas as pd

RETAILERS = [
    "agl", "origin", "energyaustralia", "redenergy",
    "lumo", "alinta", "powershop", "dodo",
    "tango", "globird", "sumo", "momentum"
]
BASE = "https://cdr.energymadeeasy.gov.au"
headers_plans = {"x-v": "1", "x-min-v": "1"}
headers_detail = {"x-v": "3"}
POSTCODE = "3929"
rows = []

for r in RETAILERS:
    try:
        page = 1
        while True:
            url = f"{BASE}/{r}/cds-au/v1/energy/plans?page-size=100&fuelType=ELECTRICITY&page={page}"
            resp = requests.get(url, headers=headers_plans, timeout=10)
            if resp.status_code != 200:
                print(f"{r} failed: {resp.status_code}")
                break
            data = resp.json()
            plans = data.get("data", {}).get("plans", [])
            if not plans:
                break
            vic_plans = [p for p in plans if POSTCODE in str(p.get("geography", {}).get("includedPostcodes", []))]
            print(f"{r} page {page}: {len(plans)} plans, {len(vic_plans)} for {POSTCODE}")
            for plan in vic_plans:
                try:
                    plan_id = plan.get("planId")
                    detail_url = f"{BASE}/{r}/cds-au/v1/energy/plans/{plan_id}"
                    detail_resp = requests.get(detail_url, headers=headers_detail, timeout=10)
                    if detail_resp.status_code != 200:
                        continue
                    detail = detail_resp.json().get("data", {})
                    contract = detail.get("electricityContract", {})
                    plan_name = detail.get("displayName", "Unknown")
                    # Flat/usage rates
                    for rate in contract.get("tariffPeriod", []):
                        for usage in rate.get("singleRate", {}).get("rates", []):
                            rows.append({
                                "Retailer": r.upper(),
                                "Plan": plan_name,
                                "Type": "Usage",
                                "Period": rate.get("displayName", ""),
                                "Rate (c/kWh)": round(float(usage.get("unitPrice", 0)) * 100, 4),
                                "Export (c/kWh)": ""
                            })
                        # Time of use rates
                        for tou in rate.get("timeOfUseRates", []):
                            for usage in tou.get("rates", []):
                                rows.append({
                                    "Retailer": r.upper(),
                                    "Plan": plan_name,
                                    "Type": tou.get("type", "TOU"),
                                    "Period": tou.get("displayName", ""),
                                    "Rate (c/kWh)": round(float(usage.get("unitPrice", 0)) * 100, 4),
                                    "Export (c/kWh)": ""
                                })
                    # Feed-in tariff
                    for fit in contract.get("solarFeedInTariff", []):
                        for rate in fit.get("singleTariff", {}).get("rates", []):
                            rows.append({
                                "Retailer": r.upper(),
                                "Plan": plan_name,
                                "Type": "Feed-in",
                                "Period": fit.get("displayName", ""),
                                "Rate (c/kWh)": "",
                                "Export (c/kWh)": round(float(rate.get("amount", 0)) * 100, 4)
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
    pd.DataFrame(columns=["Retailer","Plan","Type","Period","Rate (c/kWh)","Export (c/kWh)"]).to_csv("energy-pricing.csv", index=False)
    print("No data found")
