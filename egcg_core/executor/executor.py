import subprocess
import os.path
import shlex
from egcg_core.app_logging import AppLogger
from egcg_core.exceptions import EGCGError


class Executor(AppLogger):
    def __init__(self, cmd):
        self.cmd = cmd
        self._validate_file_paths()
        self.proc = None

    def join(self):
        """
        Set self.proc to a Popen and start.
        :rtype: tuple[bytes, bytes]
        :raises: EGCGError on any exception
        """
        try:
            out, err = self._process().communicate()
            for stream, emit in ((out, self.info), (err, self.error)):
                for line in stream.decode('utf-8').split('\n'):
                    emit(line)
            return self.proc.poll()

        except Exception as e:
            raise EGCGError('Command failed: ' + self.cmd) from e

    def start(self):
        raise NotImplementedError

    def _process(self):
        """
        Translate self.cmd to a subprocess. Override to manipulate how the process is run, e.g. with different
        resource managers.
        :rtype: subprocess.Popen
        """
        self.info('Executing: ' + self.cmd)
        # TODO: explore how to run commands with Bash constructs , e.g. 'command <(sub command)'
        self.proc = subprocess.Popen(shlex.split(self.cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return self.proc

    def _validate_file_paths(self):
        for arg in self.cmd.split(' '):
            if arg.startswith('/') and not os.path.exists(arg):
                self.debug('Could not find file: ' + arg + '. Will the executed command create it?')
