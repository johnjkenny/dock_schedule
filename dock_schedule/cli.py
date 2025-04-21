from argparse import REMAINDER

from dock_schedule.arg_parser import ArgParser
from dock_schedule.utils import Init, Utils


def parse_parent_args(args: dict):
    if args.get('init'):
        return init(args['init'])
    if args.get('addNode'):
        return add_node(args['addNode'])
    if args.get('removeNode'):
        return remove_node(args['removeNode'])
    return True


def parent():
    args = ArgParser('Dock Schedule Commands', None, {
        'init': {
            'short': 'I',
            'help': 'Initialize dock-schedule environment',
            'nargs': REMAINDER
        },
        'addNode': {
            'short': 'a',
            'help': 'Add a node to the dock-schedule swarm',
            'nargs': REMAINDER
        },
        'removeNode': {
            'short': 'R',
            'help': 'Remove a node from the dock-schedule swarm',
            'nargs': REMAINDER
        },
    }).set_arguments()
    if not parse_parent_args(args):
        exit(1)
    exit(0)


def parse_init_args(args: dict):
    if args.get('run'):
        return Init(args['force'])._run()
    return True


def init(parent_args: list = None):
    args = ArgParser('Dock Schedule Initialization', parent_args, {
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
    }).set_arguments()
    if not parse_init_args(args):
        exit(1)
    exit(0)


def parse_add_node_args(args: dict):
    if args.get('name') and args.get('ip'):
        return Utils().add_docker_swarm_node(args['name'], args['ip'])
    return True


def add_node(parent_args: list = None):
    args = ArgParser('Dock Schedule Add Node', parent_args, {
        'name': {
            'short': 'n',
            'help': 'Name of the node',
            'required': True
        },
        'ip': {
            'short': 'i',
            'help': 'IP address of the node',
            'required': True
        },
    }).set_arguments()
    if not parse_add_node_args(args):
        exit(1)
    exit(0)


def parse_remove_node_args(args: dict):
    if args.get('name') and args.get('ip'):
        return Utils().remove_docker_swarm_node(args['name'], args['ip'])
    return True


def remove_node(parent_args: list = None):
    args = ArgParser('Dock Schedule Remove Node', parent_args, {
        'name': {
            'short': 'n',
            'help': 'Name of the node',
            'required': True
        },
        'ip': {
            'short': 'i',
            'help': 'IP address of the node',
            'required': True
        },
    }).set_arguments()
    if not parse_remove_node_args(args):
        exit(1)
    exit(0)
