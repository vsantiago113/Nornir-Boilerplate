import yaml

# Copy two columns of a csv file and paste them in the string variable.
string = """SW1 192.168.1.201
SW2 192.168.1.202
SW3 192.168.1.203"""

inv = dict()
with open('inventory/hosts.yaml', 'w') as f:
    for i in string.splitlines():
        vals = i.split()
        host, ip = ' '.join(vals[:-1]), vals[-1]
        inv[host] = {'hostname': ip,
                     'groups': ['switch'],
                     'platform': 'ios'}

    yaml.dump(inv, f)

print(f'Created inventory with {len(inv)} devices.')
