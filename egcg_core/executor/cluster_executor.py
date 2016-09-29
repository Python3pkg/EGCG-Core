import subprocess
from time import sleep
from egcg_core.exceptions import EGCGError
from egcg_core.app_logging import AppLogger
from egcg_core.config import cfg
from . import script_writers


class ClusterExecutor(AppLogger):
    script_writer = script_writers.ClusterWriter
    finished_statuses = None
    unfinished_statuses = None

    def __init__(self, *cmds, prelim_cmds=None, **cluster_config):
        """
        :param list cmds: Full path to a job submission script
        """
        self.job_queue = cfg['executor']['job_queue']
        self.interval = cfg.query('executor', 'join_interval', ret_default=30)
        self.writer = self._get_writer(**cluster_config)
        self.job_id = None
        self.cmds = cmds
        self.prelim_cmds = prelim_cmds
        self.submit_cmd = cfg['executor']['qsub'] + ' ' + self.writer.script_name

    def write_script(self):
        if self.prelim_cmds:
            self.writer.register_cmds(*self.prelim_cmds)

        pre_job_source = cfg.query('executor', 'pre_job_source')
        if pre_job_source:
            self.writer.register_cmd('source ' + pre_job_source)

        self.writer.line_break()
        self.writer.register_cmds(*self.cmds)
        self.writer.add_header()
        self.writer.save()

    def start(self):
        """Write the jobs into a script, submit it and capture qsub's output as self.job_id."""
        self.write_script()
        self.job_id = self._submit_job()
        self.info('Submitted "%s" as job %s' % (self.submit_cmd, self.job_id))

    def join(self):
        """Wait until the job has finished, then return its exit status."""
        sleep(10)
        while not self._job_finished():
            sleep(self.interval)
        return self._job_exit_code()

    def _get_writer(self, job_name, working_dir, walltime=None, cpus=1, mem=2, log_commands=True):
        return self.script_writer(job_name, working_dir, self.job_queue, log_commands=log_commands, cpus=cpus, mem=mem, walltime=walltime)

    def _job_status(self):
        raise NotImplementedError

    def _job_exit_code(self):
        raise NotImplementedError

    def _submit_job(self):
        p = self._get_stdout(self.submit_cmd)
        if p is None:
            raise EGCGError('Job submission failed')
        return p

    def _job_finished(self):
        status = self._job_status()
        if status in self.unfinished_statuses:
            return False
        elif status in self.finished_statuses:
            return True
        self.debug('Bad job status: %s', status)

    def _get_stdout(self, cmd):
        p = subprocess.Popen(cmd.split(' '), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        exit_status = p.wait()
        o, e = p.stdout.read(), p.stderr.read()
        self.debug('%s -> (%s, %s, %s)', cmd, exit_status, o, e)
        if exit_status:
            return None
        else:
            return o.decode('utf-8').strip()


class PBSExecutor(ClusterExecutor):
    unfinished_statuses = 'BEHQRSTUW'
    finished_statuses = 'FXM'
    script_writer = script_writers.PBSWriter

    def _qstat(self):
        h1, h2, data = self._get_stdout('qstat -x {j}'.format(j=self.job_id)).split('\n')
        return data.split()

    def _job_status(self):
        job_id, job_name, user, time, status, queue = self._qstat()
        return status

    def _job_exit_code(self):
        return self.finished_statuses.index(self._job_status())


class SlurmExecutor(ClusterExecutor):
    unfinished_statuses = ('RUNNING', 'RESIZING', 'SUSPENDED', 'PENDING')
    finished_statuses = ('COMPLETED', 'CANCELLED', 'FAILED', 'TIMEOUT', 'NODE_FAIL')
    script_writer = script_writers.SlurmWriter

    def _submit_job(self):
        # sbatch stdout: "Submitted batch job {job_id}"
        return super()._submit_job().split()[-1].strip()

    def _sacct(self, output_format):
        return self._get_stdout('sacct -n -j {j} -o {o}'.format(j=self.job_id, o=output_format))

    def _squeue(self):
        s = self._get_stdout('squeue -j {j} -o %T'.format(j=self.job_id))
        if not s or len(s.split('\n')) < 2:
            return None
        return sorted(set(s.split('\n')[1:]))

    def _job_status(self):
        state = self._squeue()
        if not state:
            state = self._sacct('State')
        return state

    def _job_exit_code(self):
        state, exit_code = self._sacct('State,ExitCode').split()
        if state == 'CANCELLED':  # cancelled jobs can still be exit status 0
            return 9
        return int(exit_code.split(':')[0])
