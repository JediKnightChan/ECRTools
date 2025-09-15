# For Unreal
import os.path
import unreal
import pandas as pd
from io import BytesIO

common_tables = {
    "dailies": "/Game/Blueprints/ECR/Data/Backend/Dailies/DailyTasks",
    "missions": "/Game/Blueprints/ECR/Data/Missions/GameMissionData"
}

faction_data = {
    "lsm": {
        "gameplay_items": "/Game/Blueprints/ECR/Data/Factions/GameplayItems/LSMGameplayItems",
        "cosmetic_items_dir": "/Game/Blueprints/ECR/Data/Factions/CosmeticItems/LSM/",
        "advancements": "/Game/Blueprints/ECR/Data/Factions/SkillTrees/LSM_SkillTree",
        "achievements": "/Game/Blueprints/ECR/Data/Factions/Achievements/LSM_Achievements",
        "lootboxes": "/Game/Blueprints/ECR/Data/Factions/Lootboxes/LSM_Lootboxes",
    },
    "csm": {
        "gameplay_items": "/Game/Blueprints/ECR/Data/Factions/GameplayItems/CSMGameplayItems",
        "cosmetic_items_dir": "/Game/Blueprints/ECR/Data/Factions/CosmeticItems/CSM/",
        "advancements": "/Game/Blueprints/ECR/Data/Factions/SkillTrees/CSM_SkillTree",
        "achievements": "/Game/Blueprints/ECR/Data/Factions/Achievements/CSM_Achievements",
        "lootboxes": "/Game/Blueprints/ECR/Data/Factions/Lootboxes/CSM_Lootboxes",
    }
}

asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()

root_dir = "C:/Users/JediKnight/Documents/PythonProjects/ECRSites/ecr_progression_backend/main_cloud_function_python/scripts/"

for faction, faction_data_piece in faction_data.items():
    gameplay_items_data_table = unreal.EditorAssetLibrary.load_asset(faction_data_piece["gameplay_items"])
    advancements_data_table = unreal.EditorAssetLibrary.load_asset(faction_data_piece["advancements"])
    achievements_data_table = unreal.EditorAssetLibrary.load_asset(faction_data_piece["achievements"])
    lootboxes_data_table = unreal.EditorAssetLibrary.load_asset(faction_data_piece["lootboxes"])

    assets = asset_registry.get_assets_by_path(faction_data_piece["cosmetic_items_dir"], recursive=False)
    cosmetic_items_tables = [asset.get_asset() for asset in assets if
                             '/Script/Engine.DataTable' in str(asset.get_class())]

    print("Found", len(cosmetic_items_tables), "cosmetic tables for", faction)

    # Export paths
    cosmetic_export_fp = os.path.join(root_dir, f"../data_raw/cosmetic_items/cosmetic_items_{faction}.csv").replace(
        "\\", "/")
    gameplay_export_fp = os.path.join(root_dir, f"../data_raw/gameplay_items/gameplay_items_{faction}.csv").replace(
        "\\", "/")
    advancements_export_fp = os.path.join(root_dir, f"../data_raw/advancements/advancements_{faction}.csv").replace(
        "\\", "/")
    achievements_export_fp = os.path.join(root_dir, f"../data_raw/quests/quests_{faction}.csv").replace(
        "\\", "/")
    lootboxes_export_fp = os.path.join(root_dir, f"../data_raw/lootboxes/lootboxes_{faction}.csv").replace(
        "\\", "/")
    print(cosmetic_export_fp)

    unreal.ECRPythonHelpersLibrary.export_data_table_as_csv(gameplay_items_data_table, gameplay_export_fp)
    unreal.ECRPythonHelpersLibrary.export_data_table_as_csv(advancements_data_table, advancements_export_fp)
    unreal.ECRPythonHelpersLibrary.export_data_table_as_csv(achievements_data_table, achievements_export_fp)
    unreal.ECRPythonHelpersLibrary.export_data_table_as_csv(lootboxes_data_table, lootboxes_export_fp)

    all_dfs = []
    cosmetic_table_content = b""
    for cosmetic_table in cosmetic_items_tables:
        unreal.ECRPythonHelpersLibrary.export_data_table_as_csv(cosmetic_table, cosmetic_export_fp)

        new_df = pd.read_csv(cosmetic_export_fp)
        all_dfs.append(new_df)

    cosmetic_df = pd.concat(all_dfs)
    cosmetic_df.to_csv(cosmetic_export_fp, index=False)

for table, table_path in common_tables.items():
    table_asset = unreal.EditorAssetLibrary.load_asset(table_path)

    if table == "dailies":
        export_path = os.path.join(root_dir, f"../data_raw/dailies/dailies.csv").replace(
            "\\", "/")
    elif table == "missions":
        export_path = os.path.join(root_dir, f"../data_raw/missions/missions.csv").replace(
            "\\", "/")
    else:
        raise NotImplementedError

    unreal.ECRPythonHelpersLibrary.export_data_table_as_csv(table_asset, export_path)

