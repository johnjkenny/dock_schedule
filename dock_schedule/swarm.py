import requests
import json
import subprocess

from tempfile import NamedTemporaryFile
from logging import Logger
from socket import gethostname
from typing import Dict, Set

from yaml import safe_load, safe_dump
from prettytable import PrettyTable

from dock_schedule.color import Color
from dock_schedule.utils import Utils


class Swarm(Utils):
    def __init__(self, logger: Logger = None):
        super().__init__(logger)
        self.hostname = gethostname().split('.')[0]

    @property
    def cert_dir(self):
        return '/opt/dock-schedule/certs'

    @property
    def cert_params(self):
        return {
            'cert': (f'{self.cert_dir}/{self.hostname}.crt', f'{self.cert_dir}/{self.hostname}.key'),
            'verify': f'{self.cert_dir}/dock-schedule-ca.crt',
        }

    @property
    def query_url(self):
        return 'https://proxy:8080/api/v1/query'

    def node_snap_data(self, name: str):
        return {
            'load_avg_1m': f'node_load1{{job="Node-Scrape", instance="{name}"}}',
            'load_avg_5m': f'node_load5{{job="Node-Scrape", instance="{name}"}}',
            'load_avg_15m': f'node_load15{{job="Node-Scrape", instance="{name}"}}',
            "cpu_cores": f'count(node_cpu_seconds_total{{mode="system", job="Node-Scrape", instance="{name}"}})',
            'mem_available': f'node_memory_MemAvailable_bytes{{job="Node-Scrape", instance="{name}"}}',
            'mem_total': f'node_memory_MemTotal_bytes{{job="Node-Scrape", instance="{name}"}}',
            'disk_avail': f'node_filesystem_avail_bytes{{job="Node-Scrape", instance="{name}", mountpoint="/"}}',
            'disk_total': f'node_filesystem_size_bytes{{job="Node-Scrape", instance="{name}", mountpoint="/"}}',
        }

    def container_snap_data(self, node: str, container: str):
        return {
            'cpu': f'rate(container_cpu_usage_seconds_total{{job="Container-Scrape", instance="{node}", \
                name="{container}"}}[1m])',
            'mem': f'container_memory_usage_bytes{{job="Container-Scrape", instance="{node}", name="{container}"}}'
        }

    def get_node_containers(self, name: str = 'dock-schedule-2'):
        query = f'container_last_seen{{instance="{name}", job="Container-Scrape"}}'
        try:
            rsp = requests.get(self.query_url, params={'query': query}, **self.cert_params)
            if rsp.status_code == 200:
                for result in rsp.json().get('data', {}).get('result', []):
                    container = result.get('metric', {}).get('name')
                    if container:
                        yield container
            else:
                self.log.error(f'Failed to container info for node {name}: [{rsp.status_code}] {rsp.text}')
        except Exception:
            self.log.exception('Failed to get node info from Prometheus query')

    def __get_node_verbose_info(self, node_name: str):
        data = {}
        for key, query in self.node_snap_data(node_name).items():
            try:
                rsp = requests.get(self.query_url, params={'query': query}, **self.cert_params)
                if rsp.status_code == 200:
                    data[key] = float(rsp.json().get('data', {}).get('result', [])[0].get('value', [])[1])
                else:
                    self.log.error(f'Failed to get node info from Prometheus query: [{rsp.status_code}] {rsp.text}')
                    data[key] = 0
            except Exception:
                continue
        return data

    def __get_container_verbose_info(self, node_name: str, container_name: str):
        data = {}
        for key, query in self.container_snap_data(node_name, container_name).items():
            try:
                rsp = requests.get(self.query_url, params={'query': query}, **self.cert_params)
                if rsp.status_code == 200:
                    data[key] = float(rsp.json().get('data', {}).get('result', [])[0].get('value', [])[1])
                else:
                    self.log.error(f'Failed to get node info from Prometheus query: [{rsp.status_code}] {rsp.text}')
                    data[key] = 0
            except Exception:
                continue
        return data

    def get_swarm_nodes(self):
        rsp = self._run_cmd('docker node ls --format json')
        if rsp[1]:
            for line in rsp[0].splitlines():
                try:
                    yield json.loads(line.strip())
                except Exception:
                    self.log.exception('Failed to parse JSON')

    def get_node_ip(self, node_name: str):
        rsp = self._run_cmd(f'docker node inspect {node_name} --format "{{{{ .Status.Addr }}}}"')
        if rsp[1]:
            return rsp[0].strip()
        return None

    def __determine_display_color(self, percent: float) -> str:
        if percent < 70:
            return 'green'
        if percent < 90:
            return 'yellow'
        else:
            return 'red'

    def __display_node_cpu_verbose_info(self, info: Dict, color: Color):
        one_min = info.get('load_avg_1m') / info.get('cpu_cores') * 100
        one_min_color = self.__determine_display_color(one_min)
        five_min = info.get('load_avg_5m') / info.get('cpu_cores') * 100
        five_min_color = self.__determine_display_color(five_min)
        fifteen_min = info.get('load_avg_15m') / info.get('cpu_cores') * 100
        fifteen_min_color = self.__determine_display_color(fifteen_min)
        color.print_message(f"    CPU Load Avg (1m):    {one_min:.1f}%", one_min_color)
        color.print_message(f"    CPU Load Avg (5m):    {five_min:.1f}%", five_min_color)
        color.print_message(f"    CPU Load Avg (15m):   {fifteen_min:.1f}%", fifteen_min_color)

    def __display_node_memory_verbose_info(self, info: Dict, color: Color):
        info['mem_used'] = info["mem_total"] - info["mem_available"]
        mem_pct = info['mem_used'] / info["mem_total"] * 100 if info["mem_total"] else 0
        mem_color = self.__determine_display_color(mem_pct)
        color.print_message(f"    Memory Used:          {info['mem_used'] / (1024**3):.2f} GiB ({mem_pct:.1f}%)",
                            mem_color)

    def __display_node_disk_verbose_info(self, info: Dict, color: Color):
        disk_used = info["disk_total"] - info["disk_avail"]
        disk_pct = disk_used / info["disk_total"] * 100 if info["disk_total"] else 0
        disk_color = self.__determine_display_color(disk_pct)
        color.print_message(f"    Disk Used:            {disk_used / (1024**3):.2f} GiB ({disk_pct:.1f}%)", disk_color)

    def __display_container_cpu_info(self, info: Dict, color: Color, cpu_qty: float | int):
        cpu = info.get('cpu')
        if cpu:
            one_min = info.get('cpu') / cpu_qty * 100
            one_min_color = self.__determine_display_color(one_min)
            color.print_message(f"\t    CPU (1m):    {one_min:.1f}%", one_min_color)
        else:
            color.print_message("\t    CPU (1m):    0.0%", 'green')

    def __display_container_memory_info(self, info: Dict, color: Color, mem_used: float | int):
        mem_pct = info["mem"] / mem_used * 100 if mem_used else 0
        mem_color = self.__determine_display_color(mem_pct)
        color.print_message(f"\t    Memory Used: {info['mem'] / (1024**2):.2f} MiB ({mem_pct:.1f}%)", mem_color)

    def __display_node_verbose_info(self, node_name: str):
        info = self.__get_node_verbose_info(node_name)
        if info:
            color = Color()
            self.__display_node_cpu_verbose_info(info, color)
            self.__display_node_memory_verbose_info(info, color)
            self.__display_node_disk_verbose_info(info, color)
            color.print_message('    Containers:', 'bright-cyan')
            for container in self.get_node_containers(node_name):
                color.print_message(f'\t{container}', 'magenta')
                container_info = self.__get_container_verbose_info(node_name, container)
                self.__display_container_cpu_info(container_info, color, info.get('cpu_cores'))
                self.__display_container_memory_info(container_info, color, info.get('mem_used'))

    def display_swarm_nodes(self, verbose: bool = False):
        for node in self.get_swarm_nodes():
            node: Dict
            manager = '[Leader]' if node.get('ManagerStatus') == 'Leader' else ''
            ip = self.get_node_ip(node.get('Hostname'))
            if node.get('Status') == 'Ready':
                if node.get('Availability') == 'Active':
                    self._display_info(f'{node.get("Hostname")} ({ip}) {manager}')
                else:
                    self._display_warning(f'{node.get("Hostname")} ({ip}): {node.get("Availability")} {manager}')
                if verbose:
                    self.__display_node_verbose_info(node.get('Hostname'))
            else:
                self._display_error(f'{node.get("Hostname")} ({ip}): {node.get("Status")} {manager}')
        return True

    def add_docker_swarm_node(self, node_name: str, ip: str):
        self.log.info(f'Adding {node_name} to swarm cluster')
        return self.run_ansible_playbook('add_node_to_swarm.yml', self._remote_inventory(node_name, ip))

    def remove_docker_swarm_node(self, node_name: str, ip: str):
        self.log.info(f'Removing {node_name} from swarm cluster')
        return self.run_ansible_playbook('remove_node_from_swarm.yml', self._remote_inventory(node_name, ip))


class Services(Swarm):
    def __init__(self, logger: Logger = None):
        super().__init__(logger)

    @property
    def __service_names(self):
        return {'broker', 'container_scraper', 'grafana', 'mongodb', 'mongodb_scraper', 'node_scraper', 'prometheus',
                'proxy', 'proxy_scraper', 'scheduler', 'worker'}

    @property
    def __rebalance_services(self):
        return {'broker', 'grafana', 'mongodb', 'mongodb_scraper', 'proxy', 'proxy_scraper', 'worker'}

    def get_active_swarm_node_qty(self):
        cnt = 0
        for node in self.get_swarm_nodes():
            node: Dict
            if node.get('Status') == 'Ready' and node.get('Availability') == 'Active':
                cnt += 1
        return cnt

    def __reload_service(self, service: str):
        service = service.replace('dock-schedule_', '')
        if service in self.__service_names or service == 'registry':
            self.log.info(f'Reloading {service} service')
            return self._run_cmd(f'docker service update --force dock-schedule_{service}')[1]
        if len(service) == 12 and service.isalnum():
            self.log.info(f'Reloading {service} service')
            return self._run_cmd(f'docker service update --force {service}')[1]
        self.log.error(f'Invalid service name provided: {service}')
        return False

    def __reload_multiple_services(self, services: Set):
        for service in services:
            service: str
            if not self.__reload_service(service.strip()):
                return False
        return True

    def reload_services(self, service: str) -> bool:
        if service == 'all':
            return self.__reload_multiple_services(self.__service_names)
        if ',' in service:
            return self.__reload_multiple_services(set(service.split(',')))
        return self.__reload_service(service)

    def rebalance_services(self):
        if self.get_active_swarm_node_qty() > 1:
            self.log.info('Rebalancing swarm services')
            deployed = self.deployed_services()
            for service in self.__rebalance_services:
                if service in deployed:
                    if not self.__reload_service(service):
                        return False
        else:
            self.log.warning('Only one node in the cluster. Add more nodes to swarm cluster to rebalance services')
        return True

    def __load_compose_file(self) -> Dict:
        try:
            with open('/opt/dock-schedule/docker-compose.yml', 'r') as file:
                return safe_load(file)
        except Exception:
            self.log.exception('Failed to load docker-compose file')
            return {}

    def __stack_deploy_temp_compose(self, data: Dict, services: str) -> bool:
        self.log.info(f'Starting services: {services}')
        with NamedTemporaryFile(mode='w+t', delete=True) as tmp_file:
            try:
                safe_dump(data, tmp_file, indent=2)
                tmp_file.flush()
            except Exception:
                self.log.exception('Failed to start all services')
                return False
            return self._run_cmd(f'docker stack deploy -c {tmp_file.name} dock-schedule')[1]

    def __start_all_services(self):
        data = self.__load_compose_file()
        if data:
            return self.__stack_deploy_temp_compose(data, 'all')
        return False

    def __pull_services_data(self, services: Set) -> Dict:
        payload = {'services': {}, 'networks': {}, 'secrets': {}}
        data = self.__load_compose_file()
        if data:
            payload.update({'networks': data.get('networks', {}), 'secrets': data.get('secrets', {})})
            for service in services:
                service: str
                service = service.replace('dock-schedule_', '').strip()
                if service not in self.__service_names:
                    self.log.error(f'Invalid service name provided: {service}')
                    return {}
                try:
                    payload['services'].update({service: data['services'][service]})
                except Exception:
                    self.log.exception(f'Failed to get service data for {service}')
                    return {}
        return payload

    def __start_multiple_services(self, services: Set):
        data = self.__pull_services_data(services)
        if data:
            return self.__stack_deploy_temp_compose(data, ','.join(services))
        return False

    def __start_single_service(self, service: str):
        data = self.__pull_services_data(set([service]))
        if data:
            return self.__stack_deploy_temp_compose(data, service)
        return False

    def start_services(self, service: str = 'all'):
        if ',' in service:
            return self.__start_multiple_services(set(service.split(',')))
        if service == 'all':
            return self.__start_all_services()
        return self.__start_single_service(service)

    def __stop_service(self, service: str) -> bool:
        service = service.replace('dock-schedule_', '')
        if service in self.__service_names:
            self.log.info(f'Stopping {service} service')
            return self._run_cmd(f'docker service rm dock-schedule_{service}')[1]
        if len(service) == 12 and service.isalnum():
            self.log.info(f'Stopping {service} service')
            return self._run_cmd(f'docker service rm {service}')[1]
        self.log.error(f'Invalid service name provided: {service}')
        return False

    def __stop_multiple_services(self, services: Set, deployed: Set) -> bool:
        for service in services:
            service: str
            if service in deployed:
                if not self.__stop_service(service.strip()):
                    return False
            else:
                self.log.info(f'Cannot stop service "{service}"')
        return True

    def stop_services(self, service: str = 'all'):
        deployed = self.deployed_services()
        if ',' in service:
            return self.__stop_multiple_services(set(service.split(',')), deployed)
        if service == 'all':
            return self.__stop_multiple_services(deployed, deployed)
        if service in deployed:
            return self.__stop_service(service)
        self.log.error(f'Cannot stop service "{service}"')
        return False

    def deployed_services(self) -> Set:
        services = set()
        for service in self.get_services():
            service: Dict
            name = service.get('Name', '').replace('dock-schedule_', '')
            if name in self.__service_names:
                services.add(name)
        return services

    def get_services(self):
        rsp = self._run_cmd('docker service ls --format json')
        if rsp[1]:
            for line in rsp[0].splitlines():
                try:
                    service = json.loads(line.strip())
                    if 'dock-schedule_' in service.get('Name', ''):
                        yield service
                except Exception:
                    self.log.exception('Failed to parse JSON')

    def __determine_display_color(self, replicas: str, total: int):
        if '/' in replicas:
            split_info = replicas.split('/')
            qty = int(split_info[0])
            total += qty
            if split_info[0] == split_info[1]:
                return 'green', total
            if qty < int(split_info[1]):
                return 'red', total
        return 'yellow', total

    def display_services(self, verbose: bool = False):
        total = 0
        color = Color()
        table = PrettyTable()
        table.field_names = ['ID', 'Name', 'Image', 'Replicas']
        for service in self.get_services():
            service: Dict
            replicas = service.get('Replicas')
            display_color, total = self.__determine_display_color(replicas, total)
            if verbose:
                color.print_message(json.dumps(service, indent=2), display_color)
            else:
                table.add_row([
                    color.format_message(service.get('ID'), display_color),
                    color.format_message(service.get('Name', '').replace('dock-schedule_', ''), display_color),
                    color.format_message(service.get('Image'), display_color),
                    color.format_message(replicas, display_color)
                ])
        if not verbose:
            table.add_row(['-', '-', '-', color.format_message('Total: ' + str(total), 'magenta')])
            print(table)
        return True


class Containers(Utils):
    def __init__(self, logger: Logger = None):
        super().__init__(logger)

    def get_containers(self):
        rsp = self._run_cmd('docker ps --all --format json')
        if rsp[1]:
            for line in rsp[0].splitlines():
                try:
                    container = json.loads(line.strip())
                    if 'dock-schedule_' in container.get('Names', ''):
                        yield container
                except Exception:
                    self.log.exception('Failed to parse JSON')

    def __determine_display_color(self, status: str) -> str:
        if '(healthy)' in status:
            return 'green'
        if '(health: starting)' in status:
            return 'yellow'
        else:
            return 'red'

    def __determine_container_name(self, orig_name: str) -> str:
        name_info = orig_name.split('.')
        if len(name_info) > 1:
            if name_info[1].isdigit():
                return name_info[0].replace('dock-schedule_', '') + f'.{name_info[1]}'
            else:
                return name_info[0].replace('dock-schedule_', '')
        return orig_name.replace('dock-schedule_', '')

    def display_containers(self, verbose: bool = False):
        color = Color()
        table = PrettyTable()
        table.field_names = ['ID', 'Name', 'Image', 'Status']
        for container in self.get_containers():
            container: Dict
            display_color = self.__determine_display_color(container.get('Status', ''))
            if verbose:
                color.print_message(json.dumps(container, indent=2), display_color)
            else:
                name = self.__determine_container_name(container.get('Names', ''))
                table.add_row([
                    color.format_message(container.get('ID'), display_color),
                    color.format_message(name, display_color),
                    color.format_message(container.get('Image'), display_color),
                    color.format_message(container.get('Status'), display_color)
                ])
        if not verbose:
            print(table)
        return True

    def container_id_lookup(self, container_name: str):
        if len(container_name) == 12 and container_name.isalnum():
            return container_name
        for containers in self.get_containers():
            containers: Dict
            if container_name in containers.get('Names', ''):
                return containers.get('ID')
        self.log.error(f'Container {container_name} not found')
        return None

    def prune_containers(self):
        self.log.info('Pruning containers')
        return self._run_cmd('docker container prune --force')[1]

    def container_logs(self, container_name: str):
        container_id = self.container_id_lookup(container_name)
        if container_id:
            process = subprocess.Popen(['docker', 'logs', container_id],
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT,
                                       text=True,
                                       bufsize=1)
            for line in process.stdout:
                print(line, end='')
            return True
        return False

    def container_watcher(self, container_name: str):
        container_id = self.container_id_lookup(container_name)
        if container_id:
            process = subprocess.Popen(['docker', 'logs', '-f', container_id],
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT,
                                       text=True,
                                       bufsize=1)
            try:
                for line in process.stdout:
                    print(line, end='')
            except KeyboardInterrupt:
                process.terminate()
            except Exception:
                self.log.exception('Failed to get container logs container')
                return False
            return True
        return False

    def __get_all_container_stats(self):
        rsp = self._run_cmd('docker stats --format json --no-stream')
        if rsp[1]:
            for line in rsp[0].splitlines():
                self._display_info(json.dumps(json.loads(line), indent=2))
        return True

    def container_stats(self, container_name: str = 'all'):
        if container_name == 'all':
            return self.__get_all_container_stats()
        container_id = self.container_id_lookup(container_name)
        if container_id:
            rsp = self._run_cmd(f'docker stats --format json --no-stream {container_id}')
            if rsp[1]:
                return self._display_info(json.dumps(json.loads(rsp[0]), indent=2))
        return False
