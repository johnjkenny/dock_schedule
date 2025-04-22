from pathlib import Path
from shutil import copytree, ignore_patterns
from string import ascii_letters
from subprocess import run
from tempfile import TemporaryDirectory
from json import dump
from random import choices, choice
from logging import Logger
from ipaddress import ip_address
from socket import gethostname

import ansible_runner

from dock_schedule.logger import get_logger
from dock_schedule.cert_auth import CertStore


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

    def __remote_inventory(self, host: str, ip: str) -> dict:
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

    def add_docker_swarm_node(self, host: str, ip: str):
        self.log.info(f'Adding {host} to swarm cluster')
        return self.run_ansible_playbook('add_node_to_swarm.yml', self.__remote_inventory(host, ip))

    def remove_docker_swarm_node(self, host: str, ip: str):
        self.log.info(f'Removing {host} from swarm cluster')
        return self.run_ansible_playbook('remove_node_from_swarm.yml', self.__remote_inventory(host, ip))

    def run_ansible_playbook(self, playbook: str, inventory: dict):
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
            return self.certs._initialize_cert_authority(self.__force) and self.__generate_container_ssl_certs()
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

    def _run(self):
        for method in [self.__create_service_users, self.__create_swarm_dir_tree, self.__init_cert_store,
                       self.create_docker_swarm]:
            if not method():
                return False
        self.log.info('Successfully initialized dock-schedule')
        return True
