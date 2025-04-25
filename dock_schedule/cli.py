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
    if args.get('schedule'):
        return Schedule().display_job_schedule()
    if args.get('create'):
        return create_job(args['create'])
    return True


def jobs(parent_args: list = None):
    args = ArgParser('Dock Schedule: Jobs', parent_args, {
        'schedule': {
            'short': 's',
            'help': 'Get dock-schedule job schedule',
            'action': 'store_true'
        },
        'create': {
            'short': 'c',
            'help': 'Create a dock-schedule job schedule',
            'nargs': REMAINDER
        },
        'delete': {
            'short': 'D',
            'help': 'Delete a dock-schedule job schedule',
        },
        'update': {
            'short': 'u',
            'help': 'Update a dock-schedule job schedule',
        },
        'run': {
            'short': 'r',
            'help': 'Run a dock-schedule job (specify job name)',
        },
        'args': {
            'short': 'a',
            'help': 'Get dock-schedule job arguments',
            'nargs': '+'
        },
    }).set_arguments()
    if not parse_job_args(args):
        exit(1)
    exit(0)


def parse_create_job_args(args: dict):
    if args.get('name'):
        return Schedule().create_job_cron(args)
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
        },
        'run': {
            'short': 'r',
            'help': 'Name of script or playbook to run for the job. This should be located: \
                /opt/dock-schedule/jobs/<type>/<run> for python3, bash, php, or node type. \
                /opt/dock-schedule/ansible/playbooks/<run> for ansible type',
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
            'help': 'Host inventory to run remote ansible job on. Requires key=value pairs: \
                "name=hostname, ip=ipaddress". Leave empty for the ansible job to run locally on the worker'
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
    if not parse_job_args(args):
        exit(1)
    exit(0)


'''
{
    "name": "job_name",
    "script_type": "python3",  # what runs the job- python3, ansible, bash, php, javascript, etc.
    "script_name": "job_name.py",  # the name of the script to run
    "script_args": [],  # arguments to pass to the script
    "frequency": "minute",  # second, minute, hour, day
    "at": "00:00",  # time to run the job
    "interval": 1,  # interval to run the job
    "timezone": "UTC",  # timezone to run the job
    "inventory": {}  # or leave empty for localhost
    "extra_vars": {},  # extra vars for ansible jobs
    'active': True  # if the job is active or not
}
'''
