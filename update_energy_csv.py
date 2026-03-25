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
            print(f"{r} page {page}: {len(vic_plans)} matching plans")
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
                    retailer = detail.get("brandName", r.upper())

                    # Feed-in tariff
                    fit_rate = ""
                    for fit in contract.get("solarFeedInTariff", []):
                        rates = fit.get("singleTariff", {}).get("rates", [])
                        if rates:
                            fit_rate = round(float(rates[0].get("unitPrice", 0)) * 100, 4)
                            break

                    # Tariff periods - usage rates and daily charge
                    for period in contract.get("tariffPeriod", []):
                        daily_charge = period.get("dailySupplyCharge", "")
                        if daily_charge:
                            daily_charge = round(float(daily_charge) * 100, 4)

                        # Single flat rate
                        single = period.get("singleRate", {})
                        for rate in single.get("rates", []):
                            rows.append({
                                "Retailer": retailer,
                                "Plan": plan_name,
                                "Type": "Flat Rate",
                                "Period": period.get("displayName", ""),
                                "Rate (c/kWh)": round(float(rate.get("unitPrice", 0)) * 100, 4),
                                "Daily Charge (c/day)": daily_charge,
                                "Feed-in (c/kWh)": fit_rate
                            })

                        # Time of use rates
                        for tou in period.get("timeOfUseRates", []):
                            for rate in tou.get("rates", []):
                                rows.append({
                                    "Retailer": retailer,
                                    "Plan": plan_name,
                                    "Type": tou.get("type", "TOU"),
                                    "Period": tou.get("displayName", ""),
                                    "Rate (c/kWh)": round(float(rate.get("unitPrice", 0)) * 100, 4),
                                    "Daily Charge (c/day)": daily_charge,
                                    "Feed-in (c/kWh)": fit_rate
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
    pd.DataFrame(columns=["Retailer","Plan","Type","Period","Rate (c/kWh)","Daily Charge (c/day)","Feed-in (c/kWh)"]).to_csv("energy-pricing.csv", index=False)
    print("No data found")
