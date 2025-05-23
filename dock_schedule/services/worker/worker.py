#!/usr/bin/env python3

import ssl
import logging
from time import sleep, gmtime
from threading import Thread, Event, local
from typing import Dict
from tempfile import TemporaryDirectory
from urllib.parse import quote_plus
from datetime import datetime
from queue import Queue
from uuid import uuid4

import ansible_runner
from pika import SelectConnection, BaseConnection
from pika.adapters.blocking_connection import BlockingChannel
from pika.credentials import PlainCredentials
from pika.channel import Channel
from pika.connection import ConnectionParameters, SSLOptions
from pika.spec import Basic
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure, ServerSelectionTimeoutError


thread_local = local()


def get_logger():
    log = logging.getLogger('dock-worker')
    log.setLevel(logging.INFO)
    if not log.hasHandlers():
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('[%(asctime)s][%(levelname)s][%(module)s,%(lineno)d]: %(message)s')
        formatter.converter = gmtime
        stream_handler.setFormatter(formatter)
        log.addHandler(stream_handler)
    return log


class Mongo():
    def __init__(self, client_id: str = None, logger: logging.Logger = None):
        self.log = logger
        self.__id = client_id or str(uuid4())[:8]
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
                            tlsCAFile='/app/ca.crt',
                            tlsCertificateKeyFile='/app/host.pem',
                            serverSelectionTimeoutMS=2000
                        )
                        self.__client.admin.command('ping')
                        self.log.info(f'[{self.__id}] MongoDB client created successfully')
                        return self.__client
                    except ServerSelectionTimeoutError:
                        self.log.error(f'[{self.__id}] Failed to connect to MongoDB {attempt + 1}/35')
                    except ConnectionFailure:
                        self.log.exception(f'[{self.__id}] Failed to connect to MongoDB')
                    except Exception:
                        self.log.exception(f'[{self.__id}] Failed to create MongoDB client')
                        return None
                    sleep(2)
        return self.__client

    def __load_creds(self):
        for key in self.__creds.keys():
            try:
                with open(f'/run/secrets/mongo_{key}', 'r') as f:
                    self.__creds[key] = f.read().strip()
            except Exception:
                self.log.exception(f'[{self.__id}] Failed to load mongodb credentials for {key}')
                return False
        return True

    def __get_db(self):
        if self.client:
            try:
                return self.client[self.__creds.get('db')]
            except Exception:
                self.log.exception(f'[{self.__id}] Failed to get database object')
        return None

    def __get_collection(self, collection_name: str = 'jobs'):
        db = self.__get_db()
        if db is not None:
            try:
                return db[collection_name]
            except Exception:
                self.log.exception(f'[{self.__id}] Failed to get collection: {collection_name}')
        return None

    def update_one(self, query: dict, update: dict, upsert: bool = False):
        collection = self.__get_collection()
        if collection is not None:
            try:
                return collection.update_one(query, update, upsert=upsert)
            except OperationFailure as error:
                self.log.error(f'[{self.__id}] Failed to update data: {error.details}')
            except Exception:
                self.log.exception(f'[{self.__id}] Failed to update document: {query}')
        return None

    def get_one(self, collection_name: str, *filters: dict):
        collection = self.__get_collection(collection_name)
        if collection is not None:
            try:
                return collection.find_one(*filters)
            except OperationFailure as error:
                self.log.error(f'[{self.__id}] Failed to find data: {error.details}')
            except Exception:
                self.log.exception(f'[{self.__id}] Failed to find data')
        return None


class JobConsumer():
    def __init__(self, consumer_id: str, queue: Queue, logger: logging.Logger = None):
        self.log = logger or get_logger()
        self.__id = consumer_id
        self.__queue = queue
        self.__route = 'job-queue'
        self.__exchange = 'dock-schedule'
        self.__thread: Thread | None = None
        self.__client: SelectConnection | None = None
        self.__channel: BlockingChannel | None = None
        self.__connect_attempt = 0
        self.__max_connect_attempts = 36
        self.__reconnecting = False
        self.__bind_set = False
        self.__conn_blocked = False
        self.__queue_declared = False

    @property
    def client_exists(self):
        if self.__client and self.__client.is_open:
            if self.__channel:
                if self.__channel.is_open:
                    return True
                return self.__wait_for_channel_open()
            self.log.error(f'[{self.__id}] Broker connection channel is closed')
        else:
            self.log.error(f'[{self.__id}] Broker connection is closed')
        return False

    def __wait_for_channel_open(self):
        cnt = 0
        if self.__channel is not None:
            while not self.__channel.is_open:
                cnt += 1
                if cnt > 100:
                    self.log.error(f'[{self.__id}] Failed to open channel')
                    return False
                sleep(.2)
            self.log.debug(f'[{self.__id}] Channel is open')
            return True
        self.log.error(f'[{self.__id}] Channel does not exist')
        return False

    def __wait_for_bind_set(self):
        while not self.__bind_set:
            if self.__connect_attempt == self.__max_connect_attempts:
                self.log.error(f'[{self.__id}] Failed to set queue bind')
                return False
            sleep(.2)
        self.log.info(f'[{self.__id}] Successfully set queue')
        return True

    def __wait_for_conn_unblock(self, timeout: int = 180):
        self.__conn_blocked = True
        cnt = 0
        while self.__conn_blocked:
            sleep(1)
            cnt += 1
            if cnt > timeout:
                self.log.error(f'[{self.__id}] Timeout waiting for connection unblock')
                return False
        return True

    def __conn_unblocked(self):
        self.__conn_blocked = False

    def __load_credentials(self):
        creds = {'user': '', 'passwd': '', 'vhost': ''}
        for key in creds.keys():
            try:
                with open(f'/run/secrets/broker_{key}', 'r') as f:
                    creds[key] = f.read().strip()
            except Exception:
                self.log.exception(f'[{self.__id}] Failed to load broker credentials for {key}')
        return creds

    def __create_connection_ssl_obj(self):
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.load_verify_locations('/app/ca.crt')
            context.load_cert_chain('/app/host.crt', '/app/host.key')
            context.verify_mode = ssl.CERT_REQUIRED
            context.check_hostname = True
            return SSLOptions(context, 'broker')
        except Exception:
            self.log.exception(f'[{self.__id}] Failed to create SSL context for broker connection')
        return None

    def __create_connection_parameters(self):
        creds: dict = self.__load_credentials()
        if creds:
            ssl = self.__create_connection_ssl_obj()
            if ssl:
                try:
                    return ConnectionParameters(
                        host='broker',
                        port=5671,
                        virtual_host=creds.get('vhost', '/'),
                        credentials=PlainCredentials(creds.get('user', ''), creds.get('passwd', '')),
                        heartbeat=15,
                        blocked_connection_timeout=20,
                        ssl_options=ssl
                    )
                except Exception:
                    self.log.exception(f'[{self.__id}] Failed to create connection parameters')
        return None

    def __reconnect_attempt(self):
        self.__reconnecting = True
        if self.__connect_attempt < self.__max_connect_attempts:
            if self.__connect_attempt != 0:
                sleep(5)
            self.__connect_attempt += 1
            self.log.info(
                f'[{self.__id}] Reconnecting to broker {self.__connect_attempt}/{self.__max_connect_attempts - 1}')
            return self._restart_io_loop_in_thread()
        return False

    def __connect(self, on_connect: callable = None, on_failed: callable = None, on_closed: callable = None):
        self.log.info(f'[{self.__id}] Connecting to message broker')
        params = self.__create_connection_parameters()
        if params:
            try:
                return SelectConnection(params, on_connect, on_failed, on_closed)
            except Exception:
                self.log.exception(f'[{self.__id}] Failed to create connection to broker')
        return None

    def __connect_success(self, connection: BaseConnection):
        self.log.info(f'[{self.__id}] Successfully connected to broker')
        self.__connect_attempt = 0
        connection.channel(on_open_callback=self.__open_channel)

    def __connect_failed(self, *args: tuple):
        self.log.error(f'[{self.__id}] Failed to create connection to broker: {args[1]}')
        return self.__reconnect_attempt()

    def __connect_closed(self, *args: tuple):
        self.log.error(f'[{self.__id}] Connection closed: {args[1]}')
        return self.__reconnect_attempt()

    def __open_channel(self, channel: BlockingChannel):
        self.log.info(f'[{self.__id}] Successfully opened channel')
        self.__channel = channel
        self.__set_queue_bind()

    def __set_queue_bind(self):
        try:
            self.__channel.exchange_declare(self.__exchange, 'direct')
            self.__channel.queue_declare(self.__route, durable=True)
            self.__channel.basic_qos(prefetch_count=3)
            self.log.info(f'[{self.__id}] Successfully set exchange')
            self.__channel.queue_bind(self.__route, self.__exchange, self.__route)
            self.__bind_set = True
            self.__reconnecting = False
            self.__conn_blocked = False
        except Exception:
            self.log.exception(f'[{self.__id}] Failed to bind to queue')
            return False
        return self.__start_consuming_queue()

    def __add_job_to_queue(self, ch: Channel, method: Basic.Deliver, _, body: bytes):
        self.__queue.put((ch, method, body))

    def __start_consuming_queue(self):
        try:
            self.log.info(f'[{self.__id}] Starting to consume messages from queue')
            self.__channel.basic_consume(self.__route, self.__add_job_to_queue, False)
            return True
        except Exception:
            self.log.exception(f'[{self.__id}] Exception occurred while consuming message queue')
            return False

    def __reset_connect_state(self):
        self.__channel = None
        self.__client = None
        self.__bind_set = False

    def __start_io_loop(self) -> bool:
        self.__client = self.__connect(self.__connect_success, self.__connect_failed, self.__connect_closed)
        if self.__client is not None:
            try:
                self.__client.add_on_connection_blocked_callback(self.__wait_for_conn_unblock)
                self.__client.add_on_connection_unblocked_callback(self.__conn_unblocked)
                self.__client.ioloop.start()
                return True
            except Exception:
                self.log.exception(f'[{self.__id}] Exception occurred in IO loop')
        return False

    def __stop_io_loop(self):
        try:
            if self.__channel is not None:
                if self.__channel.is_open:
                    self.__channel.close()
            if self.__client is not None:
                if self.__client.is_open:
                    self.__client.close()
                self.__client.ioloop.stop()
            self.__reset_connect_state()
            return True
        except Exception:
            self.log.exception(f'[{self.__id}] Exception occurred while stopping IO-loop')
            return False

    def __stop_thread(self):
        if self.__thread:
            try:
                if self.__thread.is_alive():
                    self.__thread.join(3)
                    if self.__thread.is_alive():
                        self.log.error(f'[{self.__id}] Failed to stop broker thread')
                        return False
                    self.__thread = None
                    self.log.info(f'[{self.__id}] Successfully stopped broker thread')
                return True
            except Exception:
                self.log.exception(f'[{self.__id}] Exception occurred while stopping broker thread')
        self.log.debug(f'[{self.__id}] Broker thread does not exist to stop')
        return True

    def _wait_for_reconnect(self, timeout: int = 1800):
        cnt = 0
        while self.__reconnecting:
            self.log.info(f'[{self.__id}] Waiting for reconnection...')
            sleep(1)
            cnt += 1
            if cnt > timeout:
                self.log.error(f'[{self.__id}] Timeout waiting for reconnection')
                return False
        return True

    def _restart_io_loop_in_thread(self):
        """The connection to the broker is done in a separate thread to avoid blocking the main thread. This method
        will get called via the reconnect procedure to restart the connection to the broker within the thread.
        __start_io_loop might not return as it will be running the IO loop until the connection is closed. This is OK.

        Returns:
            bool: True if the connection was successfully restarted, otherwise False
        """
        if self.__stop_io_loop():
            return self.__start_io_loop()
        self.log.error(f'[{self.__id}] Failed to restart broker connection')
        return False

    def __configure_queue(self):
        if not self.__queue_declared:
            try:
                self.__channel.queue_declare(self.__route, durable=True)
                self.__queue_declared = True
                self.log.info(f'[{self.__id}] Successfully declared queue')
            except Exception:
                self.log.exception(f'[{self.__id}] Failed to declare queue')
                return False
        return True

    def __handle_blocked_connection(self):
        self.log.info(f'[{self.__id}] Connection blocked, waiting for unblock from server...')
        while self.__conn_blocked:
            sleep(.5)
        self.log.info(f'[{self.__id}] Connection unblocked, resuming operations...')

    def __can_send(self) -> bool:
        if self.__conn_blocked:
            self.__handle_blocked_connection()
        if self.client_exists:
            return self.__configure_queue()
        if self._wait_for_reconnect():
            return self.__can_send()
        return False

    def start(self):
        if self.__thread:
            self.log.error(f'[{self.__id}] Broker already running')
            return False
        self.log.info(f'[{self.__id}] Starting broker')
        try:
            self.__thread = Thread(target=self.__start_io_loop, daemon=True)
            self.__thread.start()
            if self.__wait_for_bind_set():
                return True
            self.log.error(f'[{self.__id}] Failed to start broker')
            return False
        except Exception:
            self.log.exception(f'[{self.__id}] Failed to start broker')
        return False

    def stop(self):
        self.log.info(f'[{self.__id}] Stopping broker')
        if self.__stop_io_loop():
            return self.__stop_thread()
        self.log.error(f'[{self.__id}] Failed to stop broker')
        return False


class Worker():
    def __init__(self):
        self.log = get_logger()
        self.stop_trigger = Event()
        self.__threads = []
        self.__create_worker_threads()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.stop_trigger.set()
        for thread in self.__threads:
            if thread.is_alive():
                thread.join(1)
        return

    def __init_worker(self):
        thread_local.consumer_id = str(uuid4())[:8]
        self.log.info(f'[{thread_local.consumer_id}] Initializing worker thread')
        queue = Queue(3)
        thread_local.db = Mongo(thread_local.consumer_id, self.log)
        thread_local.consumer = JobConsumer(thread_local.consumer_id, queue, self.log)
        if not thread_local.consumer.start():
            raise Exception(f'[{thread_local.consumer_id}] Failed to start job consumer')
        while not self.stop_trigger.is_set():
            self.__job_request_handler(*queue.get())
        thread_local.consumer.stop()

    def __create_worker_threads(self):
        for _ in range(3):
            thread = Thread(target=self.__init_worker, daemon=True)
            thread.start()
            self.__threads.append(thread)

    def __job_request_handler(self, ch: Channel, method: Basic.Deliver, body: bytes):
        job = thread_local.db.get_one('jobs', {'_id': body.decode()})
        if job:
            if job.get('state', '') == 'pending':
                self.run_job(job)
            else:
                self.log.info(f'[{thread_local.consumer_id}] Job already running: {job.get("_id")[:8]}')
            try:
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception:
                self.log.exception(f'[{thread_local.consumer_id}] Failed to ack message')
        else:
            self.log.error(f'[{thread_local.consumer_id}] Job not found in database: {body.decode()}')

    @property
    def ansible_env_vars(self) -> Dict:
        """Get Ansible environment variables

        Returns:
            dict: Ansible environment variables
        """
        return {
            'ANSIBLE_CONFIG': '/app/ansible/ansible.cfg',
            'ANSIBLE_PYTHON_INTERPRETER': '/usr/bin/python3',
            'ANSIBLE_PRIVATE_KEY_FILE': '/app/ansible/.env/.ansible_rsa',
        }

    def __parse_host_inventory(self, inventory: Dict | None) -> Dict:
        if inventory:
            if isinstance(inventory, dict):
                __inventory = {'all': {'hosts': {}}}
                for host, ip in inventory.items():
                    __inventory['all']['hosts'][host] = {'ansible_host': ip}
                return __inventory
            else:
                self.log.error(f'[{thread_local.consumer_id}] Invalid inventory type: {type(inventory)}')
                return {}
        return {'all': {'hosts': {'localhost': {'ansible_connection': 'local'}}}}

    def __parse_script_type(self, script_type: str | None, job_name: str) -> str:
        if script_type in ['python3', 'ansible', 'bash', 'php', 'node']:
            return script_type
        suffix = job_name.split('.')[-1]
        if suffix == 'py':
            return 'python3'
        if suffix == 'sh':
            return 'bash'
        if suffix == 'php':
            return 'php'
        if suffix == 'js' or script_type == 'javascript':
            return 'node'
        if suffix == 'yml' or suffix == 'yaml':
            return 'ansible'
        self.log.error(f'[{thread_local.consumer_id}] Unknown script type: {script_type} for job: {job_name}')
        return ''

    def __parse_playbook(self, job: Dict) -> str:
        script_type = self.__parse_script_type(job.get('type'), job.get('run'))
        if script_type:
            if script_type == 'ansible':
                playbook = f'/app/ansible/playbooks/{job.get("run")}'
            else:
                playbook = '/app/ansible/playbooks/run_job_script.yml'
                job['extraVars'] = {
                    'script_file': job.get('run'),
                    'script_type': script_type,
                    'script_args': job.get('args', []),
                }
            return playbook
        return ''

    def __handle_result(self, result: ansible_runner.runner.Runner, job: Dict):
        job['state'] = 'completed'
        job['end'] = datetime.now()
        job['tasks'] = []
        for event in result.events:
            if event.get('event') not in ['runner_on_ok', 'runner_on_failed']:
                continue
            data = event.get('event_data', {})
            res = data.get('res', {})
            task_info = {
                'task': data.get('task', 'Unknown'),
                'host': data.get('host', 'Unknown'),
                'rc': res.get('rc', -1),
                'stdin': res.get('cmd', []),
                'stdout': res.get('stdout_lines', []),
                'stderr': res.get('stderr_lines', []),
                'msg': res.get('msg', ''),
            }
            if event.get('event') == 'runner_on_failed':
                msg = res.get('stderr', '') or task_info.get('msg')
                error = f"Task: {task_info.get('task')}, Host: {task_info.get('host')}, Error: {msg}"
                self.log.error(error)
                job['errors'].append(error)
            job['tasks'].append(task_info)
        if result.rc == 0:
            self.log.info(
                f"[{thread_local.consumer_id}] Job completed successfully: {job.get("name")} {job.get("_id")[:8]}")
            job['result'] = True
        else:
            job['result'] = False
            self.log.error(f"[{thread_local.consumer_id}] Job failed: {job.get('name')} {job.get('_id')[:8]}")
        if not thread_local.db.update_one({'_id': job.get('_id')}, {'$set': job}):
            self.log.error(f"[{thread_local.consumer_id}] Failed to update job status in database: {job.get('_id')}")
        return job['result']

    def run_job(self, job: Dict) -> bool:
        self.log.info(f'[{thread_local.consumer_id}] Running job: {job.get("name")} {job.get("_id")[:8]}')
        job['start'] = datetime.now()
        job['state'] = 'running'
        thread_local.db.update_one({'_id': job.get('_id')}, {'$set': job})
        inventory = self.__parse_host_inventory(job.get('hostInventory'))
        playbook = self.__parse_playbook(job)
        if inventory and playbook:
            with TemporaryDirectory(prefix=f'job-{job.get("_id")}-', dir='/tmp', delete=True) as temp_dir:
                return self.__handle_result(ansible_runner.run(
                    private_data_dir=temp_dir,
                    playbook=playbook,
                    inventory=inventory,
                    envvars=self.ansible_env_vars,
                    extravars=job.get('extraVars', {}),
                    quiet=True
                ), job)
        return False


def main():
    with Worker() as worker:
        while not worker.stop_trigger.is_set():
            sleep(1)


if __name__ == "__main__":
    main()
