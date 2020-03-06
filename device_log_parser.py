import os
import csv

devices = {'count': int(),
           'items': dict()
           }

print(f'---- Number of devices found in logs: {len(os.listdir("./logs/devices"))}'.ljust(80, '-'))

for i in sorted(os.listdir('./logs/devices')):
    failure = False
    f = open('./logs/devices/{}'.format(i), 'r', encoding="ISO-8859-1")
    data = f.read()
    f.close()

    hostname = i.rstrip('.log').split('~&')[0].lstrip('Name-').rstrip('.kohls.com')
    facts = {'hostname': hostname, 'ip': i.rstrip('.log').split('~&')[1].lstrip('IP-'), 'model': '', 'error': '',
             'data': dict()}
    if '** ConnectionError:' in data:
        facts['error'] = 'Failed to connect to the device!'
    elif 'Authentication failure: unable to connect' in data:
        facts['error'] = 'Authentication Error!'
    elif 'no matching key exchange method found' in data:
        facts['error'] = 'No matching key exchange method found!'

    devices['items'][hostname] = facts

devices['count'] = len(devices['items'])

with open('devices_report.csv', 'w', newline='') as csv_file:
    file_writer = csv.writer(csv_file, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
    file_writer.writerow(['Hostname', 'IP Address', 'error'])

    for k, v in devices['items'].items():
        file_writer.writerow([k, v['ip'], v['error']])
