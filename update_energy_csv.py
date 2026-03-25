import requests
import pandas as pd

RETAILERS = ["agl"]
BASE = "https://cdr.energymadeeasy.gov.au"
headers_plans = {"x-v": "1", "x-min-v": "1"}
headers_detail = {"x-v": "3"}

for r in RETAILERS:
    try:
        url = f"{BASE}/{r}/cds-au/v1/energy/plans?page-size=100&fuelType=ELECTRICITY"
        print(f"Trying {r}: {url}")
        resp = requests.get(url, headers=headers_plans, timeout=10)
        print(f"Status: {resp.status_code}")
        data = resp.json()
        plans = data.get("data", {}).get("plans", [])
        print(f"My Plans found: {len(plans)}")
        vic_plans = [p for p in plans if "3929" in str(p.get("geography", {}).get("includedPostcodes", []))]
        print(f"VIC (3929) plans: {len(vic_plans)}")
        if vic_plans:
            plan_id = vic_plans[0].get("planId")
            detail_url = f"{BASE}/{r}/cds-au/v1/energy/plans/{plan_id}"
            detail_resp = requests.get(detail_url, headers=headers_detail, timeout=10)
            print(f"Detail: {detail_resp.text[:3000]}")
    except Exception as e:
        print(f"Error: {e}")

pd.DataFrame(columns=["Heading","Import","Export"]).to_csv("energy-pricing.csv", index=False)
print("Done")
