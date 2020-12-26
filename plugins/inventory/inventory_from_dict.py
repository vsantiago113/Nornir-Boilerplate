from typing import Any, Dict, Type

from nornir.core.inventory import (
    Inventory,
    Group,
    Groups,
    Host,
    Hosts,
    Defaults,
    ConnectionOptions,
    HostOrGroup,
    ParentGroups,
)


def _get_connection_options(data: Dict[str, Any]) -> Dict[str, ConnectionOptions]:
    cp = {}
    for cn, c in data.items():
        cp[cn] = ConnectionOptions(
            hostname=c.get('hostname'),
            port=c.get('port'),
            username=c.get('username'),
            password=c.get('password'),
            platform=c.get('platform'),
            extras=c.get('extras'),
        )
    return cp


def _get_defaults(data: Dict[str, Any]) -> Defaults:
    return Defaults(
        hostname=data.get('hostname'),
        port=data.get('port'),
        username=data.get('username'),
        password=data.get('password'),
        platform=data.get('platform'),
        data=data.get('data'),
        connection_options=_get_connection_options(data.get('connection_options', {})),
    )


def _get_inventory_element(
    typ: Type[HostOrGroup], data: Dict[str, Any], name: str, defaults: Defaults
) -> HostOrGroup:
    return typ(
        name=name,
        hostname=data.get('hostname'),
        port=data.get('port'),
        username=data.get('username'),
        password=data.get('password'),
        platform=data.get('platform'),
        data=data.get('data'),
        groups=data.get(
            'groups'
        ),  # this is a hack, we will convert it later to the correct type
        defaults=defaults,
        connection_options=_get_connection_options(data.get('connection_options', {})),
    )


class InventoryFromDict:
    def __init__(
        self,
        host_dict: Dict = None,
        group_dict: Dict = None,
        defaults_dict: Dict = None,
    ) -> None:
        """
        DictInventory is an inventory plugin that loads data from dictionaries.
        The dictionaries follow the same structure as the native objects

        Args:

          host_dict: a dictionary with hosts definition
          group_dict: a dictionary with groups definition. If
                it doesn't exist it will be skipped
          defaults_dict: a dictionary with defaults definition.
                If it doesn't exist it will be skipped
        """

        self.host_dict = host_dict
        self.group_dict = group_dict
        self.defaults_dict = defaults_dict

    def load(self) -> Inventory:
        if self.defaults_dict:
            defaults = _get_defaults(self.defaults_dict)
        else:
            defaults = Defaults()

        hosts = Hosts()
        hosts_dict = self.host_dict

        for n, h in hosts_dict.items():
            hosts[n] = _get_inventory_element(Host, h, n, defaults)

        groups = Groups()
        if self.group_dict:
            groups_dict = self.group_dict

            for n, g in groups_dict.items():
                groups[n] = _get_inventory_element(Group, g, n, defaults)

            for h in hosts.values():
                h.groups = ParentGroups([groups[g] for g in h.groups])

            for g in groups.values():
                g.groups = ParentGroups([groups[g] for g in g.groups])

        return Inventory(hosts=hosts, groups=groups, defaults=defaults)
