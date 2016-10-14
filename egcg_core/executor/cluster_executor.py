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

    def _job_statuses(self):
        raise NotImplementedError

    def _job_exit_code(self):
        raise NotImplementedError

    def _submit_job(self):
        p = self._get_stdout(self.submit_cmd)
        if p is None:
            raise EGCGError('Job submission failed')
        return p

    def _job_finished(self):
        statuses = self._job_statuses()
        for s in statuses:
            if s in self.finished_statuses:
                pass
            elif s in self.unfinished_statuses:
                return False
            else:
                raise EGCGError('Bad job status: %s', s)
        return True

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
        data = self._get_stdout('qstat -xt {j}'.format(j=self.job_id)).split('\n')
        return [d for d in data[2:] if d]

    def _job_statuses(self):
        statuses = set()
        reports = self._qstat()
        for r in reports:
            job_id, job_name, user, time, status, queue = r.split()
            statuses.add(status)
        return statuses

    def _job_exit_code(self):
        exit_status = 0
        for s in self._job_statuses():
            exit_status += self.finished_statuses.index(s)
        return exit_status


class SlurmExecutor(ClusterExecutor):
    unfinished_statuses = ('RUNNING', 'RESIZING', 'SUSPENDED', 'PENDING')
    finished_statuses = ('COMPLETED', 'CANCELLED', 'CANCELLED+', 'FAILED', 'TIMEOUT', 'NODE_FAIL')
    script_writer = script_writers.SlurmWriter

    def _submit_job(self):
        # sbatch stdout: "Submitted batch job {job_id}"
        return super()._submit_job().split()[-1].strip()

    def _sacct(self, output_format):
        s = self._get_stdout('sacct -nX -j {j} -o {o}'.format(j=self.job_id, o=output_format))
        return set([t.strip() for t in s.split('\n')])

    def _squeue(self):
        s = self._get_stdout('squeue -h -j {j} -o %T'.format(j=self.job_id))
        if s:
            return sorted(set(s.split('\n')))

    def _job_statuses(self):
        s = self._squeue()
        if s:  # job is still running, so use output from squeue
            return s
        return self._sacct('State')  # job no longer in squeue, so use sacct

    def _job_exit_code(self):
        exit_status = 0
        states = self._sacct('State,ExitCode')
        for s in states:
            state, exit_code = s.split()
            exit_code = int(exit_code.split(':')[0])
            if 'CANCELLED' in state and not exit_code:  # cancelled jobs can still be exit status 0
                self.debug('Found a cancelled job - using exit status 9')
                exit_code = 9
            exit_status += exit_code
        return exit_status
