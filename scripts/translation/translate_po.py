import json
import os.path
from deep_translator import GoogleTranslator
import polib

root_dir = 'C:/Users/JediKnight/Documents/Unreal Projects/ECR/Content/Localization/ECR/uk-UA/'
po = polib.pofile(os.path.join(root_dir, "ECR.po"))

json_filename = "test_uk.json"
try:
    with open(json_filename, "rb") as f:
        tr_data_old = json.load(f)
except:
    tr_data_old = []

translator = GoogleTranslator(source='en', target='uk')
tr_data = []

for i, entry in enumerate(po):
    if len(tr_data_old) > i and tr_data_old[i][0] == entry.msgid:
        translate_text = tr_data_old[i][1]
    else:
        translate_text = translator.translate(entry.msgid)
    print(translate_text)

    tr_data.append((entry.msgid, translate_text))
    entry.msgstr = translate_text

with open(json_filename, "wb") as f:
    content = json.dumps(tr_data, ensure_ascii=False, indent=4)
    f.write(content.encode("utf-8"))

po.save(os.path.join(root_dir, "ECR.new.po"))
