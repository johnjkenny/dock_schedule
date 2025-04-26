from argparse import REMAINDER

from dock_schedule.arg_parser import ArgParser
from dock_schedule.utils import Utils, Schedule
from dock_schedule.init import Init
from dock_schedule.swarm import Swarm, Services


def parse_parent_args(args: dict):
    if args.get('init'):
        return init(args['init'])
    if args.get('workers'):
        return workers(args['workers'])
    if args.get('services'):
        return services(args['services'])
    if args.get('swarm'):
        return swarm(args['swarm'])
    if args.get('containers'):
        return containers(args['containers'])
    if args.get('jobs'):
        return jobs(args['jobs'])
    return True


def parent():
    args = ArgParser('Dock Schedule Parent Commands', None, {
        'init': {
            'short': 'I',
            'help': 'Initialize dock-schedule environment',
            'nargs': REMAINDER
        },
        'swarm': {
            'short': 'S',
            'help': 'Dock Schedule swarm commands',
            'nargs': REMAINDER
        },
        'workers': {
            'short': 'w',
            'help': 'Dock Schedule worker commands',
            'nargs': REMAINDER
        },
        'services': {
            'short': 's',
            'help': 'Dock Schedule service commands',
            'nargs': REMAINDER
        },
        'containers': {
            'short': 'c',
            'help': 'Dock Schedule container commands',
            'nargs': REMAINDER
        },
        'jobs': {
            'short': 'j',
            'help': 'Dock Schedule job commands',
            'nargs': REMAINDER
        }
    }).set_arguments()
    if not parse_parent_args(args):
        exit(1)
    exit(0)


def parse_init_args(args: dict):
    if args.get('run'):
        return Init(args['force'], args['nonInteractive'])._run()
    return True


def init(parent_args: list = None):
    args = ArgParser('Dock Schedule: Initialization', parent_args, {
        'run': {
            'short': 'r',
            'help': 'Run initialization',
            'action': 'store_true'
        },
        'force': {
            'short': 'F',
            'help': 'Force operations',
            'action': 'store_true'
        },
        'nonInteractive': {
            'short': 'N',
            'help': 'Run in non-interactive mode',
            'action': 'store_true'
        },
    }).set_arguments()
    if not parse_init_args(args):
        exit(1)
    exit(0)


def parse_swarm_args(args: dict):
    if args.get('addNode'):
        if not args.get('name') or not args.get('ip'):
            return Swarm()._display_error('Error: --name (-n) and --ip (-i) are required for swarm node add request')
        return Swarm().add_docker_swarm_node(args['name'], args['ip'])
    if args.get('removeNode'):
        if not args.get('name') or not args.get('ip'):
            return Swarm()._display_error('Error: --name (-n) and --ip (-i) are required for swarm node remove request')
        return Swarm().remove_docker_swarm_node(args['name'], args['ip'])
    if args.get('listNodes'):
        return Swarm().display_swarm_nodes(args['verbose'])
    return True


def swarm(parent_args: list = None):
    args = ArgParser('Dock Schedule: Swarm', parent_args, {
        'addNode': {
            'short': 'a',
            'help': 'Add a node to the dock-schedule swarm',
            'action': 'store_true'
        },
        'removeNode': {
            'short': 'R',
            'help': 'Remove a node from the dock-schedule swarm',
            'action': 'store_true'
        },
        'name': {
            'short': 'n',
            'help': 'Name of the node to add or remove',
        },
        'ip': {
            'short': 'i',
            'help': 'IP address of the node to add or remove',
        },
        'listNodes': {
            'short': 'l',
            'help': 'List all nodes in the dock-schedule swarm',
            'action': 'store_true'
        },
        'verbose': {
            'short': 'v',
            'help': 'Enable verbose output',
            'action': 'store_true'
        }
    }).set_arguments()
    if not parse_swarm_args(args):
        exit(1)
    exit(0)


def parse_workers_args(args: dict):
    if args.get('qty'):
        return Utils().set_workers(args['qty'])
    return True


def workers(parent_args: list = None):
    args = ArgParser('Dock Scheduler: Worker', parent_args, {
        'qty': {
            'short': 'q',
            'help': 'Set the number of workers. This is the number of total workers deployed. Default: 1',
            'default': 1,
            'type': int,
        },
    }).set_arguments()
    if not parse_workers_args(args):
        exit(1)
    exit(0)


def parse_service_args(args: dict):
    if args.get('balance'):
        return Services().rebalance_services()
    if args.get('reload'):
        return Services().reload_services(args['reload'])
    if args.get('start'):
        return Services().start_services(args['start'])
    if args.get('stop'):
        return Services().stop_services(args['stop'])
    if args.get('list'):
        return Services().display_services()
    return True


def services(parent_args: list = None):
    args = ArgParser('Dock Schedule: Services', parent_args, {
        'balance': {
            'short': 'B',
            'help': 'Balance the dock-schedule services among swarm nodes',
            'action': 'store_true'
        },
        'start': {
            'short': 's',
            'help': 'Start the dock-schedule service(s). Specify service name for specific service, else "all" is \
                used. Use comma separated list for multiple services (example: service1,service2)',
            'nargs': '?',
            'const': 'all',
            'default': None
        },
        'stop': {
            'short': 'S',
            'help': 'Stop the dock-schedule service(s). Specify service name for specific service, else "all" is \
                used. Use comma separated list for multiple services (example: service1,service2)',
            'nargs': '?',
            'const': 'all',
            'default': None
        },
        'reload': {
            'short': 'R',
            'help': 'Reload a dock-schedule service (specify service name or ID). Use comma separated list for \
                multiple services (example: service1,service2). Use "all" to reload all services.',
        },
        'list': {
            'short': 'l',
            'help': 'List dock-schedule services and their status',
            'action': 'store_true'
        }
        # ToDO: Add build methods???? Maybe?
    }).set_arguments()
    if not parse_service_args(args):
        exit(1)
    exit(0)


def parse_container_args(args: dict):
    return True


def containers(parent_args: list = None):
    args = ArgParser('Dock Schedule: Containers', parent_args, {
        'get': {
            'short': 'g',
            'help': 'Get dock-schedule service containers and their status',
        },
        'logs': {
            'short': 'l',
            'help': 'Display logs for a dock-schedule service container (specify container name)',
        }
    }).set_arguments()
    if not parse_container_args(args):
        exit(1)
    exit(0)


def parse_job_args(args: dict):
    if args.get('list'):
        return Schedule().display_all_job_schedules()
    if args.get('create'):
        return create_job(args['create'])
    if args.get('delete'):
        return Schedule().delete_cron_job(args['delete'])
    if args.get('update'):
        return update_job(args['update'])
    if args.get('get'):
        return get_job_schedule(args['get'])
    if args.get('run'):
        return run_job(args['run'])
    if args.get('results'):
        return job_results(args['results'])
    return True


def jobs(parent_args: list = None):
    args = ArgParser('Dock Schedule: Jobs', parent_args, {
        'list': {
            'short': 'l',
            'help': 'List dock-schedule job schedule',
            'action': 'store_true'
        },
        'get': {
            'short': 'g',
            'help': 'Get dock-schedule job schedule (specify job name)',
            'nargs': REMAINDER
        },
        'create': {
            'short': 'c',
            'help': 'Create a dock-schedule job cron',
            'nargs': REMAINDER
        },
        'delete': {
            'short': 'D',
            'help': 'Delete a dock-schedule job cron (specify job ID)',
        },
        'update': {
            'short': 'u',
            'help': 'Update a dock-schedule job cron',
            'nargs': REMAINDER
        },
        'run': {
            'short': 'r',
            'help': 'Run a dock-schedule job (specify job name)',
            'nargs': REMAINDER
        },
        'results': {
            'short': 'R',
            'help': 'Get the results of dock-schedule jobs',
            'nargs': REMAINDER,
        }
    }).set_arguments()
    if not parse_job_args(args):
        exit(1)
    exit(0)


def parse_create_job_args(args: dict):
    if args.get('name'):
        return Schedule().create_cron_job(args)
    return True


def create_job(parent_args: list = None):
    args = ArgParser('Dock Schedule: Create Job Cron', parent_args, {
        'name': {
            'short': 'n',
            'help': 'Name of the job to create. Required to create a job cron',
            'required': True,
        },
        'type': {
            'short': 't',
            'help': 'Type of the job to create. Options: python3, ansible, bash, php, node',
            'choices': ['python3', 'ansible', 'bash', 'php', 'node'],
            'required': True,
        },
        'run': {
            'short': 'r',
            'help': 'Name of script or playbook to run for the job. This should be located: \
                /opt/dock-schedule/jobs/<type>/<run> for python3, bash, php, or node type. \
                /opt/dock-schedule/ansible/playbooks/<run> for ansible type',
            'required': True,
        },
        'args': {
            'short': 'a',
            'help': 'Arguments to pass to the python3, bash, php or node script arg parser \
                (example: "--arg1 value1", "--arg2 value2").',
            'nargs': '+'
        },
        'frequency': {
            'short': 'f',
            'help': 'Frequency to run the job. Options: second, minute, hour, day',
            'choices': ['second', 'minute', 'hour', 'day'],
            'required': True,
        },
        'interval': {
            'short': 'i',
            'help': 'Interval to run the job based on the frequency. Must set either interval or at, but not both. \
                "at" will take precedence. Options: \
                second frequency: 1-infinity, \
                minute frequency: 1-infinity, \
                hour frequency: 1-infinity, \
                day frequency: 1-infinity',
            'type': int,
        },
        'at': {
            'short': 'A',
            'help': 'The time to run the job based on the frequency. Must set either interval or at, but not both. \
                "at" will take precedence. Options: \
                minute frequency: ":SS", \
                hour frequency: "MM:SS" or ":MM", \
                day frequency: "HH:MM:SS" or "HH:MM"',
        },
        'timezone': {
            'short': 'T',
            'help': 'Timezone to run the job. Used in junction with "at". Default: UTC',
            'default': 'UTC'
        },
        'hostInventory': {
            'short': 'H',
            'help': 'Host inventory to run remote ansible job on. Requires key=value pairs separated by comma: \
                "hostname1=ip1, hostname2=ip2". Leave empty for the ansible job to run locally on the worker'
        },
        'extraVars': {
            'short': 'e',
            'help': 'Extra vars to pass to the ansible job. Requires key=value pairs separated by comma. \
                "var1=value1, var2=value2". These will be directly used in the ansible playbook'
        },
        'disabled': {
            'short': 'd',
            'help': 'If the job is disabled. This will cause the job to not run until it is enabled. Default: False',
            'action': 'store_true',
        }
    }).set_arguments()
    if not parse_create_job_args(args):
        exit(1)
    exit(0)


def parse_update_job_args(args: dict):
    if args.get('jobID'):
        job_id = args.pop('jobID')
        return Schedule().update_cron_job(job_id, args)
    return True


def update_job(parent_args: list = None):
    args = ArgParser('Dock Schedule: Update Job Cron', parent_args, {
        'jobID': {
            'short': 'j',
            'help': 'Job ID of the job to update. Required to update a job cron',
            'required': True,
        },
        'name': {
            'short': 'n',
            'help': 'New name for the cron job',
            'default': None,
        },
        'type': {
            'short': 't',
            'help': 'Job type update. Options: python3, ansible, bash, php, node',
            'choices': ['python3', 'ansible', 'bash', 'php', 'node', None],
            'default': None,
        },
        'run': {
            'short': 'r',
            'help': 'Job file to run. This should be located: \
                /opt/dock-schedule/jobs/<type>/<run> for python3, bash, php, or node type. \
                /opt/dock-schedule/ansible/playbooks/<run> for ansible type',
            'default': None,
        },
        'args': {
            'short': 'a',
            'help': 'Arguments to pass to the python3, bash, php or node script arg parser \
                (example: "--arg1 value1", "--arg2 value2"). Include all args and not just the updated ones. \
                    Use "NONE" to remove all args.',
            'nargs': '+',
            'default': None
        },
        'frequency': {
            'short': 'f',
            'help': 'Frequency to run the job. Options: second, minute, hour, day',
            'choices': ['second', 'minute', 'hour', 'day', None],
            'default': None,
        },
        'interval': {
            'short': 'i',
            'help': 'Interval to run the job based on the frequency. Must set either interval or at, but not both. \
                "at" will take precedence. Options: \
                second frequency: 1-infinity, \
                minute frequency: 1-infinity, \
                hour frequency: 1-infinity, \
                day frequency: 1-infinity. Use "None" to remove.',
            'default': None,
        },
        'at': {
            'short': 'A',
            'help': 'The time to run the job based on the frequency. Must set either interval or at, but not both. \
                "at" will take precedence. Options: \
                minute frequency: ":SS", \
                hour frequency: "MM:SS" or ":MM", \
                day frequency: "HH:MM:SS" or "HH:MM". Use "None" to remove.',
            'default': None,
        },
        'timezone': {
            'short': 'T',
            'help': 'Timezone to run the job. Used in junction with "at"',
            'default': None
        },
        'hostInventory': {
            'short': 'H',
            'help': 'Host inventory to run remote ansible job on. Requires key=value pairs separated by comma: \
                "hostname1=ip1, hostname2=ip2". Use "None" to remove and use localhost.',
            'default': None
        },
        'extraVars': {
            'short': 'e',
            'help': 'Extra vars to pass to the ansible job. Requires key=value pairs separated by comma. \
                "var1=value1, var2=value2". Include all expected key values and not just the updated ones',
            'default': None
        },
        'state': {
            'short': 's',
            'help': 'State of the cron job. Options: enabled, disabled',
            'choices': ['enabled', 'disabled', None],
            'default': None
        }
    }).set_arguments()
    if not parse_update_job_args(args):
        exit(1)
    exit(0)


def parse_get_job_schedule_args(args: dict):
    if args.get('id'):
        return Schedule().display_job_schedule(job_id=args['id'])
    if args.get('name'):
        return Schedule().display_job_schedule(job_name=args['name'])
    if args.get('type'):
        return Schedule().display_job_schedule(job_type=args['type'])
    if args.get('run'):
        return Schedule().display_job_schedule(job_run=args['run'])
    return True


def get_job_schedule(parent_args: list = None):
    args = ArgParser('Dock Schedule: Get Job Schedule', parent_args, {
        'id': {
            'short': 'i',
            'help': 'Get job schedule by job ID',
        },
        'name': {
            'short': 'n',
            'help': 'Get job schedule by job name',
        },
        'type': {
            'short': 't',
            'help': 'Get job schedule by job type',
            'choices': ['python3', 'ansible', 'bash', 'php', 'node'],
        },
        'run': {
            'short': 'r',
            'help': 'Get job schedule by job file to run. This should be located: \
                /opt/dock-schedule/jobs/<type>/<run> for python3, bash, php, or node type. \
                /opt/dock-schedule/ansible/playbooks/<run> for ansible type',
        }
    }).set_arguments()
    if not parse_get_job_schedule_args(args):
        exit(1)
    exit(0)


def parse_run_job_args(args: dict):
    if args.get('id'):
        return Schedule().run_predefined_job(args['id'], args.get('args'), args.get('hostInventory'),
                                             args.get('extraVars'), args.get('wait'))
    if args.get('run'):
        if not args.get('type'):
            return Schedule()._display_error('Error: --type (-t) is required to run a job')
        return Schedule().run_job(args)
    return True


def run_job(parent_args: list = None):
    args = ArgParser('Dock Schedule: Run Job', parent_args, {
        'id': {
            'short': 'i',
            'help': 'ID of the cron job to run if you want to run a predefined job',
        },
        'name': {
            'short': 'n',
            'help': 'Name to use for the job run. Default: manual-<type>-<run> (example: manual-python3-hello.py)',
            'default': 'GENERATE',
        },
        'type': {
            'short': 't',
            'help': 'Job type to run. Will use predefined if "--id" is used. \
                Options: python3, ansible, bash, php, node',
            'choices': ['python3', 'ansible', 'bash', 'php', 'node'],
        },
        'run': {
            'short': 'r',
            'help': 'Job file to run. Will use predefined if "--id" is used. This should be located: \
                /opt/dock-schedule/jobs/<type>/<run> for python3, bash, php, or node type. \
                /opt/dock-schedule/ansible/playbooks/<run> for ansible type',
        },
        'args': {
            'short': 'a',
            'help': 'Arguments to pass to the python3, bash, php or node script arg parser \
                (example: "--arg1 value1", "--arg2 value2"). Will override predefined if "--id" is used',
            'nargs': '+',
            'default': None
        },
        'hostInventory': {
            'short': 'H',
            'help': 'Host inventory to run remote ansible job on. Requires key=value pairs separated by comma: \
                "hostname1=ip1, hostname2=ip2". Will override predefined if "--id" is used. Use "None" to remove and \
                use worker localhost.',
            'default': None
        },
        'extraVars': {
            'short': 'e',
            'help': 'Extra vars to pass to the ansible job. Requires key=value pairs separated by comma. \
                "var1=value1, var2=value2". Will override predefined if "--id" is used.',
            'default': None
        },
        'wait': {
            'short': 'w',
            'help': 'Wait for the job to finish before returning. Default: False',
            'action': 'store_true',
        }
    }).set_arguments()
    if not parse_run_job_args(args):
        exit(1)
    exit(0)


def parse_job_result_args(args: dict):
    if args['name'] == 'all':
        args['name'] = None
    return Schedule().display_results(args['id'], args['name'], args['filter'], args['limit'], args['verbose'])


def job_results(parent_args: list = None):
    args = ArgParser('Dock Schedule: Run Job', parent_args, {
        'id': {
            'short': 'i',
            'help': 'ID of the job to get results for',
            'default': None
        },
        'name': {
            'short': 'n',
            'help': 'Job name to query. Use "all" to get all jobs.',
            'default': None
        },
        'limit': {
            'short': 'l',
            'help': 'Limit the number of job results to return. Default: 10',
            'type': int,
            'default': 10
        },
        'filter': {
            'short': 'f',
            'help': 'Filter the job results by status. Options: success, failed, scheduled',
            'choices': ['success', 'failed', 'scheduled'],
            'default': None
        },
        'verbose': {
            'short': 'v',
            'help': 'Enable verbose output',
            'action': 'store_true'
        }
    }).set_arguments()
    if not parse_job_result_args(args):
        exit(1)
    exit(0)
