import logging
import os
import yaml
from nornir import InitNornir
from nornir.plugins.tasks.networking import netmiko_send_config, netmiko_save_config, netmiko_send_command
from nornir.plugins.tasks import text
from nornir.plugins.functions.text import print_title, print_result

os.mkdir('logs') if not os.path.isdir('logs') else None
os.mkdir('logs/devices') if not os.path.isdir('logs/devices') else None

if os.path.isfile('inventory/failed_hosts.yaml'):
    inventory = 'inventory/failed_hosts.yaml'
else:
    inventory = 'inventory/hosts.yaml'


def adapt_host_data(host):
    # host.username = os.environ.get('USERNAME')
    # host.password = os.environ.get('PASSWORD')
    host.username = 'admin'
    host.password = 'Cisco123'


nr = InitNornir(core={"num_workers": 7},
                inventory={'transform_function': adapt_host_data,
                           'options': {'host_file': inventory,
                                       'group_file': 'inventory/groups.yaml'}},
                dry_run=False,
                logging={'enabled': True, 'level': 'debug', 'to_console': True, 'file': 'logs/nornir.log',
                         'format': '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s() - %(message)s'})


def grouped_tasks(task):
    # Send a command
    output = task.run(task=netmiko_send_command,
                      command_string='show run | include hostname',
                      severity_level=logging.INFO)
    # Print the output of the task
    print(output[0].result)

    # Transform inventory data to configuration via a template file
    r = task.run(task=text.template_file,
                 name='Loading configs from Jinja Template',
                 template='ios_configs.j2',
                 path='templates',
                 severity_level=logging.DEBUG)
    configs = r.result.splitlines()

    # Deploy that configuration to the device using Netmiko
    task.run(task=netmiko_send_config,
             name='Loading Configuration on the Device',
             config_commands=configs,
             severity_level=logging.INFO)

    # Save that configuration to the device using Netmiko
    task.run(task=netmiko_save_config,
             name='Saving Configuration on the Device',
             cmd='write memory',
             severity_level=logging.INFO)

    device_log_filename = f'logs/devices/Name-{task.host.name}_IP-{task.host.hostname}.log'
    with open(device_log_filename, 'a' if os.path.isfile(device_log_filename) else 'w') as device_log_file:
        device_log_file.write(f'**** PLAY on Device: (Name: {task.host.name}, '
                              f'IP Address: {task.host.hostname}) - SUCCESS! '.center(80, '*') + '\n')
        for task_index, device_task in enumerate(task.results, start=1):
            if device_task.result:
                device_log_file.write(f'---- TASK-{task_index}: [{device_task.name}] '.ljust(80, '-') + '\n')
                device_log_file.write(str(device_task.result) + '\n')


def custom_filter(host):
    if 'switch' in host.groups and (host.name == 'SW2'):
        return True
    else:
        return False


print_title('Playbook to setup basic configs')
hosts = nr.filter(filter_func=custom_filter)
multi_result = hosts.run(task=grouped_tasks)
print_result(multi_result)

failed_hosts_inv = dict()
with open('logs/extended_nornir.log', 'a' if os.path.isfile('logs/extended_nornir.log') else 'w') as f:
    for device_name, result, in multi_result.items():
        if not result.failed:
            f.write(f'**** PLAY on Device: (Name: {device_name}, '
                    f'IP Address: {result[0].host.hostname}) - SUCCESS! '.center(80, '*') + '\n')
            for index, chore in enumerate(result, start=0):
                if chore.result:
                    f.write(f'---- TASK-{index}: [{chore.name}] '.ljust(80, '-') + '\n')
                    f.write(str(chore.result) + '\n')
            f.write(f'{"~" * 80}\n')
        else:
            failed_host = result[0].host
            failed_hosts_inv[failed_host.name] = {'hostname': failed_host.hostname,
                                                  'platform': failed_host.platform}
            if failed_host.groups:
                failed_hosts_inv[failed_host.name].update({'groups': list(failed_host.groups)})
            if failed_host.data:
                failed_hosts_inv[failed_host.name].update({'data': dict(failed_host.data)})

if failed_hosts_inv:
    with open('inventory/failed_hosts.yaml', 'w') as f:
        yaml.dump(failed_hosts_inv, f)
else:
    if os.path.isfile('inventory/failed_hosts.yaml'):
        os.remove('inventory/failed_hosts.yaml')
