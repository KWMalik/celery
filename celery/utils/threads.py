# -*- coding: utf-8 -*-
"""
    celery.utils.threads
    ~~~~~~~~~~~~~~~~~~~~

    Threading utilities.

"""
from __future__ import absolute_import, print_function

import os
import sys
import threading
import traceback

from kombu.syn import detect_environment

USE_PURE_LOCALS = os.environ.get('USE_PURE_LOCALS')


class bgThread(threading.Thread):

    def __init__(self, name=None, **kwargs):
        super(bgThread, self).__init__()
        self._is_shutdown = threading.Event()
        self._is_stopped = threading.Event()
        self.daemon = True
        self.name = name or self.__class__.__name__

    def body(self):
        raise NotImplementedError('subclass responsibility')

    def on_crash(self, msg, *fmt, **kwargs):
        print(msg.format(*fmt), file=sys.stderr)
        exc_info = sys.exc_info()
        try:
            traceback.print_exception(exc_info[0], exc_info[1], exc_info[2],
                                      None, sys.stderr)
        finally:
            del(exc_info)

    def run(self):
        body = self.body
        shutdown_set = self._is_shutdown.is_set
        try:
            while not shutdown_set():
                try:
                    body()
                except Exception as exc:
                    try:
                        self.on_crash('{0!r} crashed: {1!r}', self.name, exc)
                        self._set_stopped()
                    finally:
                        os._exit(1)  # exiting by normal means won't work
        finally:
            self._set_stopped()

    def _set_stopped(self):
        try:
            self._is_stopped.set()
        except TypeError:  # pragma: no cover
            # we lost the race at interpreter shutdown,
            # so gc collected built-in modules.
            pass

    def stop(self):
        """Graceful shutdown."""
        self._is_shutdown.set()
        self._is_stopped.wait()
        if self.is_alive():
            self.join(1e100)

if detect_environment() == 'default' and not USE_PURE_LOCALS:
    class LocalStack(threading.local):

        def __init__(self):
            self.stack = []
            self.push = self.stack.append
            self.pop = self.stack.pop

        @property
        def top(self):
            try:
                return self.stack[-1]
            except (AttributeError, IndexError):
                return None
else:
    # See #706
    from celery.local import LocalStack  # noqa
