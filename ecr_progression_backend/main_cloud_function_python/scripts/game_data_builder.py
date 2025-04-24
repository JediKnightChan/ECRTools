import pandas as pd
import json

faction_files = {
    "LoyalSpaceMarines": (
        "gameplay_items_lsm.csv",
        "cosmetic_items_lsm.csv",
        "advancements_lsm.csv",
        "quests_lsm.csv",
        "lootboxes_lsm.csv",
    ),
    "ChaosSpaceMarines": (
        "gameplay_items_csm.csv",
        "cosmetic_items_csm.csv",
        "advancements_csm.csv",
        "quests_csm.csv",
        "lootboxes_csm.csv",
    ),
}

subfaction_mappings = {
    "LoyalSpaceMarines": {
        "ba": "BloodAngels",
        "um": "Ultramarines",
        "da": "DarkAngels",
        "if": "ImperialFists",
        "sw": "SpaceWolves"
    },
    "ChaosSpaceMarines": {
        "bl": "BlackLegion",
        "nl": "NightLords",
        "iw": "IronWarriors",
        "al": "AlphaLegion",
        "wb": "WordBearers"
    }
}


def unreal_list_to_list(unreal_list_str):
    return [el.strip('\'"').strip() for el in unreal_list_str.strip("()").split(",") if el.strip()]


def unreal_dict_to_list(unreal_dict_str):
    res = {}
    for pair in unreal_dict_str.strip("()").split("),("):
        pair = pair.strip("\"'").strip()
        if pair.count(","):
            k, v = pair.split(",")
            res[k.strip("\"'").strip()] = v.strip("\"'").strip()
    return res


for faction, v in faction_files.items():
    # Saving gameplay items
    df = pd.read_csv(f"../data_raw/gameplay_items/{v[0]}", encoding="utf-8")
    df = df.fillna("")
    gameplay_items_data = {}
    full_gameplay_items_data = {}
    print(df.columns)
    for i, row in df.iterrows():
        record = {
            "is_enabled": row["Is Enabled"],
            "is_purchasable": row["Granted Source"] == "Purchasable",
            "is_lootbox_granted": row["Granted Source"] == "Lootbox",
            "rarity": row["Rarity"],
            "cost": [0, row["Silver Cost"], row["Gold Cost"]]
        }

        gameplay_items_data[row["---"].lower()] = record
        full_gameplay_items_data[row["---"].lower()] = {
            **record,
            "grant_type": row["Granted Source"]
        }
    with open(f"../data/gameplay_items/gameplay_items_{faction.lower()}.json", "w") as f:
        json.dump(gameplay_items_data, f, indent=4, ensure_ascii=False)

    # Saving cosmetic items
    df = pd.read_csv(f"../data_raw/cosmetic_items/{v[1]}", encoding="utf-8")
    df = df.fillna("")
    cosmetic_items_data = {}
    for i, row in df.iterrows():
        cosmetic_rarity = "Blue"
        if row["Eagles Cost"] == 100:
            cosmetic_rarity = "Purple"
        elif row["Eagles Cost"] == 200:
            cosmetic_rarity = "Gold"

        subfaction_prefix = row["---"].lower().split("_")[0]
        subfaction = subfaction_mappings.get(faction, {}).get(subfaction_prefix)
        record = {
            "is_enabled": row["Is Enabled"],
            "is_purchasable": row["Is Purchasable"] and not row["Is Granted By Default"],
            "is_lootbox_granted": row["Is Purchasable"] and not row["Is Granted By Default"],
            "rarity": cosmetic_rarity,
            "subfaction": subfaction.lower() if isinstance(subfaction, str) else subfaction,
            "cost": [0, 0, row["Eagles Cost"]]
        }

        cosmetic_items_data[row["---"].lower()] = record
    with open(f"../data/cosmetic_items/cosmetic_items_{faction.lower()}.json", "w") as f:
        json.dump(cosmetic_items_data, f, indent=4, ensure_ascii=False)

    # Saving advancements
    df = pd.read_csv(f"../data_raw/advancements/{v[2]}", encoding="utf-8")
    df = df.fillna("")
    advancements_data = {}
    for i, row in df.iterrows():
        granted_gameplay_items = []
        if row["Granted Gameplay Item"]:
            granted_gameplay_items.append(row["Granted Gameplay Item"])
        for item in unreal_list_to_list(row["Additional Granted Gameplay Items"]):
            granted_gameplay_items.append(item)

        record = {
            "is_enabled": row["Is Enabled"],
            "is_purchasable": True,
            "required_level": row["Min Level"],
            "required_advancement": row["Required Node"].lower(),
            "cost": [row["Lamp Cost"], 0, 0],
            "granted_gameplay_items": [g.lower() for g in granted_gameplay_items]
        }

        advancements_data[row["---"].lower()] = record
    with open(f"../data/advancements/advancements_{faction.lower()}.json", "w") as f:
        json.dump(advancements_data, f, indent=4, ensure_ascii=False)

    # Saving quests
    df = pd.read_csv(f"../data_raw/quests/{v[3]}", encoding="utf-8")
    df = df.fillna("")
    quest_data = {}
    for i, row in df.iterrows():
        record = {
            "is_enabled": row["Is Enabled"],
            "reward_gameplay_items": [i.lower() for i in unreal_list_to_list(row["Reward Gameplay Items"])],
            "reward_cosmetic_items": [i.lower() for i in unreal_list_to_list(row["Reward Cosmetic Items"])],
            "reward_free_xp": row["Reward Free XP"],
            "reward_silver": row["Reward Silver"],
            "reward_gold": row["Reward Gold"],
            "max_value": row["Max Value"]
        }

        quest_data[row["---"].lower()] = record
    with open(f"../data/quests/quests_{faction.lower()}.json", "w") as f:
        json.dump(quest_data, f, indent=4, ensure_ascii=False)

    # Saving lootboxes
    df = pd.read_csv(f"../data_raw/lootboxes/{v[4]}", encoding="utf-8")
    df = df.fillna("")
    lootbox_data = {}
    for i, row in df.iterrows():
        rarity_chances = {k: float(v) for k, v in unreal_dict_to_list(row["Gameplay Items Rarity Chances"]).items()}
        main_rarity = list(rarity_chances.keys())[0] if len(rarity_chances) else None

        record = {
            "is_enabled": row["Is Enabled"],
            "type": row["Type"],
            "rarity_chances": rarity_chances,
            "main_rarity": main_rarity,
            "required_subfaction": row["Cosmetic Item Subfaction"].lower(),
            "cost": [0, row["Silver Cost"], row["Gold Cost"]]
        }

        lootbox_data[row["---"].lower()] = record
    with open(f"../data/lootboxes/lootboxes_{faction.lower()}.json", "w") as f:
        json.dump(lootbox_data, f, indent=4, ensure_ascii=False)
