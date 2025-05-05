import json
from subprocess import run
from tempfile import TemporaryDirectory
from logging import Logger
from typing import Dict
from urllib.parse import quote_plus
from time import sleep

import ansible_runner
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure, ServerSelectionTimeoutError

from dock_schedule.logger import get_logger
from dock_schedule.color import Color


class Mongo():
    def __init__(self, logger: Logger):
        self.log = logger
        self.__client: MongoClient | None = None
        self.__creds = {'user': '', 'passwd': '', 'db': ''}

    @property
    def __host(self):
        return "mongodb://%s:%s@mongodb:27017/" % (quote_plus(self.__creds.get('user')),
                                                   quote_plus(self.__creds.get('passwd')))

    @property
    def client(self):
        if self.__client is None:
            if self.__load_creds():
                for attempt in range(36):
                    try:
                        self.__client = MongoClient(
                            host=self.__host,
                            tls=True,
                            tlsCAFile='/etc/docker/ca.crt',
                            tlsCertificateKeyFile='/etc/docker/host.pem',
                            serverSelectionTimeoutMS=2000
                        )
                        self.__client.admin.command('ping')
                        self.log.info('MongoDB client created successfully')
                        return self.__client
                    except ServerSelectionTimeoutError:
                        self.log.error(f'Failed to connect to MongoDB {attempt + 1}/36')
                    except ConnectionFailure:
                        self.log.exception('Failed to connect to MongoDB')
                    except Exception:
                        self.log.exception('Failed to create MongoDB client')
                        return None
                    sleep(2)
        return self.__client

    def __load_creds(self):
        try:
            with open('/opt/dock-schedule/.mongo', 'r') as file:
                self.__creds = json.load(file)
            return True
        except Exception:
            self.log.exception('Failed to load mongodb credentials')
            return False

    def __get_db(self):
        if self.client:
            try:
                return self.client[self.__creds.get('db')]
            except Exception:
                self.log.exception('Failed to get database object')
        return None

    def __get_collection(self, collection_name: str = 'jobs'):
        db = self.__get_db()
        if db is not None:
            try:
                return db[collection_name]
            except Exception:
                self.log.exception(f'Failed to get collection: {collection_name}')
        return None

    def insert_one(self, collection_name: str, document: dict):
        collection = self.__get_collection(collection_name)
        if collection is not None:
            try:
                return collection.insert_one(document)
            except OperationFailure as error:
                self.log.error(f'Failed to insert document: {error.details}')
            except Exception:
                self.log.exception(f'Failed to insert document: {document}')
        return None

    def insert_many(self, collection_name: str, documents: list[dict]):
        collection = self.__get_collection(collection_name)
        if collection is not None:
            try:
                return collection.insert_many(documents)
            except OperationFailure as error:
                self.log.error(f'Failed to insert documents: {error.details}')
            except Exception:
                self.log.exception(f'Failed to insert documents: {documents}')
        return None

    def get_one(self, collection_name: str, *filters: dict):
        collection = self.__get_collection(collection_name)
        if collection is not None:
            try:
                return collection.find_one(*filters)
            except OperationFailure as error:
                self.log.error(f'Failed to find data: {error.details}')
            except Exception:
                self.log.exception('Failed to find data')
        return None

    def get_all(self, collection_name: str, *filters: dict):
        collection = self.__get_collection(collection_name)
        if collection is not None:
            try:
                return list(collection.find(*filters))
            except OperationFailure as error:
                self.log.error(f'Failed to find data: {error.details}')
            except Exception:
                self.log.exception('Failed to query collection')
        return []

    def get_all_with_cursor(self, collection_name: str, *filters: dict):
        collection = self.__get_collection(collection_name)
        if collection is not None:
            try:
                return collection.find(*filters)
            except OperationFailure as error:
                self.log.error(f'Failed to find data: {error.details}')
            except Exception:
                self.log.exception('Failed to query collection')
        return None

    def update_one(self, collection_name: str, query: dict, update: dict, upsert: bool = False):
        collection = self.__get_collection(collection_name)
        if collection is not None:
            try:
                return collection.update_one(query, update, upsert=upsert)
            except OperationFailure as error:
                self.log.error(f'Failed to update data: {error.details}')
            except Exception:
                self.log.exception(f'Failed to update document: {query}')
        return None

    def update_many(self, collection_name: str, query: dict, update: dict, upsert: bool = False):
        collection = self.__get_collection(collection_name)
        if collection is not None:
            try:
                return collection.update_many(query, update, upsert=upsert)
            except OperationFailure as error:
                self.log.error(f'Failed to update data: {error.details}')
            except Exception:
                self.log.exception(f'Failed to update documents: {query}')
        return None

    def delete_one(self, collection_name: str, query: dict) -> bool:
        collection = self.__get_collection(collection_name)
        if collection is not None:
            try:
                collection.delete_one(query)
                return True
            except OperationFailure as error:
                self.log.error(f'Failed to delete data: {error.details}')
            except Exception:
                self.log.exception(f'Failed to delete document: {query}')
        return False

    def delete_many(self, collection_name: str, query: dict) -> bool:
        collection = self.__get_collection(collection_name)
        if collection is not None:
            try:
                collection.delete_many(query)
                return True
            except OperationFailure as error:
                self.log.error(f'Failed to delete data: {error.details}')
            except Exception:
                self.log.exception(f'Failed to delete documents: {query}')
        return False


class Utils():
    def __init__(self, logger: Logger = None):
        self.log = logger or get_logger('dock-schedule')

    @property
    def ansible_private_key(self):
        return '/opt/dock-schedule/ansible/.env/.ansible_rsa'

    @property
    def ansible_env_vars(self):
        return {
            'ANSIBLE_CONFIG': '/opt/dock-schedule/ansible/ansible.cfg',
            'ANSIBLE_PYTHON_INTERPRETER': '/usr/bin/python3',
            'ANSIBLE_PRIVATE_KEY_FILE': self.ansible_private_key,
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

    def set_workers(self, worker_qty: int = 1):
        return self._run_cmd(f'docker service scale dock-schedule_worker={worker_qty} -d')[1]

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
