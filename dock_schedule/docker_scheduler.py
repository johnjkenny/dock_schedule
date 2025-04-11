
from dock_schedule.logger import get_logger


class DockSched():
    def __init__(self):
        self.log = get_logger('docker-scheduler')
