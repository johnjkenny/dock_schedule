import json
from pathlib import Path
from logging import Logger
from typing import Dict, List
from uuid import uuid4
from datetime import datetime, timedelta
from time import sleep

from pymongo import DESCENDING
from pytz import all_timezones_set

from dock_schedule.color import Color
from dock_schedule.utils import Utils, Mongo


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


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
            if job.get('at'):
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

    def __parse_ansible_job_data(self, job: Dict) -> bool:
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

    def __wait_for_job_completion(self, job_id: str, max_wait: int = 1800) -> bool:
        try:
            scheduled = False
            while max_wait > 0:
                if not scheduled:
                    state = self.__db.get_one('scheduledJob', {'_id': job_id}, {'state': 1})
                    if state and state.get('state') == 'done':
                        scheduled = True
                if scheduled:
                    result = self.__db.get_one('jobs', {'_id': job_id}, {'result': 1, 'error': 1})
                    if result and result.get('result') is not None:
                        if result['result'] is True:
                            self.log.info('Job completed successfully')
                            return True
                        else:
                            self.log.error(f'Job failed: {result.get("error")}')
                            return False
                sleep(5)
                max_wait -= 5
            self.log.error('Failed to wait for job completion in allotted time')
        except KeyboardInterrupt:
            self.log.info('Waiting for job completion interrupted')
            return False
        except Exception:
            self.log.exception('Failed to wait for job completion')
            return False

    def run_predefined_job(self, job_id: str, args: List[str] = None, host_inventory: Dict = None,
                           extra_vars: Dict = None, wait: bool = False) -> bool:
        job = self.get_job_by_id(job_id)
        if job:
            if job.get('type') == 'ansible':
                if host_inventory:
                    job['hostInventory'] = host_inventory if host_inventory != 'None' else None
                if extra_vars:
                    job['extraVars'] = extra_vars if extra_vars != 'None' else None
                if not self.__parse_ansible_job_data(job):
                    return False
            else:
                if args:
                    job['args'] = args
            return self.__create_manual_job(job, wait)
        return False

    def __create_manual_job(self, job: Dict, wait: bool = False) -> bool:
        job['_id'] = str(uuid4())
        job['expiryTime'] = datetime.now() + timedelta(hours=1)
        job['state'] = 'pending'
        if self.__db.insert_one('scheduledJob', job):
            if wait:
                self.log.info(f'Job {job.get("name")} sent to scheduler successfully. Waiting for completion...')
                return self.__wait_for_job_completion(job['_id'])
            self.log.info(f'Job {job.get("name")} sent to scheduler successfully')
            return True
        else:
            self.log.error(f'Failed to send job {job.get("name")} to scheduler')
        return False

    def run_job(self, job: Dict):
        if job.get('name', '') == 'GENERATE':
            job['name'] = f'manual-{job.get("type")}-{job.get("run")}'
        if self.__check_job_run_file_exists(job.get('type'), job.get('run')):
            if job.get('type') == 'ansible':
                if not self.__parse_ansible_job_data(job):
                    return False
            return self.__create_manual_job(job, job.get('wait', False))
        return False

    def get_jobs_by_filter(self, _filter: Dict, limit: int = 10) -> List[Dict] | None:
        if not _filter:
            cursor = self.__db.get_all_with_cursor('jobs')
        else:
            cursor = self.__db.get_all_with_cursor('jobs', _filter)
        if cursor:
            return list(cursor.sort('scheduled', DESCENDING).limit(limit))
        return []

    def __determine_result_color(self, result: bool) -> str:
        if result is True:
            return 'green'
        elif result is False:
            return 'red'
        return 'yellow'

    def __convert_timedelta_to_units(self, delta: timedelta):
        """Convert timedelta to time units. If days > 0, return days and hours:minutes:seconds unless days > 365 which
        {days // 365} year(s) {days % 365} day(s) and {hours}:{minutes} is returned. If hours > 0, return
        hours and minutes:seconds. If minutes > 0, return minutes and seconds. If seconds > 0, return seconds. If
        milliseconds > 0, return milliseconds. Else return microseconds

        Args:
            delta (timedelta): datetime.timedelta object to convert to time units

        Returns:
            str: time units or empty string if failed
        """
        try:
            days = delta.days
            hours = delta.seconds // 3600
            minutes = (delta.seconds // 60) % 60
            seconds = delta.seconds % 60
            milliseconds = delta.microseconds // 1000
            microseconds = delta.microseconds % 1000
            if days > 0:
                if days >= 365:
                    return f"{days // 365} year(s) {days % 365} day(s) and {hours}:{minutes}"
                return f"{days} day(s) and {hours}:{minutes:02}:{seconds:02}"
            if hours > 0:
                return f"{hours} hour(s) and {minutes:02}:{seconds:02}"
            if minutes > 0:
                return f"{minutes} minute(s) and {seconds:02}.{milliseconds:03} seconds"
            if seconds > 0:
                return f"{seconds:02}.{milliseconds:03} seconds"
            if milliseconds > 0:
                return f"{milliseconds} ms"
            if microseconds > 0:
                return f"{microseconds} µs"
            return f"{(microseconds * 1000) % 1000} ns"
        except Exception:
            self.log.exception("Failed to convert timedelta to units")
        return str(delta)

    def __determine_result_filter(self, _filter: str, _filters: Dict) -> Dict:
        if _filter == 'success':
            _filters['result'] = True
        elif _filter == 'failed':
            _filters['result'] = False
        elif _filter == 'scheduled':
            _filters['state'] = 'pending'
        else:
            self.log.error(f'Invalid filter: {_filter}')

    def display_results(self, job_id: str = None, job_name: str = None, _filter: str = None, limit: int = 10,
                        verbose: bool = False) -> bool:
        if job_id:
            results = self.get_jobs_by_filter({'_id': job_id}, 1)
        else:
            _filters = {}
            if job_name:
                _filters['name'] = job_name
            if _filter:
                self.__determine_result_filter(_filter, _filters)
            results = self.get_jobs_by_filter(_filters, limit)
        if verbose:
            return self._display_info(f'Job Results:\n{json.dumps(results, indent=2, cls=DateTimeEncoder)}')
        for r in results:
            color = self.__determine_result_color(r.get('result'))
            error = r.get('error', 'N/A') if color == 'red' else ''
            msg = f'ID: {r.get('_id')}, Name: {r.get("name")}, State: {r.get("state")}, Result: {r.get("result")}, '
            if r.get('end'):
                msg += f'Duration: {self.__convert_timedelta_to_units(r.get("end") - r.get("start"))}'
            else:
                msg += 'Duration: N/A'
            if error:
                msg += f'\n  Error: {error}'
            Color().print_message(msg + '\n', color)
