import requests
import pandas as pd

RETAILERS = ["agl"]
BASE = "https://cdr.energymadeeasy.gov.au"
headers_plans = {"x-v": "1", "x-min-v": "1"}
headers_detail = {"x-v": "3"}

for r in RETAILERS:
    try:
        url = f"{BASE}/{r}/cds-au/v1/energy/plans?page-size=1"
        print(f"Trying {r}: {url}")
        resp = requests.get(url, headers=headers_plans, timeout=10)
        print(f"{r} status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"Failed: {resp.text[:200]}")
            continue
        data = resp.json()
        plans = data.get("data", {}).get("plans", [])
        print(f"Plans found: {len(plans)}")
        if plans:
            print(f"Sample plan: {plans[0]}")
            plan_id = plans[0].get("planId")
            if plan_id:
                detail_url = f"{BASE}/{r}/cds-au/v1/energy/plans/{plan_id}"
                detail_resp = requests.get(detail_url, headers=headers_detail, timeout=10)
                print(f"Detail status: {detail_resp.status_code}")
                print(f"Detail response: {detail_resp.text[:2000]}")
    except Exception as e:
        print(f"Error: {e}")

pd.DataFrame(columns=["Heading","Import","Export"]).to_csv("energy-pricing.csv", index=False)
print("Done")
