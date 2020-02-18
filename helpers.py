import os


def adapt_host_data(host):
    host.username = os.environ.get('LAB_USERNAME')
    host.password = os.environ.get('LAB_PASSWORD')
