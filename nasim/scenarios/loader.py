"""This module contains functionality for loading network scenarios from yaml
files.
"""
from nasim.env.host import Host
import nasim.scenarios.utils as u
import nasim.utils.futils as futils
from nasim.scenarios import Scenario


# dictionary of valid key names and value types for config file
VALID_CONFIG_KEYS = {u.SUBNETS: list,
                     u.TOPOLOGY: list,
                     u.SENSITIVE_HOSTS: dict,
                     u.SERVICES: list,
                     u.OS: list,
                     u.EXPLOITS: dict,
                     u.SERVICE_SCAN_COST: int,
                     u.OS_SCAN_COST: int,
                     u.HOST_CONFIGS: dict,
                     u.FIREWALL: dict}


# required keys for exploits
EXPLOIT_KEYS = {u.EXPLOIT_SERVICE: str,
                u.EXPLOIT_OS: str,
                u.EXPLOIT_PROB: float,
                u.EXPLOIT_COST: (int, float)}


class ScenarioLoader:

    def load(self, file_path):
        """Load the scenario from file

        Arguments
        ---------
        file_path : str
            path to scenario file

        Returns
        -------
        scenario_dict : dict
            dictionary with scenario definition

        Raises
        ------
        Exception
            If file unable to load or scenario file is invalid.
        """
        self.yaml_dict = futils.load_yaml(file_path)
        self._check_scenario_sections_valid()

        self._parse_subnets()
        self._parse_topology()
        self._parse_services()
        self._parse_sensitive_hosts()
        self._parse_exploits()
        self._parse_scan_cost()
        self._parse_host_configs()
        self._parse_firewall()
        self._parse_hosts()
        return self._construct_scenario()

    def _construct_scenario(self):
        scenario_dict = dict()
        scenario_dict[u.SUBNETS] = self.subnets
        scenario_dict[u.TOPOLOGY] = self.topology
        scenario_dict[u.SERVICES] = self.services
        scenario_dict[u.SENSITIVE_HOSTS] = self.sensitive_hosts
        scenario_dict[u.EXPLOITS] = self.exploits
        scenario_dict[u.SERVICE_SCAN_COST] = self.service_scan_cost
        scenario_dict[u.OS_SCAN_COST] = self.os_scan_cost
        scenario_dict[u.FIREWALL] = self.firewall
        scenario_dict[u.HOSTS] = self.hosts
        return Scenario(scenario_dict)

    def _check_scenario_sections_valid(self):
        """Checks if a scenario dictionary contains all required section is valid. """
        # 0. check correct number of keys
        if len(self.yaml_dict) != len(VALID_CONFIG_KEYS):
            raise KeyError(f"Incorrect number of config file keys: "
                           f"{len(self.yaml_dict)} != {len(VALID_CONFIG_KEYS)}")

        # 1. check keys are valid and values are correct type
        for k, v in self.yaml_dict.items():
            if k not in VALID_CONFIG_KEYS.keys():
                raise KeyError(f"{k} not a valid config file key")
            expected_type = VALID_CONFIG_KEYS[k]
            if type(v) is not expected_type:
                raise TypeError(f"{v} invalid type for config file key '{k}': "
                                f"{type(v)} != {expected_type}")

    def _parse_subnets(self):
        subnets = self.yaml_dict[u.SUBNETS]
        self._validate_subnets(subnets)
        # insert internet subnet
        subnets.insert(0, 1)
        self.subnets = subnets
        self.num_hosts = sum(subnets)-1

    def _validate_subnets(self, subnets):
        # check subnets is valid list of positive ints
        if len(subnets) < 1:
            raise ValueError("Subnets connot be empty list")
        for subnet_size in subnets:
            if type(subnet_size) is not int or subnet_size <= 0:
                raise ValueError(f"{subnet_size} invalid subnet size, must be positive int")

    def _parse_topology(self):
        topology = self.yaml_dict[u.TOPOLOGY]
        self._validate_topology(topology)
        self.topology = topology

    def _validate_topology(self, topology):
        # check topology is valid adjacency matrix
        if len(topology) != len(self.subnets):
            raise ValueError("Number of rows in topology adjacency matrix must equal number "
                             f" of subnets: {len(topology)} != {len(self.subnets)}")
        for row in topology:
            if type(row) is not list:
                raise ValueError("topology must be 2D adjacency matrix (i.e. list of lists)")
            if len(row) != len(self.subnets):
                raise ValueError("Number of colomns in topology adjacency matrix must equal number "
                                 f" of subnets: {len(topology)} != {len(self.subnets)}")
            for col in row:
                if type(col) is not int or (col != 1 and col != 0):
                    raise ValueError("Subnet_connections adjaceny matrix must "
                                     "contain only 1 (connected) or 0 (not "
                                     f"connected): {col} invalid")

    def _parse_services(self):
        services = self.yaml_dict[u.SERVICES]
        self._validate_services(services)
        self.services = services

    def _validate_services(self, services):
        # check services is postive int
        if len(services) < 1:
            raise ValueError(f"{len(services)}. Invalid number of services, must be >= 1")
        if len(services) < len(set(services)):
            raise ValueError(f"{len(services)}. Services must not contain duplicates")

    def _parse_sensitive_hosts(self):
        sensitive_hosts = self.yaml_dict[u.SENSITIVE_HOSTS]
        self._validate_sensitive_hosts(sensitive_hosts)

        self.sensitive_hosts = dict()
        for address, value in sensitive_hosts.items():
            self.sensitive_hosts[eval(address)] = value

    def _validate_sensitive_hosts(self, sensitive_hosts):
        # check sensitive_hosts is valid dict of (subnet, id) : value
        if len(sensitive_hosts) < 1:
            raise ValueError("Number of sensitive hosts must be >= 1: "
                             f"{len(sensitive_hosts)} not >= 1")
        if len(sensitive_hosts) > self.num_hosts:
            raise ValueError("Number of sensitive hosts must be <= total number of "
                             f"hosts: {len(sensitive_hosts)} not <= {self.num_hosts}")

        # sensitive hosts must be valid address
        for address, value in sensitive_hosts.items():
            subnet_id, host_id = eval(address)
            if not self._is_valid_subnet_ID(subnet_id):
                raise ValueError("Invalid sensitive host tuple: subnet_id must"
                                 f" be a valid subnet: {subnet_id} != non-negative int "
                                 f"less than {len(self.subnets) + 1}")
            if not self._is_valid_host_address(subnet_id, host_id):
                raise ValueError(f"Invalid sensitive host tuple: host_id "
                                 f"must be a valid int: {host_id} != non-negative int "
                                 f"less than {self.subnets[subnet_id]}")
            if not isinstance(value, (float, int)) or value <= 0:
                raise ValueError("Invalid sensitive host tuple: invalid value:"
                                 f" {value} != a positive int or float")

        # 5.c sensitive hosts must not contain duplicate addresses
        for i, m in enumerate(sensitive_hosts.keys()):
            h1_addr = eval(m)
            for j, n in enumerate(sensitive_hosts.keys()):
                h2_addr = eval(n)
                if i != j and h1_addr == h2_addr:
                    raise ValueError("Sensitive hosts list must not contain "
                                     f"duplicate host addresses: {m} == {n}")

    def _is_valid_subnet_ID(self, subnet_ID):
        if type(subnet_ID) is not int or subnet_ID < 1 or subnet_ID > len(self.subnets):
            return False
        return True

    def _is_valid_host_address(self, subnet_ID, host_ID):
        if not self._is_valid_subnet_ID(subnet_ID):
            return False
        if type(host_ID) is not int or host_ID < 0 or host_ID >= self.subnets[subnet_ID - 1]:
            return False
        return True

    def _parse_exploits(self):
        exploits = self.yaml_dict[u.EXPLOITS]
        self._validate_exploits(exploits)
        self.exploits = exploits

    def _validate_exploits(self, exploits):
        for e_name, e in exploits.items():
            self._validate_single_exploit(e_name, e)

    def _validate_single_exploit(self, e_name, e):
        if not isinstance(e, dict):
            raise ValueError(f"{e_name}. Exploit must be a dict.")
        for k, t in EXPLOIT_KEYS.items():
            if k not in e:
                raise ValueError(f"{e_name}. Exploit missing key: '{k}'")
            if not isinstance(e[k], t):
                raise ValueError(f"{e_name}. Exploit '{k}' incorrect type. Expected {t}")
        if e[u.EXPLOIT_SERVICE] not in self.services:
            raise ValueError(f"{e_name}. Exploit target service invalid: '{e[u.EXPLOIT_SERVICE]}'")
        if e[u.EXPLOIT_PROB] < 0 or 1 < e[u.EXPLOIT_PROB]:
            raise ValueError(f"{e_name}. Exploit probability, '{e[u.EXPLOIT_PROB]}' not "
                             "a valid probability")
        if e[u.EXPLOIT_COST] < 0:
            raise ValueError(f"{e_name}. Exploit cost must be > 0.")

    def _parse_scan_cost(self):
        service_scan_cost = self.yaml_dict[u.SERVICE_SCAN_COST]
        os_scan_cost = self.yaml_dict[u.OS_SCAN_COST]
        self._validate_scan_cost(service_scan_cost, os_scan_cost)
        self.service_scan_cost = service_scan_cost
        self.os_scan_cost = os_scan_cost

    def _validate_scan_cost(self, service_scan_cost, os_scan_cost):
        if service_scan_cost < 0:
            raise ValueError("Service Scan Cost must be >= 0.")
        if os_scan_cost < 0:
            raise ValueError("OS Scan Cost must be >= 0.")

    def _parse_host_configs(self):
        host_configs = self.yaml_dict[u.HOST_CONFIGS]
        self._validate_host_configs(host_configs)
        self.host_configs = host_configs

    def _validate_host_configs(self, host_configs):
        if len(host_configs) != self.num_hosts:
            raise ValueError("Number of host configurations must match the number of hosts in "
                             f"network: {len(host_configs)} != {self.num_hosts}")
        if not self._has_all_host_addresses(host_configs.keys()):
            raise ValueError("Host configurations must have no duplicates and have an address for "
                             "each host on network.")
        for cfg in host_configs.values():
            if not self._is_valid_host_config(cfg):
                raise ValueError("Host configurations must be at list, contain at least one "
                                 f"exploitable service and contain no duplicates: {cfg} is invalid")

    def _has_all_host_addresses(self, addresses):
        """Check that list of (subnet_ID, host_ID) tuples contains all addresses on network based
        on subnets list
        """
        for s_id, s_size in enumerate(self.subnets[1:]):
            for m in range(s_size):
                # +1 to s_id since first subnet is 1
                if str((s_id + 1, m)) not in addresses:
                    return False
        return True

    def _is_valid_host_config(self, cfg):
        """Check if a host config is valid or not given the list of exploits available
        N.B. each host config must contain at least one service
        """
        if type(cfg) != list or len(cfg) == 0:
            return False
        for service in cfg:
            if service not in self.services:
                return False
        for i, x in enumerate(cfg):
            for j, y in enumerate(cfg):
                if i != j and x == y:
                    return False
        return True

    def _parse_firewall(self):
        firewall = self.yaml_dict[u.FIREWALL]
        self._validate_firewall(firewall)
        # convert (subnet_id, subnet_id) string to tuple
        self.firewall = {}
        for connect, v in firewall.items():
            self.firewall[eval(connect)] = v

    def _validate_firewall(self, firewall):
        if not self._contains_all_required_firewalls(firewall):
            raise ValueError("Firewall dictionary must contain two entries for each subnet "
                             "connection in network (including from outside) as defined by "
                             "network topology matrix")
        for f in firewall.values():
            if not self._is_valid_firewall_setting(f):
                raise ValueError("Firewall setting must be a list, contain only valid services "
                                 " and contain no duplicates: {f} is not valid")

    def _contains_all_required_firewalls(self, firewall):
        for src, row in enumerate(self.topology):
            for dest, col in enumerate(row):
                if src == dest:
                    continue
                if col == 1 and (str((src, dest)) not in firewall or str((dest, src)) not in firewall):
                    return False
        return True

    def _is_valid_firewall_setting(self, f):
        if type(f) != list:
            return False
        for service in f:
            if service not in self.services:
                return False
        for i, x in enumerate(f):
            for j, y in enumerate(f):
                if i != j and x == y:
                    return False
        return True

    def _parse_hosts(self):
        """Returns ordered dictionary of hosts in network, with address as keys and host
        objects as values
        """
        hosts = dict()
        for address, services in self.host_configs.items():
            formatted_address = eval(address)
            cfg = self._construct_host_config(services)
            value = self._get_host_value(formatted_address)
            hosts[formatted_address] = Host(formatted_address, cfg, value)
        self.hosts = hosts

    def _construct_host_config(self, host_services):
        cfg = {}
        for service in self.services:
            cfg[service] = service in host_services
        return cfg

    def _get_host_value(self, address):
        return float(self.sensitive_hosts.get(address, 0.0))
