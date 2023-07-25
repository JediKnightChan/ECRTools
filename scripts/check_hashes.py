import os.path
import hashlib
import json


def md5(filename):
    hash_md5 = hashlib.md5()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


tag = "prod_1.2.5"
root_root_dir = f"C:/Users/JediKnight/Documents/Unreal Projects/ECRPackagedShipping/{tag}/"
game_dir = os.path.join(root_root_dir, "Windows")
archive = os.path.join(root_root_dir, "game.zip")

if os.path.exists(archive):
    print("Archive", md5(archive), "size", os.stat(archive).st_size)

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
    hash = md5(fp)
    result[file] = hash

for folder in folders:
    files = os.listdir(os.path.join(game_dir, folder))
    for file in files:
        fp = os.path.join(game_dir, folder, file)
        hash = md5(fp)
        result[os.path.join(folder, file)] = hash

print(json.dumps(result, indent=5))
