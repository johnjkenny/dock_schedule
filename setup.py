from setuptools import setup


try:
    setup(
        name='pkg-name',
        version='1.0.0',
        entry_points={'console_scripts': [
            'pkg-name = pkg_name.cli:pkg_parent',
        ]},
    )
    exit(0)
except Exception as error:
    print(f'Failed to setup package: {error}')
    exit(1)
