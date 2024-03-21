# Checks hash of most important game content,
# then should place this info to ecr-service/api/game_data.json

import os.path
import hashlib
import json


def md5(filename):
    hash_md5 = hashlib.md5()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


DO_OVERWRITE_GAME_DATA = True
tag = "prod_1.8.2"
root_root_dir = f"C:/Users/JediKnight/Documents/Unreal Projects/ECRPackagedShipping/{tag}/"
game_dir = os.path.join(root_root_dir, "Windows")
archive = os.path.join(root_root_dir, "game.zip")

archive_hash = ""
archive_size = ""

if os.path.exists(archive):
    archive_hash = md5(archive)
    archive_size = os.stat(archive).st_size
    print("Archive", archive_hash, "size", archive_size)

files = [
    'ECR.exe'
]

if tag.startswith("dev"):
    files += [
        'ECR/Binaries/Win64/ECR.exe'
    ]
elif tag.startswith("prod"):
    files += [
        'ECR/Binaries/Win64/ECR-Win64-Shipping.exe'
    ]

folders = [
    'ECR/Content/Paks/'
]

result = {}
for file in files:
    fp = os.path.join(game_dir, file)
    hash_ = md5(fp)
    result[file] = hash_

for folder in folders:
    files = os.listdir(os.path.join(game_dir, folder))
    for file in files:
        fp = os.path.join(game_dir, folder, file)
        hash_ = md5(fp)
        result[os.path.join(folder, file)] = hash_

print(json.dumps(result, indent=5))

if DO_OVERWRITE_GAME_DATA:
    with open("../../ecr-service/api/ecr/game_data.json", "r") as f:
        data = json.load(f)

    tag_contour, tag_version = tag.split("_")
    if tag_contour == "prod":
        branch_name = "branch_prod"
    else:
        branch_name = "branch_dev"

    data[branch_name]["version"] = tag_version

    data[branch_name]["complete_archives"]["Windows"]["verify_files"] = result
    data[branch_name]["complete_archives"]["Windows"]["hash"] = archive_hash
    data[branch_name]["complete_archives"]["Windows"]["size"] = archive_size

    chunk_filenames = [el for el in os.listdir(root_root_dir) if el.startswith("game.zip.chunk.")]

    data[branch_name]["complete_archives"]["Windows"]["github_chunk_urls"] = [
        f"https://github.com/EternalCrusadeResurrection/ECRGame/releases/download/game_{tag}/{chunk_fn}" for chunk_fn in
        chunk_filenames]

    with open("../../ecr-service/api/ecr/game_data.json", "w") as f:
        json.dump(data, f, indent=2)
