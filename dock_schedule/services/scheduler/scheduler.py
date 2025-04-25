#!/usr/bin/env python3

import ssl
import logging
from time import sleep, gmtime
from threading import Thread, Event
from uuid import uuid4
from json import dumps, loads
from typing import Dict
from urllib.parse import quote_plus
from datetime import datetime, timedelta

import schedule
from pika import SelectConnection, BaseConnection, BasicProperties
from pika.adapters.blocking_connection import BlockingChannel
from pika.credentials import PlainCredentials
from pika.channel import Channel
from pika.connection import ConnectionParameters, SSLOptions
from pika.spec import Basic
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure


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
    def __init__(self, logger: logging.Logger = None):
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
                        tlsCAFile='/app/ca.crt',
                        tlsCertificateKeyFile='/app/host.pem',
                    )
                except ConnectionFailure:
                    self.log.exception('Failed to connect to MongoDB')
                except Exception:
                    self.log.exception('Failed to create MongoDB client')
        return self.__client

    def __load_creds(self):
        for key in self.__creds.keys():
            try:
                with open(f'/run/secrets/mongo_{key}', 'r') as f:
                    self.__creds[key] = f.read().strip()
            except Exception:
                self.log.exception(f'Failed to load mongodb credentials for {key}')
                return False
        return True

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


class JobPublisher():
    def __init__(self, logger: logging.Logger = None):
        self.log = logger or get_logger()
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
            self.log.error('Broker connection channel is closed')
        else:
            self.log.error('Broker connection is closed')
        return False

    def __wait_for_channel_open(self):
        cnt = 0
        if self.__channel is not None:
            while not self.__channel.is_open:
                cnt += 1
                if cnt > 100:
                    self.log.error('Failed to open channel')
                    return False
                sleep(.2)
            self.log.debug('Channel is open')
            return True
        self.log.error('Channel does not exist')
        return False

    def __wait_for_exchange_declare(self):
        while not self.__exchange_declared:
            if self.__connect_attempt == self.__max_connect_attempts:
                self.log.error('Failed to declare exchange')
                return False
            sleep(.2)
        self.log.debug('Exchange declared')
        return True

    def __wait_for_conn_unblock(self, timeout: int = 180):
        self.__conn_blocked = True
        cnt = 0
        while self.__conn_blocked:
            sleep(1)
            cnt += 1
            if cnt > timeout:
                self.log.error('Timeout waiting for connection unblock')
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
                self.log.exception(f'Failed to load broker credentials for {key}')
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
            self.log.exception('Failed to create SSL context for broker connection')
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
                    self.log.exception('Failed to create connection parameters')
        return None

    def __reconnect_attempt(self):
        self.__reconnecting = True
        if self.__connect_attempt < self.__max_connect_attempts:
            if self.__connect_attempt != 0:
                sleep(5)
            self.__connect_attempt += 1
            self.log.info(f'Reconnecting to broker {self.__connect_attempt}/{self.__max_connect_attempts - 1}')
            return self._restart_io_loop_in_thread()
        return False

    def __connect(self, on_connect: callable = None, on_failed: callable = None, on_closed: callable = None):
        self.log.info('Connecting to message broker')
        params = self.__create_connection_parameters()
        if params:
            try:
                return SelectConnection(params, on_connect, on_failed, on_closed)
            except Exception:
                self.log.exception('Failed to create connection to broker')
        return None

    def __connect_success(self, connection: BaseConnection):
        self.log.info('Successfully connected to broker')
        self.__connect_attempt = 0
        connection.channel(on_open_callback=self.__open_channel)

    def __connect_failed(self, *args: tuple):
        self.log.error(f'Failed to create connection to broker: {args[1]}')
        return self.__reconnect_attempt()

    def __connect_closed(self, *args: tuple):
        self.log.error(f'Connection closed: {args[1]}')
        return self.__reconnect_attempt()

    def __open_channel(self, channel: Channel):
        self.log.info('Successfully opened channel and set exchange')
        self.__channel = channel
        self.__channel.exchange_declare(self.__exchange, 'direct')
        self.__channel.add_on_return_callback(self.__returned_to_sender_handler)
        self.__exchange_declared = True
        self.__reconnecting = False
        self.__conn_blocked = False

    def __reset_connect_state(self):
        self.__client = None
        self.__channel = None
        self.__exchange_declared = False
        self.__queue_declared = False

    def __returned_to_sender_handler(self, ch: Channel, _: Basic.Deliver, properties: BasicProperties, body: bytes):
        try:
            job_id = loads(body.decode()).get('_id')
            self.log.error(f'Message returned for job ID {job_id}. Resending to queue...')
            sleep(1)
            ch.basic_publish(
                exchange=self.__exchange,
                routing_key=self.__route,
                body=body,
                properties=properties,
                mandatory=True
            )
        except Exception:
            self.log.error('Failed to resend message to queue')

    def __start_io_loop(self) -> bool:
        self.__client = self.__connect(self.__connect_success, self.__connect_failed, self.__connect_closed)
        if self.__client is not None:
            try:
                self.__client.add_on_connection_blocked_callback(self.__wait_for_conn_unblock)
                self.__client.add_on_connection_unblocked_callback(self.__conn_unblocked)
                self.__client.ioloop.start()
                return True
            except Exception:
                self.log.exception('Exception occurred in IO loop')
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
            self.log.exception('Exception occurred while stopping IO-loop')
            return False

    def __stop_thread(self):
        if self.__thread:
            try:
                if self.__thread.is_alive():
                    self.__thread.join(3)
                    if self.__thread.is_alive():
                        self.log.error('Failed to stop broker thread')
                        return False
                    self.__thread = None
                    self.log.info('Successfully stopped broker thread')
                return True
            except Exception:
                self.log.exception('Exception occurred while stopping broker thread')
        self.log.debug('Broker thread does not exist to stop')
        return True

    def _wait_for_reconnect(self, timeout: int = 1800):
        cnt = 0
        while self.__reconnecting:
            self.log.info('Waiting for reconnection...')
            sleep(1)
            cnt += 1
            if cnt > timeout:
                self.log.error('Timeout waiting for reconnection')
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
        self.log.error('Failed to restart broker connection')
        return False

    def __configure_queue(self):
        if not self.__queue_declared:
            try:
                self.__channel.queue_declare(self.__route, durable=True)
                self.__queue_declared = True
                self.log.info('Successfully declared queue')
            except Exception:
                self.log.exception('Failed to declare queue')
                return False
        return True

    def __handle_blocked_connection(self):
        self.log.info('Connection blocked, waiting for unblock from server...')
        while self.__conn_blocked:
            sleep(.5)
        self.log.info('Connection unblocked, resuming operations...')

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
                    properties = BasicProperties(content_type='application/octet-stream', delivery_mode=2)
                    self.__channel.basic_publish(self.__exchange, self.__route, msg, properties)
                    self.log.info(f'Sent job to queue: {job_id[:8]}')
                    return True
                except Exception:
                    self.log.exception('Failed to send message to queue')
            else:
                self.log.error('Failed to send message to queue')
        else:
            self.log.error(f'Invalid message type: {type(msg)}')
        return False

    def start(self):
        if self.__thread:
            self.log.error('Broker already running')
            return False
        self.log.info('Starting broker')
        try:
            self.__thread = Thread(target=self.__start_io_loop, daemon=True)
            self.__thread.start()
            if self.__wait_for_exchange_declare():
                return True
            self.log.error('Failed to start broker')
            return False
        except Exception:
            self.log.exception('Failed to start broker')
        return False

    def stop(self):
        self.log.info('Stopping broker')
        if self.__stop_io_loop():
            return self.__stop_thread()
        self.log.error('Failed to stop broker')
        return False


class JobScheduler():
    def __init__(self):
        self.log = get_logger()
        self.stop_trigger = Event()
        self.__publisher = JobPublisher(self.log)
        self.__db = Mongo(self.log)
        self._crons = schedule
        if not self.__publisher.start():
            raise Exception('Failed to start job publisher')

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.__publisher.stop()

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

    def get_cron_update_state(self):
        state: dict = self.__db.get_one('cronUpdate', {'_id': 1})
        if state:
            if state.get('update', False):
                if not self.__db.update_one('cronUpdate', {'_id': 1}, {'$set': {'update': False}}):
                    self.log.error('Failed to update cron update state')
                    return False
                return True
        else:
            self.log.error('Failed to get cron update state')
        return False

    def _run_cron(self, cron: Dict):
        try:
            job_id = str(uuid4())
            job = {
                '_id': job_id,
                'name': cron.get('name', ''),
                'type': cron.get('type'),
                'run': cron.get('run', ''),
                'args': cron.get('args', []),
                'hostInventory': cron.get('hostInventory', {}),
                'extraVars': cron.get('extraVars', {}),
                'state': 'pending',
                'result': None,
                'error': None,
            }
            self.__publisher.send_msg(dumps(job).encode(), job_id)
            job['expiryTime'] = datetime.now() + timedelta(days=7)
        except Exception:
            self.log.exception('Failed to send job to broker')
            return False
        return bool(self.__db.insert_one('jobs', job))

    def set_cron_schedule(self):
        self._crons.clear()
        for cron in self.__get_crons():
            cron: Dict
            if not self.__create_cron_job(cron):
                self.log.error(f'Failed to create cron job for {cron.get("name")}')
                return False
        return True


def main():
    with JobScheduler() as scheduler:
        if not scheduler.set_cron_schedule():
            exit(1)
        cnt = 0
        while not scheduler.stop_trigger.is_set():
            scheduler._crons.run_pending()
            if cnt == 60:
                if scheduler.get_cron_update_state():
                    if scheduler.set_cron_schedule():
                        scheduler.log.info('Updated cron schedule')
                    else:
                        scheduler.log.error('Failed to update cron schedule')
                        exit(1)
                cnt = 0
            sleep(1)
            cnt += 1
    exit(0)


if __name__ == "__main__":
    main()


'''
inventory = [
    {
        'name': 'node1',
        'ip': 'ip'
    }
]
'''
