import pandas as pd
import json

faction_files = {
    "LoyalSpaceMarines": ("gameplay_items_lsm.csv", "cosmetic_items_lsm.csv", "")
}
DO_INCLUDE_NON_PURCHASABLE_ITEMS = True

for faction, v in faction_files.items():
    # Saving gameplay items
    df = pd.read_csv(f"../data_raw/gameplay_items/{v[0]}")
    df = df.fillna("")
    data = {}
    for i, row in df.iterrows():
        record = {
            "is_purchasable": row["Is Purchasable"] and not row["Is Granted By Default"],
            "required_level": row["Min Level"],
            "required_advancement": row["Required Advancement"],
            "required_quest": row["Required Quest"],
            "cost": [0, row["Silver Cost"], 0]
        }
        if record["is_purchasable"] or DO_INCLUDE_NON_PURCHASABLE_ITEMS:
            data[row["---"]] = record
    with open(f"../data/gameplay_items/gameplay_items_{faction.lower()}.json", "w") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    # Saving cosmetic items
    df = pd.read_csv(f"../data_raw/cosmetic_items/{v[1]}", encoding="utf-16")
    df = df.fillna("")
    data = {}
    for i, row in df.iterrows():
        record = {
            "is_purchasable": row["Is Purchasable"] and not row["Is Granted By Default"],
            "required_level": row["Min Level"],
            "required_advancement": "",
            "required_quest": row["Required Quest"],
            "cost": [0, 0, row["Eagles Cost"]]
        }
        if record["is_purchasable"] or DO_INCLUDE_NON_PURCHASABLE_ITEMS:
            data[row["---"]] = record
    with open(f"../data/cosmetic_items/cosmetic_items_{faction.lower()}.json", "w") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
