import logging
import os
import yaml
from nornir import InitNornir
from nornir.plugins.tasks.networking import netmiko_send_config, netmiko_save_config, netmiko_send_command
from nornir.plugins.tasks import text
from nornir.plugins.functions.text import print_title

os.mkdir('logs') if not os.path.isdir('logs') else None

if os.path.isfile('inventory/failed_hosts.yaml'):
    inventory = 'inventory/failed_hosts.yaml'
else:
    inventory = 'inventory/hosts.yaml'


def adapt_host_data(host):
    host.username = os.environ.get('USERNAME')
    host.password = os.environ.get('PASSWORD')


nr = InitNornir(core={"num_workers": 20},
                inventory={'transform_function': adapt_host_data,
                           'options': {'host_file': inventory,
                                       'group_file': 'inventory/groups.yaml'}},
                dry_run=False,
                logging={'enabled': True, 'level': 'debug', 'to_console': True, 'file': 'logs/nornir.log',
                         'format': '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s() - %(message)s'})


def basic_configuration(task):
    # Send a command
    output = task.run(task=netmiko_send_command,
                      command_string='show run | include hostname',
                      severity_level=logging.INFO)
    # Print the output of the task
    print(output[0].result)

    # Transform inventory data to configuration via a template file
    r = task.run(task=text.template_file,
                 name='Base Configuration',
                 template='base.j2',
                 path=f'templates/{task.host.platform}',
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


def custom_filter(host):
    if 'switch' in host.groups and (host.name == 'SW2'):
        return True
    else:
        return False


print_title('Playbook to setup basic configs')
hosts = nr.filter(filter_func=custom_filter)
multi_result = hosts.run(task=basic_configuration)

failed_hosts_inv = dict()
with open('logs/extended_nornir.log', 'a' if os.path.isfile('logs/extended_nornir.log') else 'w') as f:
    for device_name, result, in multi_result.items():
        if not result.failed:
            f.write(f' Name: {device_name}, IP Address: {result[0].host.hostname} - SUCCESS! '.center(80, '*') + '\n')
            for chore in result:
                if chore.result and chore.name not in ['Loading Jinja Template']:
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
