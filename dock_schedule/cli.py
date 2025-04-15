from argparse import REMAINDER

from dock_schedule.arg_parser import ArgParser
from dock_schedule.utils import Init


def parse_parent_args(args: dict):
    if args.get('init'):
        return init(args['init'])
    return True


def parent():
    args = ArgParser('Pkg Commands', None, {
        'init': {
            'short': 'I',
            'help': 'Initialize dock-schedule environment',
            'nargs': REMAINDER
        }
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
