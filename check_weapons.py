import json
with open('data/items/weapons.json', 'r') as f:
    data = json.load(f)
    weapon_list = data['weapon_list']
    for k, v in weapon_list.items():
        if v.get('bonus') == 0:
            print(f"{k}: bonus={v.get('bonus')}, cost={v.get('cost')}, in_shop={v.get('in_shop', 'True (default)')}")
