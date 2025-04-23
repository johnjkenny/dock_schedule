import requests
from pathlib import Path
from shutil import copytree, ignore_patterns
from string import ascii_letters
from subprocess import run
from tempfile import TemporaryDirectory, NamedTemporaryFile
from json import dump, loads
from random import choices, choice
from logging import Logger
from ipaddress import ip_address
from socket import gethostname
from typing import Dict, Set

import ansible_runner
from yaml import safe_load, safe_dump

from dock_schedule.logger import get_logger
from dock_schedule.cert_auth import CertStore
from dock_schedule.color import Color


class Utils():
    def __init__(self, logger: Logger = None):
        self.log = logger or get_logger('dock-schedule')

    @property
    def ansible_env_vars(self):
        return {
            'ANSIBLE_CONFIG': '/opt/dock-schedule/ansible/ansible.cfg',
            'ANSIBLE_PYTHON_INTERPRETER': '/usr/bin/python3',
            'ANSIBLE_PRIVATE_KEY_FILE': '/opt/dock-schedule/.env/.ansible_rsa',
        }

    @property
    def localhost_inventory(self):
        return {'all': {'hosts': {'localhost': {'ansible_connection': 'local'}}}}

    def _display_error(self, message: str):
        Color().print_message(message, 'red')
        return False

    def _display_success(self, message: str):
        Color().print_message(message, 'green')
        return True

    def _display_info(self, message: str):
        Color().print_message(message, 'cyan')
        return True

    def _display_warning(self, message: str):
        Color().print_message(message, 'yellow')
        return True

    def _remote_inventory(self, host: str, ip: str) -> Dict:
        return {'all': {'hosts': {host: {'ansible_host': ip}}}}

    def _set_cert_permissions(self) -> bool:
        return self._run_cmd('chmod -R 440 /opt/dock-schedule/certs')[1] and \
            self._run_cmd('chown -R root:root /opt/dock-schedule/certs')[1]

    def _run_cmd(self, cmd: str, ignore_error: bool = False, log_output: bool = False) -> tuple:
        """Run a command and return the output

        Args:
            cmd (str): Command to run
            ignore_error (bool, optional): ignore errors. Defaults to False
            log_output (bool, optional): Log command output. Defaults to False.

        Returns:
            tuple: (stdout, True. '') on success or (stdout, False, error) on failure
        """
        state = True
        error = ''
        output = run(cmd, shell=True, capture_output=True, text=True)
        if output.returncode != 0:
            state = False
            error = output.stderr
            if not ignore_error:
                self.log.error(f'Command: {cmd}\nExit Code: {output.returncode}\nError: {error}')
                return '', state, error
        stdout = output.stdout
        if log_output:
            self.log.info(f'Command: {cmd}\nOutput: {stdout}')
        return stdout, state, error

    def create_docker_swarm(self):
        self.log.info('Creating docker swarm')
        return self.run_ansible_playbook('create_swarm.yml', self.localhost_inventory)

    def set_workers(self, worker_qty: int = 1):
        return self._run_cmd(f'docker service scale dock-schedule_worker={worker_qty}')[1]

    def run_ansible_playbook(self, playbook: str, inventory: Dict):
        with TemporaryDirectory(dir='/tmp', delete=True) as temp_dir:
            result = ansible_runner.run(
                private_data_dir=temp_dir,
                playbook=f'/opt/dock-schedule/ansible/playbooks/{playbook}',
                inventory=inventory,
                envvars=self.ansible_env_vars)
            if result.rc != 0:
                self.log.error(f'Failed to run ansible playbook: {result.status}')
                return False
            return True


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
                    yield loads(line.strip())
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
        if service in self.__service_names:
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
            for service in self.__rebalance_services:
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
                self.log.info(f'Service {service} is not running')
        return True

    def stop_services(self, service: str = 'all'):
        deployed = self.deployed_services()
        if ',' in service:
            return self.__stop_multiple_services(set(service.split(',')), deployed)
        if service == 'all':
            return self.__stop_multiple_services(deployed, deployed)
        if service in deployed:
            return self.__stop_service(service)
        self.log.info(f'Service {service} is not running')
        return True

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
                    yield loads(line.strip())
                except Exception:
                    self.log.exception('Failed to parse JSON')

    def display_services(self):
        containers = 0
        color = Color()
        color.print_message('Services:', 'cyan')
        for service in self.get_services():
            service: Dict
            replicas = service.get('Replicas')
            replica_data = replicas.split('/')
            version = service.get('Image').split(':')[1]
            name = service.get('Name', '').replace('dock-schedule_', '')
            containers += int(replica_data[0])
            if replica_data[0] == replica_data[1]:
                color.print_message(f'  {name}:{version} {replica_data[0]}', 'green')
            else:
                color.print_message(f'  {name}:{version} {replicas}', 'red')
        color.print_message(f'Total containers: {containers}', 'magenta')
        return True


class Init(Utils):
    def __init__(self, force: bool = False, logger: Logger = None):
        super().__init__(logger)
        self.__force = force

    @property
    def certs(self):
        return CertStore(self.log)

    def __create_service_users(self):
        self.log.info('Creating service users')
        for user in [('grafana', 3000), ('rabbitmq', 3001), ('mongodb', 3002)]:
            rsp = self._run_cmd(f'getent passwd {user[0]}', ignore_error=True)
            if rsp[1]:
                split_data = rsp[0].split(':')
                if user[1] == int(split_data[2]) and user[1] == int(split_data[3]):
                    continue
                if self.__force:
                    self.log.info(f'User {user} exists but with different UID/GID. Recreating user.')
                    if not self._run_cmd(f'userdel {user}')[1] or self._run_cmd(f'groupdel {user}')[1]:
                        self.log.error(f'Failed to delete user {user}')
                        return False
                else:
                    self.log.error(f'User {user} exists with different UID/GID. Use --force to recreate.')
                    return False
            if not self._run_cmd(f'groupadd -g {user[1]} {user[0]}')[1]:
                self.log.error(f'Failed to create group {user[0]}')
                return False
            if not self._run_cmd(f'useradd -u {user[1]} -g {user[0]} -s /sbin/nologin -M {user[0]}')[1]:
                self.log.error(f'Failed to create user {user[0]}')
                return False
        return True

    def __create_swarm_dir_tree(self):
        self.log.info('Creating swarm directory tree')
        for path in ['ansible/playbooks', 'broker/data', 'grafana/data', 'jobs', 'mongodb/data', 'prometheus/data',
                     'certs']:
            try:
                Path('/opt/dock-schedule/' + path).mkdir(parents=True, exist_ok=True)
            except Exception:
                self.log.exception(f'Failed to create directory {path}')
                return False
        return self.__create_ansible_files()

    def __create_ansible_files(self):
        try:
            src = Path(__file__).parent / 'ansible/'
            copytree(src, '/opt/dock-schedule/ansible/', dirs_exist_ok=True, ignore=ignore_patterns('__init__.py'))
        except Exception:
            self.log.exception('Failed to copy ansible files')
            return False
        return self.__create_job_files()

    def __create_job_files(self):
        try:
            src = Path(__file__).parent / 'jobs/'
            copytree(src, '/opt/dock-schedule/jobs/', dirs_exist_ok=True, ignore=ignore_patterns('__init__.py'))
        except Exception:
            self.log.exception('Failed to copy ansible files')
            return False
        return self.__set_share_dir_permissions()

    def __set_share_dir_permissions(self):
        for permission in [('rabbitmq', 'broker'), ('grafana', 'grafana'), ('mongodb', 'mongodb')]:
            if not self._run_cmd(f'chown -R {permission[0]}:root /opt/dock-schedule/{permission[1]}/data')[1]:
                self.log.error(f'Failed to set permissions for {permission}')
                return False
        return self.__copy_swarm_services()

    def __copy_swarm_services(self):
        self.log.info('Creating dock-schedule directory tree')
        try:
            src = Path(__file__).parent / 'services/'
            copytree(src, '/opt/dock-schedule/', dirs_exist_ok=True, ignore=ignore_patterns('__init__.py'))
            return True
        except Exception:
            self.log.exception('Failed to copy dock-schedule files')
            return False

    def __init_cert_store(self):
        self.log.info('Initializing certificate store')
        if self.__create_cert_subject():
            if self.certs._initialize_cert_authority(self.__force) and self.__generate_container_ssl_certs():
                return self.__generate_swarm_manager_ssl_certs()
        return False

    def __fill_subject_randoms(self, subject: dict) -> dict:
        for key, value in subject.items():
            if value == 'Random':
                if key == 'country':
                    subject[key] = ''.join(choices(ascii_letters, k=2))
                elif key == 'email':
                    subject[key] = ''.join(choices(ascii_letters, k=choice(range(10, 20)))) + '@random.com'
                else:
                    subject[key] = ''.join(choices(ascii_letters, k=choice(range(10, 20))))
        return subject

    def __create_cert_subject(self) -> bool:
        """Create the CA subject file if it does not exist or force is set

        Returns:
            bool: True if successful, False otherwise
        """
        file = Path('/opt/dock-schedule/certs/.ca-subject')
        if file.exists() and not self.__force:
            return True
        subject = {}
        subject['country'] = input('CA Country Name (2 letter code) [Random]: ') or 'Random'
        subject['state'] = input('CA State or Province Name [Random]: ') or 'Random'
        subject['city'] = input('CA Locality Name (city) [Random]: ') or 'Random'
        subject['company'] = input('CA Organization Name (eg, company) [Random]: ') or 'Random'
        subject['department'] = input('CA Organizational Unit Name (eg, section) [Random]: ') or 'Random'
        subject['email'] = input('CA email [Random]: ') or 'Random'
        subject = self.__fill_subject_randoms(subject)
        try:
            with open(file, 'w') as file:
                dump(subject, file, indent=2)
                file.write('\n')
            return True
        except Exception:
            self.log.exception('Failed to create CA subject file')
        return False

    def __generate_container_ssl_certs(self):
        for service in ['broker', 'grafana', 'mongodb', 'mongodb_scraper', 'prometheus', 'scheduler', 'node_scraper',
                        'worker', 'proxy', 'proxy_scraper', 'container_scraper']:
            if not self.certs.create(service, [service, 'localhost', '127.0.0.1']):
                self.log.error(f'Failed to create certificate for {service}')
                return False
        return True

    def __get_primary_ip(self):
        rsp = self._run_cmd('hostname -I')
        if rsp[1]:
            ip = rsp[0].split()[0]
            try:
                ip_address(ip)
                return ip
            except Exception:
                self.log.error(f'Failed to get primary IP address: {ip}')
        else:
            self.log.error('Failed to get primary IP address')
        return None

    def __generate_swarm_manager_ssl_certs(self):
        self.log.info('Generating SSL certificates for swarm manager')
        ip = self.__get_primary_ip()
        if ip:
            hostname = gethostname().split('.')[0]
            if self.certs.create(hostname, [hostname, ip, 'localhost', '127.0.0.1']):
                return self._set_cert_permissions()
        return False

    def __create_proxy_hosts_entry(self):
        try:
            with open('/etc/hosts', 'a+') as file:
                file.write('\n127.0.0.1  proxy')
        except Exception:
            self.log.exception('Failed to create /etc/hosts entry for proxy service')
            return False

    def _run(self):
        for method in [self.__create_service_users, self.__create_swarm_dir_tree, self.__init_cert_store,
                       self.__create_proxy_hosts_entry, self.create_docker_swarm]:
            if not method():
                return False
        self.log.info('Successfully initialized dock-schedule')
        return True
