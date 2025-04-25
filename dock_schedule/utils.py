
import json
from pathlib import Path
from subprocess import run
from tempfile import TemporaryDirectory
from logging import Logger
from typing import Dict, List
from uuid import uuid4
from urllib.parse import quote_plus

import ansible_runner
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
from pytz import all_timezones_set

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
                try:
                    self.__client = MongoClient(
                        host=self.__host,
                        tls=True,
                        tlsCAFile='/etc/docker/ca.crt',
                        tlsCertificateKeyFile='/etc/docker/host.pem',
                    )
                except ConnectionFailure:
                    self.log.exception('Failed to connect to MongoDB')
                except Exception:
                    self.log.exception('Failed to create MongoDB client')
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


class Schedule(Utils):
    def __init__(self, logger: Logger = None):
        super().__init__(logger)
        self.__db = Mongo(self.log)

    def get_job_schedule(self) -> List[Dict] | None:
        return self.__db.get_all('crons')

    def display_all_job_schedules(self):
        schedule = self.get_job_schedule()
        if schedule is not None:
            return self._display_info('Job Schedule:\n' + json.dumps(schedule, indent=2))
        return False

    def __check_job_run_file_exists(self, job_type: str, job_run: str) -> bool:
        if job_type == 'ansible':
            job_file = f'/opt/dock-schedule/ansible/playbooks/{job_run}'
        else:
            job_file = f'/opt/dock-schedule/jobs/{job_type}/{job_run}'
        if not Path(job_file).exists():
            self.log.error(f'Job run file does not exist: {job_file}')
            return False
        return True

    def __set_update_flag(self):
        if not self.__db.update_one('cronUpdate', {'_id': 1}, {'$set': {'update': True}}):
            self.log.error('Failed to set update flag')
            return False
        return True

    @property
    def __schedule_keys(self):
        return {
            'name', 'type', 'run', 'args', 'frequency', 'interval',
            'at', 'timezone', 'hostInventory', 'extraVars', 'disabled'
        }

    def create_cron_job(self, job: Dict) -> bool:
        """Create a job cron

        Args:
            job (Dict): Job data used to create the cron job

                name (str): name of the job

                type (str): type of the job (ansible, python3, bash, php, node)

                run (str): name of the job run file (ansible playbook name or script type file name)

                args (list[str]): arguments to pass to non ansible job types

                frequency (str): frequency of the job (second, minute, hour, day)

                interval (int): frequency interval (1, 2, 3, etc)

                at (str): time to run the job (HH:MM:SS)

                timezone (str): timezone to run the job (UTC, EST, PST, etc)

                hostInventory (str): host inventory to run the job on (ansible inventory)

                extraVars (str): extra variables to pass to the job (ansible extra vars)

                disabled (bool): job is disabled and will not run until reenabled

        Returns:
            bool: True if successful, False otherwise
        """
        if not job.get('interval') and not job.get('at'):
            return self._display_error('Error: --interval (-i) or --at (-A) is required for job creation')
        if self.__check_job_run_file_exists(job.get('type'), job.get('run')):
            if not self.__validate_timezone(job.get('timezone')):
                return False
            if 'at' in job:
                if not self.__validate_job_at_time(job.get('frequency'), job.get('at')):
                    return False
            job['_id'] = str(uuid4())
            if job.get('type') == 'ansible':
                if not self.__parse_ansible_job_data(job):
                    return False
            if self.__db.insert_one('crons', job):
                self.log.info(f'Job {job.get("name")} created successfully')
                return self.__set_update_flag()
        self.log.error(f'Failed to create job {job.get("name")}')
        return False

    def __parse_key_value_data(self, parse: str | Dict) -> Dict:
        if isinstance(parse, dict):
            return parse
        data = {}
        pair_count = parse.count('=')
        if pair_count == 0:
            self.log.error(f'Invalid key=value syntax: {parse}')
            return {}
        if pair_count == 1:
            key, value = parse.split('=')
            data[key.strip()] = value.strip()
            return data
        if parse.count(',') + 1 != pair_count:
            self.log.error(f'Invalid "key1=value1, key2=value2, etc..." syntax: {parse}')
            return {}
        for key_value in parse.split(','):
            if '=' not in key_value:
                self.log.error(f'Invalid key=value syntax: {key_value}')
                return {}
            key, value = key_value.split('=')
            data[key.strip()] = value.strip()
        return data

    def __parse_ansible_job_data(self, job: Dict) -> Dict:
        if job.get('hostInventory'):
            data = self.__parse_key_value_data(job['hostInventory'])
            if not data:
                return False
            job['hostInventory'] = data
        else:
            job['hostInventory'] = {}
        if job.get('extraVars'):
            data = self.__parse_key_value_data(job['extraVars'])
            if not data:
                return False
            job['extraVars'] = data
        else:
            job['extraVars'] = {}
        return True

    def __validate_job_at_time(self, freq: str, at: str) -> bool:
        if freq == 'second':
            self.log.error('Frequency cannot be set to "second" when using "at"')
            return False
        if freq == 'minute':
            if len(at) != 3 or at[0] != ':' or not at[1:].isdigit():
                self.log.error('Invalid time format for "at" with frequency "minute" (:SS), examples: :30, :05')
                return False
            return True
        if freq == 'hour':
            if len(at) == 3:
                if at[0] == ':' and at[1:].isdigit():
                    return True
            elif len(at) == 5:
                if at[2] == ':' and at[:2].isdigit() and at[3:].isdigit():
                    return True
            self.log.error('Invalid time format for "at" with frequency "hour" (MM:SS or :MM) examples: :30:05, :05')
            return False
        if freq == 'day':
            if len(at) == 5:
                if at[2] == ':' and at[:2].isdigit() and at[3:].isdigit():
                    return True
            elif len(at) == 8:
                if at[2] == ':' and at[5] == ':' and at[:2].isdigit() and at[3:5].isdigit() and at[6:].isdigit():
                    return True
            self.log.error('Invalid time format for "at" with frequency "day" (HH:MM:SS or HH:MM), examples: \
                12:30:05, 05:30')
        else:
            self.log.error('Invalid frequency, must be one of: second, minute, hour, day')
        return False

    def __validate_timezone(self, timezone: str) -> bool:
        if timezone in all_timezones_set:
            return True
        self.log.error(f'Invalid timezone: {timezone}')
        zones = list(all_timezones_set)
        zones.sort()
        return self._display_error(f'Must be one of: {json.dumps(zones, indent=2)}')

    def get_timezone_options(self):
        zones = list(all_timezones_set)
        zones.sort()
        return self._display_info(f'Must be one of: {json.dumps(zones, indent=2)}')

    def delete_cron_job(self, job_id: str):
        if len(job_id) != 36:
            self.log.error(f'Invalid job ID: {job_id}')
            return False
        if self.__db.get_one('crons', {'_id': job_id}) is None:
            self.log.error(f'Failed to delete job ID {job_id}, does not exist')
            return False
        if self.__db.delete_one('crons', {'_id': job_id}):
            self.log.info(f'Successfully deleted job ID {job_id}')
            return self.__set_update_flag()
        self.log.error(f'Failed to delete job ID {job_id}')
        return False

    def update_cron_job(self, job_id: str, update: dict) -> bool:
        if len(job_id) != 36:
            self.log.error(f'Invalid job ID: {job_id}')
            return False
        job = self.__db.get_one('crons', {'_id': job_id})
        if job is None:
            self.log.error(f'Failed to update job ID {job_id}, does not exist')
            return False
        data = {}
        for key, value in update.items():
            if value is None:
                continue
            if key == 'state':
                data['disabled'] = value.lower() == 'disabled'
            else:
                if key not in self.__schedule_keys:
                    self.log.error(f'Invalid key: {key}')
                    return False
                if key in ['hostInventory', 'extraVars']:
                    value = self.__parse_key_value_data(value)
                    if not value:
                        self.log.error(f'Failed to parse {key} data')
                        return False
                elif key == 'type':
                    if not self.__check_job_run_file_exists(value, update.get('run') or job.get('run')):
                        return False
                elif key == 'run':
                    if not self.__check_job_run_file_exists(update.get('type') or job.get('type'), value):
                        return False
                elif key == 'at':
                    if value == 'None':
                        value = None
                    elif not self.__validate_job_at_time(update.get('frequency') or job.get('frequency'), value):
                        return False
                elif key == 'interval':
                    if value.isdigit():
                        value = int(value)
                    elif value.lower() == 'none':
                        value = None
                    else:
                        self.log.error(f'Invalid interval value: {value}')
                        return False
                elif key == 'args':
                    if value[0] == 'NONE':
                        value = None
                elif value.lower() == 'none':
                    value = None
                elif key == 'timezone':
                    if not self.__validate_timezone(value):
                        return False
                data[key] = value
        job.update(data)
        if self.__db.update_one('crons', {'_id': job_id}, {'$set': job}):
            self.log.info(f'Successfully updated job ID {job_id}')
            return self.__set_update_flag()
        self.log.error(f'Failed to update job ID {job_id}')
        return False

    def get_job_by_id(self, job_id: str) -> Dict | None:
        if len(job_id) != 36:
            self.log.error(f'Invalid job ID: {job_id}')
            return None
        job = self.__db.get_one('crons', {'_id': job_id})
        if job is None:
            self.log.error(f'Failed to get job ID {job_id}, does not exist')
            return None
        return job

    def get_job_by_name(self, job_name: str) -> Dict | None:
        job = self.__db.get_all('crons', {'name': job_name})
        if job is None:
            self.log.error(f'Failed to get job {job_name}, does not exist')
            return None
        return job

    def get_job_by_type(self, job_type: str) -> List[Dict] | None:
        job = self.__db.get_all('crons', {'type': job_type})
        if job is None:
            self.log.error(f'Failed to get job type {job_type}, does not exist')
            return None
        return job

    def get_job_by_run(self, job_run: str) -> List[Dict] | None:
        job = self.__db.get_all('crons', {'run': job_run})
        if job is None:
            self.log.error(f'Failed to get job run {job_run}, does not exist')
            return None
        return job

    def display_job_schedule(self, job_name: str = None, job_id: str = None, job_type: str = None,
                             job_run: str = None) -> bool:
        job = None
        if job_id:
            job = self.get_job_by_id(job_id)
        elif job_name:
            job = self.get_job_by_name(job_name)
        elif job_type:
            job = self.get_job_by_type(job_type)
        elif job_run:
            job = self.get_job_by_run(job_run)
        else:
            self.log.error('Job name or job ID is required')
            return False
        if job is not None:
            return self._display_info(f'Job Schedule:\n{json.dumps(job, indent=2)}')
        return False
