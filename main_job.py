import logging
import os
from nornir import InitNornir
from nornir.plugins.tasks.networking import netmiko_send_config, netmiko_save_config, netmiko_send_command
from nornir.plugins.tasks import text
from nornir.plugins.functions.text import print_title

os.mkdir('logs') if not os.path.isdir('logs') else None

nr = InitNornir(config_file='config.yaml', dry_run=False,
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
    # Save the compiled configuration into a host variable
    task.host['config'] = r.result

    # Deploy that configuration to the device using Netmiko
    task.run(task=netmiko_send_config,
             name='Loading Configuration on the Device',
             config_commands=task.host['config'].splitlines(),
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

with open('logs/extended_nornir.log', 'w') as f:
    for device, result, in multi_result.items():
        if result.failed:
            f.write(f' Name: {device}, IP Address: {result[0].host.hostname} - FAILED! '.center(80, '*') + '\n')
        else:
            f.write(f' Name: {device}, IP Address: {result[0].host.hostname} - SUCCESS! '.center(80, '*') + '\n')
            for stdout in result[2:]:
                if stdout.result:
                    f.write(str(stdout) + '\n')
        f.write(f'{"~" * 80}\n')
