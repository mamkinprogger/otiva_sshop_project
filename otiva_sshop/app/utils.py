from typing import Callable

from django.db import close_old_connections, connections


class SideDBWorker:
    def __init__(self, func: Callable, *args, **kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def thread(self):
        """Checks and closes old connections in a separate thread"""
        close_old_connections()
        try:
            return self.func(*self.args, **self.kwargs)
        finally:
            # return connection in main pool
            connections.close_all()
