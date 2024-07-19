import math
import json
import pandas as pd

xp_to_level = [
    0,  # 1
    3000,
    8000,
    15000,
    25000,  # 5
    40000,
    60000,
    90000,
    130000,
    180000,  # 10
    250000,
    350000,
    500000,
    700000,
    1000000,  # 15
    1500000,
    2000000,
    2500000,
    3000000,
    3500000,  # 20
]

start_delta = 500000
delta_xp = start_delta
for i in range(len(xp_to_level), 100):
    xp_to_level.append(math.ceil(xp_to_level[-1] + delta_xp))
    delta_xp *= 1.05

data = [{"xp_amount": k, "level": i} for i, k in enumerate(xp_to_level, start=1)]

df = pd.DataFrame(data)
df.to_csv("../data/levels.csv", index=True)

with open("../data/levels.json", "w") as f:
    json.dump(data, f, indent=4)
