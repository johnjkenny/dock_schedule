from setuptools import setup


try:
    setup(
        name='dock-schedule',
        version='1.0.0',
        entry_points={'console_scripts': [
            'dschedule = dock_sched.cli:parent',
        ]},
    )
    exit(0)
except Exception as error:
    print(f'Failed to setup package: {error}')
    exit(1)
