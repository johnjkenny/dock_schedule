
from pkg_name.logger import get_logger


class MyPkg():
    def __init__(self):
        self.log = get_logger('my-pkg')
