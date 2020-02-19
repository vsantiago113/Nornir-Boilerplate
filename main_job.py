import logging
import os
from nornir import InitNornir
from nornir.plugins.tasks.networking import netmiko_send_config, netmiko_save_config
from nornir.plugins.tasks import text
from nornir.plugins.functions.text import print_result, print_title
from nornir.core.filter import F

os.mkdir('logs') if not os.path.isdir('logs') else None

nr = InitNornir(config_file='config.yaml', dry_run=False,
                logging={'enabled': True, 'level': 'debug', 'to_console': True, 'file': 'logs/nornir.log',
                         'format': '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s() - %(message)s'})


def basic_configuration(task):
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


print_title('Playbook to setup basic configs')
switches = nr.filter(F(groups__contains='switch'))
multi_result = switches.run(task=basic_configuration)
print_result(multi_result)

with open('logs/extended_nornir.log', 'w') as f:
    for host, result, in multi_result.items():
        if result.failed:
            f.write(f' Name: {host}, IP Address: {result[0].host.hostname} - FAILED! '.center(80, '*') + '\n')
        else:
            f.write(f' Name: {host}, IP Address: {result[0].host.hostname} - SUCCESS! '.center(80, '*') + '\n')
            for output in result[2:]:
                if output.result:
                    f.write(str(output) + '\n')
        f.write(f'{"~" * 80}\n')
