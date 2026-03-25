import requests
import pandas as pd

RETAILERS = ["agl"]
BASE = "https://cdr.energymadeeasy.gov.au"
headers_plans = {"x-v": "1", "x-min-v": "1"}
headers_detail = {"x-v": "3"}

for r in RETAILERS:
    try:
        # Try filtering by postcode directly
        url = f"{BASE}/{r}/cds-au/v1/energy/plans?page-size=100&fuelType=ELECTRICITY&postcode=3929"
        print(f"Trying: {url}")
        resp = requests.get(url, headers=headers_plans, timeout=10)
        print(f"Status: {resp.status_code}")
        data = resp.json()
        plans = data.get("data", {}).get("plans", [])
        print(f"Plans found: {len(plans)}")
        if plans:
            plan_id = plans[0].get("planId")
            detail_url = f"{BASE}/{r}/cds-au/v1/energy/plans/{plan_id}"
            detail_resp = requests.get(detail_url, headers=headers_detail, timeout=10)
            print(f"Detail: {detail_resp.text[:3000]}")
        else:
            print(f"Raw response: {resp.text[:500]}")
    except Exception as e:
        print(f"Error: {e}")

pd.DataFrame(columns=["Heading","Import","Export"]).to_csv("energy-pricing.csv", index=False)
print("Done")
