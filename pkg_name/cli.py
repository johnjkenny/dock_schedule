from argparse import REMAINDER

from pkg_name.arg_parser import ArgParser


def parse_parent_args(args: dict):
    if args.get('placeholder'):
        return pkg_placeholder(args['placeholder'])
    return True


def pkg_parent():
    args = ArgParser('Pkg Commands', None, {
        'placeholder': {
            'short': 'p',
            'help': 'placeholder',
            'nargs': REMAINDER
        }
    }).set_arguments()
    if not parse_parent_args(args):
        exit(1)
    exit(0)


def parse_placeholder_args(args: dict):
    return True


def pkg_placeholder(parent_args: list = None):
    args = ArgParser('Pkg Placeholder', parent_args, {
    }).set_arguments()
    if not parse_placeholder_args(args):
        exit(1)
    exit(0)
