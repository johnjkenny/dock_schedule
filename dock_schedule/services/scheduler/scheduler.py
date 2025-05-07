#!/usr/bin/env python3

import ssl
import logging
from time import sleep, gmtime
from threading import Thread, Event, local
from multiprocessing import Process, Queue
from queue import Empty
from uuid import uuid4
from json import loads
from typing import Dict
from urllib.parse import quote_plus
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

import schedule
import uvicorn
from fastapi import FastAPI, Request, Response
from pika import SelectConnection, BaseConnection, BasicProperties
from pika.adapters.blocking_connection import BlockingChannel
from pika.credentials import PlainCredentials
from pika.channel import Channel
from pika.connection import ConnectionParameters, SSLOptions
from pika.spec import Basic
from pymongo import MongoClient, DESCENDING
from pymongo.errors import ConnectionFailure, OperationFailure, ServerSelectionTimeoutError


thread_local = local()


def get_logger():
    log = logging.getLogger('dock-scheduler')
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

    def insert_one(self, collection_name: str, document: dict):
        collection = self.__get_collection(collection_name)
        if collection is not None:
            try:
                return collection.insert_one(document)
            except OperationFailure as error:
                self.log.error(f'[{self.__id}] failed to insert document: {error.details}')
            except Exception:
                self.log.exception(f'[{self.__id}] Failed to insert document: {document}')
        return None

    def insert_many(self, collection_name: str, documents: list[dict]):
        collection = self.__get_collection(collection_name)
        if collection is not None:
            try:
                return collection.insert_many(documents)
            except OperationFailure as error:
                self.log.error(f'[{self.__id}] Failed to insert documents: {error.details}')
            except Exception:
                self.log.exception(f'[{self.__id}] Failed to insert documents: {documents}')
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

    def get_all(self, collection_name: str, *filters: dict):
        collection = self.__get_collection(collection_name)
        if collection is not None:
            try:
                return list(collection.find(*filters))
            except OperationFailure as error:
                self.log.error(f'[{self.__id}] Failed to find data: {error.details}')
            except Exception:
                self.log.exception(f'[{self.__id}] Failed to query collection')
        return []

    def get_all_with_cursor(self, collection_name: str, *filters: dict):
        collection = self.__get_collection(collection_name)
        if collection is not None:
            try:
                return collection.find(*filters)
            except OperationFailure as error:
                self.log.error(f'[{self.__id}] Failed to find data: {error.details}')
            except Exception:
                self.log.exception(f'[{self.__id}] Failed to query collection')
        return None

    def update_one(self, collection_name: str, query: dict, update: dict, upsert: bool = False):
        collection = self.__get_collection(collection_name)
        if collection is not None:
            try:
                return collection.update_one(query, update, upsert=upsert)
            except OperationFailure as error:
                self.log.error(f'[{self.__id}] Failed to update data: {error.details}')
            except Exception:
                self.log.exception(f'[{self.__id}] Failed to update document: {query}')
        return None

    def update_many(self, collection_name: str, query: dict, update: dict, upsert: bool = False):
        collection = self.__get_collection(collection_name)
        if collection is not None:
            try:
                return collection.update_many(query, update, upsert=upsert)
            except OperationFailure as error:
                self.log.error(f'[{self.__id}] Failed to update data: {error.details}')
            except Exception:
                self.log.exception(f'[{self.__id}] Failed to update documents: {query}')
        return None

    def delete_one(self, collection_name: str, query: dict) -> bool:
        collection = self.__get_collection(collection_name)
        if collection is not None:
            try:
                collection.delete_one(query)
                return True
            except OperationFailure as error:
                self.log.error(f'[{self.__id}] Failed to delete data: {error.details}')
            except Exception:
                self.log.exception(f'[{self.__id}] Failed to delete document: {query}')
        return False

    def delete_many(self, collection_name: str, query: dict) -> bool:
        collection = self.__get_collection(collection_name)
        if collection is not None:
            try:
                collection.delete_many(query)
                return True
            except OperationFailure as error:
                self.log.error(f'[{self.__id}] Failed to delete data: {error.details}')
            except Exception:
                self.log.exception(f'[{self.__id}] Failed to delete documents: {query}')
        return False

    def count_documents(self, collection_name: str, query: Dict) -> int:
        collection = self.__get_collection(collection_name)
        if collection is not None:
            try:
                return collection.count_documents(query, maxTimeMS=2000)
            except OperationFailure as error:
                self.log.error(f'[{self.__id}] Failed to count documents: {error.details}')
            except Exception:
                self.log.exception(f'[{self.__id}] Failed to count documents')
        return 0


class WebServer():
    def __init__(self, queue: Queue, logger: logging.Logger):
        self.log = logger
        self._app = FastAPI()
        self.__db: Mongo | None = None
        self.__msg_queue = queue
        self.__process: Process | None = None

        @self._app.get('/is-running')
        def is_running_route() -> Response:
            """Check if the server is running route

            Returns:
                Response: 200 response if the server is running
            """
            return Response('Web-Server is running', 200)

        @self._app.get('/metrics')
        def metrics_route() -> Response:
            if self.__db is None:
                self.__db = Mongo('web-server', self.log)
            try:
                total_jobs = self.__db.count_documents('jobs', {})
                pending_jobs = self.__db.count_documents('jobs', {'state': 'pending'})
                running_jobs = self.__db.count_documents('jobs', {'state': 'running'})
                successful_jobs = self.__db.count_documents('jobs', {'state': 'completed', 'result': True})
                failed_jobs = self.__db.count_documents('jobs', {'state': 'completed', 'result': False})
                total_crons = self.__db.count_documents('crons', {})
                total_crons_enabled = self.__db.count_documents('crons', {'disabled': False})
                output = [
                    "# HELP scheduler_jobs_total Total number of jobs submitted",
                    "# TYPE scheduler_jobs_total counter",
                    f"scheduler_jobs_total {total_jobs}",

                    "# HELP scheduler_jobs_pending Current number of pending jobs waiting to be run",
                    "# TYPE scheduler_jobs_pending gauge",
                    f"scheduler_jobs_pending {pending_jobs}",

                    "# HELP scheduler_jobs_running Current number of running jobs",
                    "# TYPE scheduler_jobs_running gauge",
                    f"scheduler_jobs_running {running_jobs}",

                    "# HELP scheduler_jobs_successful_total Total number of successful jobs run",
                    "# TYPE scheduler_jobs_successful_total counter",
                    f"scheduler_jobs_successful_total {successful_jobs}",

                    "# HELP scheduler_jobs_failed_total Total number of failed jobs run",
                    "# TYPE scheduler_jobs_failed_total counter",
                    f"scheduler_jobs_failed_total {failed_jobs}",

                    "# HELP scheduler_crons_total Total number of crons",
                    "# TYPE scheduler_crons_total counter",
                    f"scheduler_crons_total {total_crons}",

                    "# HELP scheduler_crons_enabled_total Total number of enabled crons",
                    "# TYPE scheduler_crons_enabled_total counter",
                    f"scheduler_crons_enabled_total {total_crons_enabled}",
                ]
                return Response('\n'.join(output), 200, media_type='text/plain')
            except Exception:
                self.log.exception('Failed to get metrics')
                return Response('Failed to get metrics', 500)

        @self._app.post('/run-job')
        async def receive_run_job_route(request: Request) -> Response:
            """Submit message route. The main route for receiving messages from a client

            Args:
                request (Request): request object

            Returns:
                Response: response based on the message received
            """
            raw_msg = await request.body()
            state = ('failed', 500)
            try:
                if isinstance(raw_msg, (bytes, str)):
                    job = loads(raw_msg)
                    if isinstance(job, dict):
                        state = ('success', 200)
                        job['request_type'] = 'run_job'
                        self.__msg_queue.put(job)
                    else:
                        self.log.error(f'Invalid message type received: {type(job)}')
                else:
                    self.log.error(f'Invalid message type received: {type(raw_msg)}')
            except Exception:
                self.log.exception('Failed to handle run job request')
                state = ('failed', 500)
            del raw_msg
            return Response(*state)

        @self._app.post('/job-update')
        async def receive_job_update_route(request: Request) -> Response:
            """Submit message route. The main route for receiving messages from a client

            Args:
                request (Request): request object

            Returns:
                Response: response based on the message received
            """
            raw_msg = await request.body()
            state = ('failed', 500)
            try:
                if isinstance(raw_msg, (bytes, str)):
                    job = loads(raw_msg)
                    if isinstance(job, dict):
                        state = ('success', 200)
                        job['request_type'] = 'job_update'
                        self.__msg_queue.put(job)
                    else:
                        self.log.error(f'Invalid message type received: {type(job)}')
                else:
                    self.log.error(f'Invalid message type received: {type(raw_msg)}')
            except Exception:
                self.log.exception('Failed to handle run job request')
                state = ('failed', 500)
            del raw_msg
            return Response(*state)

    @property
    def __certs(self):
        return {
            'ssl_ca_certs': '/app/ca.crt',
            'ssl_certfile': '/app/host.crt',
            'ssl_keyfile': '/app/host.key',
            'ssl_cert_reqs': ssl.CERT_REQUIRED
        }

    def __start_web_server(self) -> bool:
        """The web server process. Stays running and is handled by the parent process

        Returns:
            bool: True on successful start and stop. False otherwise
        """
        try:
            uvicorn.run(self._app, host='0.0.0.0', port=6000, proxy_headers=True, **self.__certs)
            return True
        except Exception:
            self.log.exception('Exception occurred in web server')
        return False

    def start(self) -> bool:
        """Start the web server cleaner thread and start the web server

        Returns:
            bool: True if the server started successfully, False otherwise
        """
        self.log.info('Starting scheduler web server')
        if self.__process and self.__process.is_alive():
            self.log.info('Server is already running')
            return True
        try:
            self.__process = Process(target=self.__start_web_server, daemon=True)
            self.__process.start()
            sleep(1)  # Give the server time to start
            return True
        except Exception:
            self.log.exception('Failed to start web server process')
        return False

    def stop(self) -> bool:
        """Stop the web server and the web server cleaner thread

        Returns:
            bool: True if the server stopped successfully, False otherwise
        """
        self.log.info('Stopping scheduler web server')
        if self.__process and self.__process.is_alive():
            try:
                self.__process.terminate()
                return True
            except Exception:
                self.log.exception('Failed to stop web server process')
                return False
        self.log.info('Web server process is not running')
        return True


class JobPublisher():
    def __init__(self, pub_id: str, logger: logging.Logger = None):
        self.log = logger or get_logger()
        self.__id = pub_id
        self.__route = 'job-queue'
        self.__exchange = 'dock-schedule'
        self.__thread: Thread | None = None
        self.__client: SelectConnection | None = None
        self.__channel: BlockingChannel | None = None
        self.__connect_attempt = 0
        self.__max_connect_attempts = 36
        self.__reconnecting = False
        self.__exchange_declared = False
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

    def __wait_for_exchange_declare(self):
        while not self.__exchange_declared:
            if self.__connect_attempt == self.__max_connect_attempts:
                self.log.error(f'[{self.__id}] Failed to declare exchange')
                return False
            sleep(.2)
        self.log.debug(f'[{self.__id}] Exchange declared')
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

    def __open_channel(self, channel: Channel):
        self.log.info(f'[{self.__id}] Successfully opened channel and set exchange')
        self.__channel = channel
        self.__channel.exchange_declare(self.__exchange, 'direct')
        self.__channel.add_on_return_callback(self.__returned_to_sender_handler)
        self.__channel.confirm_delivery(ack_nack_callback=self.__ack_nack_handler)
        self.__exchange_declared = True
        self.__reconnecting = False
        self.__conn_blocked = False

    def __ack_nack_handler(self, method_frame: Basic.Deliver):
        if method_frame.method.NAME != 'Basic.Ack':
            self.log.error(f'[{self.__id}] Message not acknowledged')
            if not self.__reconnecting:
                self.__reconnect_attempt()

    def __reset_connect_state(self):
        self.__client = None
        self.__channel = None
        self.__exchange_declared = False
        self.__queue_declared = False

    def __returned_to_sender_handler(self, ch: Channel, _: Basic.Deliver, properties: BasicProperties, body: bytes):
        try:
            job_id = body.decode()
            self.log.error(f'[{self.__id}] Message returned for job ID {job_id}. Resending to queue...')
            sleep(1)
            ch.basic_publish(
                exchange=self.__exchange,
                routing_key=self.__route,
                body=body,
                properties=properties,
                mandatory=True
            )
        except Exception:
            self.log.error(f'[{self.__id}] Failed to resend message to queue')

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

    def send_msg(self, msg: bytes, job_id: str):
        if isinstance(msg, bytes):
            if self.__can_send():
                try:
                    self.__channel.basic_publish(self.__exchange, self.__route, msg, BasicProperties(
                        content_type='application/octet-stream',
                        delivery_mode=2,
                        message_id=job_id
                    ))
                    self.log.info(f'[{self.__id}] Sent job to queue: {job_id[:8]}')
                    return True
                except Exception:
                    self.log.exception(f'[{self.__id}] Failed to send message to queue')
            else:
                self.log.error(f'[{self.__id}] Failed to send message to queue')
        else:
            self.log.error(f'[{self.__id}] Invalid message type: {type(msg)}')
        return False

    def start(self):
        if self.__thread:
            self.log.error(f'[{self.__id}] Broker already running')
            return False
        self.log.info(f'[{self.__id}] Starting broker')
        try:
            self.__thread = Thread(target=self.__start_io_loop, daemon=True)
            self.__thread.start()
            if self.__wait_for_exchange_declare():
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


class JobScheduler():
    def __init__(self):
        self.log = get_logger()
        self.stop_trigger = Event()
        self.__db = Mongo('parent', self.log)
        self.__run_job_queue = Queue()
        self.__web_server = WebServer(self.__run_job_queue, self.log)
        self._crons = schedule
        self.__pool = ThreadPoolExecutor(3, initializer=self.__init_scheduler)
        if not self.__web_server.start():
            raise Exception('Failed to start web server')

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.__pool.shutdown(wait=False)
        self.__web_server.stop()

    def __init_scheduler(self):
        thread_local.sched_id = str(uuid4())[:8]
        self.log.info(f'Initializing scheduler {thread_local.sched_id}')
        thread_local.db = Mongo(thread_local.sched_id, self.log)
        thread_local.publisher = JobPublisher(thread_local.sched_id, self.log)
        if not thread_local.publisher.start():
            raise Exception(f'[{thread_local.sched_id}] Failed to start job publisher')

    def __create_cron_job(self, cron: Dict):
        freq = cron.get('frequency')
        if freq == 'second':
            if cron.get('interval'):
                return self._crons.every(cron['interval']).seconds.do(self._run_cron, cron)
        elif freq == 'minute':
            if cron.get('at'):
                return self._crons.every().minute.at(cron['at'], cron.get('timezone', 'UTC')).do(self._run_cron, cron)
            if cron.get('interval'):
                return self._crons.every(cron['interval']).minutes.do(self._run_cron, cron)
        elif freq == 'hour':
            if cron.get('at'):
                return self._crons.every().hour.at(cron['at'], cron.get('timezone', 'UTC')).do(self._run_cron, cron)
            if cron.get('interval'):
                return self._crons.every(cron['interval']).hours.do(self._run_cron, cron)
        elif freq == 'day':
            if cron.get('at'):
                return self._crons.every().day.at(cron['at']).do(self._run_cron, cron)
            if cron.get('interval'):
                return self._crons.every(cron['interval']).days.do(self._run_cron, cron)
        self.log.error(f'Unknown schedule frequency: {freq}')
        return None

    def __get_crons(self):
        return self.__db.get_all('crons', {'disabled': False})

    def get_scheduled_run_now_jobs(self):
        jobs = []
        while True:
            try:
                item = self.__run_job_queue.get(block=False)
                jobs.append(item)
            except Empty:
                break
        update = False
        for job in jobs:
            if job.get('request_type') == 'run_job':
                if not self._run_cron(job, job.get('_id')):
                    self.log.error(f'Failed to schedule job {job.get("_id")} {job.get("name")}')
            elif job.get('request_type') == 'job_update':
                update = True
        if update:
            if not self.set_cron_schedule():
                self.log.error('Failed to update cron schedule')
                return False
            self.log.info('Updated cron schedule')
        return True

    def __publish_job(self, cron: Dict, job_id: str = None):
        try:
            now = datetime.now()
            job = {
                '_id': job_id or str(uuid4()),
                'name': cron.get('name', ''),
                'type': cron.get('type'),
                'run': cron.get('run', ''),
                'args': cron.get('args', []),
                'hostInventory': cron.get('hostInventory', {}),
                'extraVars': cron.get('extraVars', {}),
                'state': 'pending',
                'resendAttempt': 0,
                'resent': now.isoformat(),
                'scheduled': now.isoformat(),
                'expiryTime': now + timedelta(days=7),
                'start': None,
                'end': None,
                'result': None,
                'errors': [],
            }
            if bool(thread_local.db.insert_one('jobs', job)):
                del job['expiryTime']
                return thread_local.publisher.send_msg(job['_id'].encode(), job['_id'])
        except Exception:
            self.log.exception(f'[{thread_local.sched_id}] Failed to publish job')
        return False

    def _run_cron(self, cron: Dict, job_id: str = None):
        self.__pool.submit(self.__publish_job, cron, job_id)

    def set_cron_schedule(self):
        self._crons.clear()
        for cron in self.__get_crons():
            cron: Dict
            if not self.__create_cron_job(cron):
                self.log.error(f'Failed to create cron job for {cron.get("name")}')
                return False
        return True

    def __reschedule_job(self, job: Dict, attempt: int = 1):
        self.log.info(f'[{thread_local.sched_id}] Resending job {job.get("_id")} attempt {attempt}')
        job['resendAttempt'] = attempt
        job['resent'] = datetime.now().isoformat()
        if bool(thread_local.db.update_one('jobs', {'_id': job.get('_id')}, {'$set': job})):
            if thread_local.publisher.send_msg(job['_id'].encode(), job['_id']):
                return True
        self.log.error(f'[{thread_local.sched_id}] Failed to reschedule job {job.get("_id")}')
        return False

    def __get_latest_completed_job(self):
        cursor = self.__db.get_all_with_cursor('jobs', {'state': 'completed'})
        if cursor:
            try:
                latest = list(cursor.sort('scheduled', DESCENDING).limit(1))
                if latest:
                    return datetime.fromisoformat(latest[0].get('scheduled'))
            except Exception:
                self.log.exception('Failed to get latest completed job')
        return None

    def reschedule_jobs_check(self):
        pending = self.__db.get_all('jobs', {'state': 'pending'})
        if pending:
            latest = self.__get_latest_completed_job()
            if latest:
                now = datetime.now()
                for job in pending:
                    if datetime.fromisoformat(job.get('scheduled')) < latest:
                        attempt = job.get('resendAttempt', 0) + 1
                        if attempt < 4:
                            if datetime.fromisoformat(job.get('resent')) < now - timedelta(minutes=attempt):
                                self.__pool.submit(self.__reschedule_job, job, attempt)


def main():
    with JobScheduler() as scheduler:
        if not scheduler.set_cron_schedule():
            exit(1)
        cnt = 0
        while not scheduler.stop_trigger.is_set():
            scheduler._crons.run_pending()
            scheduler.get_scheduled_run_now_jobs()
            if cnt == 60:
                scheduler.reschedule_jobs_check()
                cnt = 0
            sleep(1)
            cnt += 1
    exit(0)


if __name__ == "__main__":
    main()
