#!/usr/bin/env python3

# import schedule
# from random import choice
import ssl
import logging
from time import sleep, gmtime
from threading import Thread, Event
# from queue import Queue, Empty
# from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from json import dumps

from pika import SelectConnection, BaseConnection, BasicProperties
from pika.adapters.blocking_connection import BlockingChannel
from pika.credentials import PlainCredentials
from pika.channel import Channel
from pika.connection import ConnectionParameters, SSLOptions


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
        cnt = 0
        while not self.__exchange_declared:
            cnt += 1
            if cnt > 50:
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
            context = ssl.create_default_context(cafile='')
            context.load_cert_chain('', '')
            context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
            return SSLOptions(context, 'sg_cluster_broker')
        except Exception:
            self.log.exception('Failed to create SSL context for broker connection')
        return None

    def __create_connection_parameters(self):
        creds: dict = self.__load_credentials()
        if creds:
            # ssl = self.__create_connection_ssl_obj()
            # if ssl:
            try:
                return ConnectionParameters(
                    host='broker',
                    port=5672,
                    virtual_host=creds.get('vhost', '/'),
                    credentials=PlainCredentials(creds.get('user', ''), creds.get('passwd', '')),
                    heartbeat=15,
                    blocked_connection_timeout=20
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
        self.__exchange_declared = True
        self.__reconnecting = False
        self.__conn_blocked = False

    def __reset_connect_state(self):
        self.__client = None
        self.__channel = None
        self.__exchange_declared = False
        self.__queue_declared = False

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

    def send_msg(self, msg: bytes):
        if isinstance(msg, bytes):
            if self.__can_send():
                try:
                    properties = BasicProperties(content_type='application/octet-stream', delivery_mode=2)
                    self.__channel.basic_publish(self.__exchange, self.__route, msg, properties)
                    self.log.info(f'Sent message to queue: {msg}')
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
        self.publisher = JobPublisher(self.log)
        if not self.publisher.start():
            raise Exception('Failed to start job publisher')

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.publisher.stop()


def main():
    payload1 = {'_id': uuid4().hex, 'type': 'python3', 'name': 'test.py', 'args': ['0'], 'inventory': {}}
    payload2 = {'_id': uuid4().hex, 'type': 'python3', 'name': 'test.py', 'args': ['1'], 'inventory': {}}
    payload3 = {'_id': uuid4().hex, 'type': 'bash', 'name': 'test.sh', 'args': ['0'], 'inventory': {}}
    payload4 = {'_id': uuid4().hex, 'type': 'bash', 'name': 'test.sh', 'args': ['1'], 'inventory': {}}
    payload5 = {'_id': uuid4().hex, 'type': 'node', 'name': 'test.js', 'args': ['0'], 'inventory': {}}
    payload6 = {'_id': uuid4().hex, 'type': 'node', 'name': 'test.js', 'args': ['1'], 'inventory': {}}
    payload7 = {'_id': uuid4().hex, 'type': 'php', 'name': 'test.php', 'args': ['0'], 'inventory': {}}
    payload8 = {'_id': uuid4().hex, 'type': 'php', 'name': 'test.php', 'args': ['1'], 'inventory': {}}
    sent = False
    with JobScheduler() as scheduler:
        while not scheduler.stop_trigger.is_set():
            if not sent:
                scheduler.publisher.send_msg(dumps(payload1).encode())
                sleep(2)
                scheduler.publisher.send_msg(dumps(payload2).encode())
                sleep(2)
                scheduler.publisher.send_msg(dumps(payload3).encode())
                sleep(2)
                scheduler.publisher.send_msg(dumps(payload4).encode())
                sleep(2)
                scheduler.publisher.send_msg(dumps(payload5).encode())
                sleep(2)
                scheduler.publisher.send_msg(dumps(payload6).encode())
                sleep(2)
                scheduler.publisher.send_msg(dumps(payload7).encode())
                sleep(2)
                scheduler.publisher.send_msg(dumps(payload8).encode())
                sent = True
            sleep(1)


if __name__ == "__main__":
    main()


'''
test case
create a series of different jobs that the workers can run
send the jobs to workers based on a cron schedule

Job Request example:
{
    "_id": "job_id",
    "inventory": {},  # or leave empty for localhost
    "type": "python3",  # what runs the job- python3, ansible, bash, php, javascript, etc.
    "name": "job_name",
    "args": [],
    "extra_vars": {}  # extra vars for ansible jobs
}


inventory = [
    {
        'name': 'node1',
        'ip': 'ip'
    }
]


jobs are listed by type:
    - python3
    - ansible
    - bash
    - php
    - javascript
'''
