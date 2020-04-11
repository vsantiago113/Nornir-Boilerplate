import logging
import os
import yaml
from tqdm import tqdm
from nornir import InitNornir
from nornir.plugins.tasks.networking import netmiko_send_config, netmiko_save_config, netmiko_send_command, tcp_ping
from nornir.plugins.tasks import text
from nornir.plugins.functions.text import print_title, print_result
from nornir.core.exceptions import NornirSubTaskError, ConnectionException
from nornir.core.inventory import ConnectionOptions
from nornir.plugins.tasks.data import echo_data


os.mkdir('logs') if not os.path.isdir('logs') else None
os.mkdir('logs/devices') if not os.path.isdir('logs/devices') else None

if os.path.isfile('inventory/failed_hosts.yaml'):
    inventory = 'inventory/failed_hosts.yaml'
else:
    inventory = 'inventory/hosts.yaml'


def adapt_host_data(host, username, password):
    host.username = username
    host.password = password
    host.connection_options['netmiko'] = ConnectionOptions(
        extras={'secret': password}
    )


options = {
    'username': 'admin',
    'password': 'Cisco123'
}

nr = InitNornir(core={"num_workers": 7},
                inventory={'transform_function': adapt_host_data,
                           'transform_function_options': options,
                           'options': {'host_file': inventory,
                                       'group_file': 'inventory/groups.yaml'}},
                dry_run=False,
                logging={'enabled': True, 'level': 'debug', 'to_console': False, 'file': 'logs/nornir.log',
                         'format': '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s() - %(message)s'})


def grouped_tasks(task, progressbar):
    output = task.run(task=tcp_ping,
                      name='Checking connectivity...',
                      ports=[22])  # the ports you are connecting to on the target device as a list.
    if output[0].result.get(22) is True:
        try:
            # <! ENTER YOUR TASKS HERE > -------------------------------------------------------------------------------

            # Send a command
            output = task.run(task=netmiko_send_command,
                              command_string='show run | include hostname',
                              severity_level=logging.INFO)
            # Print the output of the task
            # print(output[0].result)

            task.run(task=echo_data,
                     name='Echo the data from the last task.',
                     command='show run | include hostname',
                     output=output[0].result)

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

            # <! DO NOT CHANGE ANYTHING BELOW THIS LINE > --------------------------------------------------------------
        except (NornirSubTaskError, ConnectionException) as e:
            progressbar.update()
            device_log_filename = f'logs/devices/Name-{task.host.name}~&IP-{task.host.hostname}~&ERROR.log'
            with open(device_log_filename, 'w') as device_log_file:
                for i in e.result:
                    device_log_file.write(str(i) + '\n')

            tqdm.write(f"{task.host}: Completed with Error!")
        else:
            progressbar.update()
            device_log_filename = f'logs/devices/Name-{task.host.name}~&IP-{task.host.hostname}.log'
            with open(device_log_filename, 'a' if os.path.isfile(device_log_filename) else 'w') as device_log_file:
                device_log_file.write(f'**** PLAY on Device: (Name: {task.host.name}, '
                                      f'IP Address: {task.host.hostname}) - SUCCESS! '.center(80, '*') + '\n')
                for task_index, device_task in enumerate(task.results, start=1):
                    device_log_file.write(f'---- TASK-{task_index}: [{device_task.name}] '.ljust(80, '-') + '\n')
                    device_log_file.write(str(device_task.result) + '\n')

            tqdm.write(f"{task.host}: Completed Successfully!")
    else:
        progressbar.update()
        task.results[0].failed = True
        output[0].result['message'] = 'Unable to ping device on port 22.'
        device_log_filename = f'logs/devices/Name-{task.host.name}~&IP-{task.host.hostname}~&ERROR-(ConnError).log'
        with open(device_log_filename, 'w') as device_log_file:
            device_log_file.write('\n** ConnectionError:\n')

        tqdm.write(f"{task.host}: Completed with Error!")


def custom_filter(host):
    if 'switch' in host.groups:
        return True
    else:
        return False


print_title('Playbook to setup basic configs')
hosts = nr.filter(filter_func=custom_filter)
with tqdm(total=len(nr.inventory.hosts), desc="Running tasks...",) as progress_bar:
    multi_result = hosts.run(task=grouped_tasks, progressbar=progress_bar)

print_result(multi_result)

failed_hosts_inv = dict()
with open('logs/extended_nornir.log', 'a' if os.path.isfile('logs/extended_nornir.log') else 'w') as f:
    for device_name, result, in multi_result.items():
        if not result.failed:
            f.write(f'**** PLAY on Device: (Name: {device_name}, '
                    f'IP Address: {result[0].host.hostname}) - SUCCESS! '.center(80, '*') + '\n')
            for index, chore in enumerate(result, start=0):
                if index == 0:  # Skip if index EQUAL 0
                    continue
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
