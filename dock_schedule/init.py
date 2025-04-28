from json import dump
from pathlib import Path
from shutil import copytree, ignore_patterns
from string import ascii_letters
from random import choices, choice
from logging import Logger
from ipaddress import ip_address
from socket import gethostname

from dock_schedule.cert_auth import CertStore
from dock_schedule.utils import Utils


class Init(Utils):
    def __init__(self, force: bool = False, non_interactive: bool = False, logger: Logger = None):
        super().__init__(logger)
        self.__force = force
        self.__non_interactive = non_interactive
        self.__subject = {'country': 'Random', 'state': 'Random', 'city': 'Random', 'company': 'Random',
                          'department': 'Random',  'email': 'Random'}

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
        for path in ['ansible/playbooks', 'ansible/.env', 'broker/data', 'grafana/data', 'jobs', 'mongodb/data',
                     'prometheus/data', 'registry/data', 'certs']:
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

    def __fill_subject_randoms(self):
        for key, value in self.__subject.items():
            if value == 'Random':
                if key == 'country':
                    self.__subject[key] = ''.join(choices(ascii_letters, k=2))
                elif key == 'email':
                    self.__subject[key] = ''.join(choices(ascii_letters, k=choice(range(10, 20)))) + '@random.com'
                else:
                    self.__subject[key] = ''.join(choices(ascii_letters, k=choice(range(10, 20))))

    def __create_cert_subject(self) -> bool:
        """Create the CA subject file if it does not exist or force is set

        Returns:
            bool: True if successful, False otherwise
        """
        file = Path('/opt/dock-schedule/certs/.ca-subject')
        if file.exists() and not self.__force:
            return True
        if not self.__non_interactive:
            self.__subject['country'] = input('CA Country Name (2 letter code) [Random]: ') or 'Random'
            self.__subject['state'] = input('CA State or Province Name [Random]: ') or 'Random'
            self.__subject['city'] = input('CA Locality Name (city) [Random]: ') or 'Random'
            self.__subject['company'] = input('CA Organization Name (eg, company) [Random]: ') or 'Random'
            self.__subject['department'] = input('CA Organizational Unit Name (eg, section) [Random]: ') or 'Random'
            self.__subject['email'] = input('CA email [Random]: ') or 'Random'
        self.__fill_subject_randoms()
        try:
            with open(file, 'w') as file:
                dump(self.__subject, file, indent=2)
                file.write('\n')
            return True
        except Exception:
            self.log.exception('Failed to create CA subject file')
        return False

    def __generate_container_ssl_certs(self):
        for service in ['broker', 'grafana', 'mongodb', 'mongodb_scraper', 'prometheus', 'scheduler', 'node_scraper',
                        'worker', 'proxy', 'proxy_scraper', 'container_scraper', 'registry']:
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

    def __create_hosts_entry(self):
        try:
            with open('/etc/hosts', 'a+') as file:
                file.write('\n127.0.0.1  proxy\n127.0.0.1  mongodb\n127.0.0.1  registry\n')
            return True
        except Exception:
            self.log.exception('Failed to create /etc/hosts entry for proxy service')
            return False

    def __create_ansible_keys(self):
        self.log.info('Creating ansible keys')
        if Path(self.ansible_private_key).exists():
            if not self.__force:
                self.log.info('Ansible keys already exist')
                return True
            if not self._run_cmd(f'rm -f {self.ansible_private_key}')[1]:
                return False
        return self._run_cmd(f'ssh-keygen -t rsa -b 4096 -C "ansible" -f {self.ansible_private_key} -N ""')[1] and \
            self._run_cmd(f'chmod 400 {self.ansible_private_key}')[1]

    def __create_mongo_credentials(self):
        creds = {'user': 'dsu-' + ''.join(choices(ascii_letters, k=8)),
                 'passwd': ''.join(choices(ascii_letters, k=32)),
                 'db': 'dsdb-' + ''.join(choices(ascii_letters, k=8))}
        try:
            with open('/opt/dock-schedule/.mongo', 'w') as file:
                dump(creds, file)
        except Exception:
            self.log.exception('Failed to create mongo credentials file')
            return False
        return self._run_cmd('chown root:root /opt/dock-schedule/.mongo')[1] and \
            self._run_cmd('chmod 440 /opt/dock-schedule/.mongo')[1]

    def __create_docker_swarm(self):
        self.log.info('Creating docker swarm')
        return self.run_ansible_playbook('create_swarm.yml', self.localhost_inventory)

    def _run(self):
        for method in [self.__create_service_users, self.__create_swarm_dir_tree, self.__init_cert_store,
                       self.__create_hosts_entry, self.__create_ansible_keys,
                       self.__create_mongo_credentials, self.__create_docker_swarm]:
            if not method():
                return False
        self.log.info('Successfully initialized dock-schedule')
        return True
