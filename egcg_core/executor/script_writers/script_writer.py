from os.path import join
from egcg_core.app_logging import AppLogger
from egcg_core.exceptions import EGCGError


class ScriptWriter(AppLogger):
    """
    Writes a basic job submission script. Subclassed by PBSWriter. Initialises with self.lines as an empty
    list, which is appended by self.write_line. This list is then saved line by line to self.script_file by
    self.save.
    """
    suffix = '.sh'
    array_index = 'JOB_INDEX'

    def __init__(self, job_name, working_dir, job_queue, log_commands=True):
        """
        :param str job_name: Desired full path to the pbs script to write
        """
        self.job_name = job_name
        self.script_name = join(working_dir, job_name + self.suffix)
        self.log_commands = log_commands
        self.working_dir = working_dir
        self.log_file = join(self.working_dir, job_name + '.log')
        self.queue = job_queue
        self.info('Writing: ' + self.script_name)
        self.info('Log file: ' + self.log_file)
        self.lines = []
        self.array_jobs_written = 0

    def register_cmd(self, cmd, log_file=None):
        if log_file:
            cmd += ' > %s 2>&1' % log_file
        self.add_line(cmd)

    def register_cmds(self, *cmds, parallel=False):
        if parallel:
            self.add_job_array(*cmds)
        else:
            self.lines.extend(list(cmds))

    def add_job_array(self, *cmds):
        if self.array_jobs_written != 0:
            raise EGCGError('Already written a job array - can only have one per script')

        if len(cmds) == 1:
            self.register_cmd(cmds[0])
        else:
            self._start_array()
            for idx, cmd in enumerate(cmds):
                self._register_array_cmd(
                    idx + 1,
                    cmd,
                    log_file=self.log_file + str(idx + 1) if self.log_commands else None
                )
            self._finish_array()

        self.array_jobs_written += len(cmds)

    def _register_array_cmd(self, idx, cmd, log_file=None):
        """
        :param int idx: The index of the job, i.e. which number the job has in the array
        :param str cmd: The command to write
        """
        line = str(idx) + ') ' + cmd
        if log_file:
            line += ' > ' + log_file + ' 2>&1'
        line += '\n' + ';;'
        self.add_line(line)

    def add_line(self, line):
        self.lines.append(line)

    def _start_array(self):
        self.add_line('case $%s in' % self.array_index)

    def _finish_array(self):
        self.add_line('*) echo "Unexpected %s: $%s"' % (self.array_index, self.array_index))
        self.add_line('esac')

    def line_break(self):
        self.lines.append('')

    def save(self):
        """Save self.lines to self.script_file. Also closes it. Always close the file."""
        with open(self.script_name, 'w') as f:
            for line in self.lines:
                f.write(line + '\n')

    @staticmethod
    def _trim_field(field, max_length):
        """
        Required for, e.g, name fields which break PBS if longer than 15 chars
        :return: field, trimmed to max_length
        """
        if len(field) > max_length:
            return field[0:max_length]
        else:
            return field


class ClusterWriter(ScriptWriter):
    header = (
        '#!/bin/bash\n\n'
        '# job name: {job_name}\n'
        '# cpus: {cpus}\n'
        '# mem: {mem}gb\n'
        '# queue: {queue}\n'
        '# log file: {log_file}'
    )
    walltime_header = '# walltime: {walltime}'
    array_header = '# job array: 1-{jobs}'

    def __init__(self, job_name, working_dir, job_queue, log_commands=True, **cluster_config):
        super().__init__(job_name, working_dir, job_queue, log_commands)
        self.cluster_config = cluster_config

    def write_header(self):
        """Write a header for a given resource manager. If multiple jobs, split them into a job array."""
        h = self.header.format(job_name=self.job_name, cpus=self.cluster_config['cpus'],
                               mem=self.cluster_config['mem'], queue=self.queue, log_file=self.log_file)
        header_lines = [h]

        if self.cluster_config['walltime']:
            header_lines.append(self.walltime_header.format(walltime=self.cluster_config['walltime']))

        if self.array_jobs_written > 1:
            header_lines.append(self.array_header.format(jobs=str(self.array_jobs_written)))

        header_lines.extend(['', 'cd ' + self.working_dir, ''])
        self.lines = header_lines + self.lines  # prepend the header
