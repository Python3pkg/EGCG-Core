import subprocess
from time import sleep
from egcg_core.exceptions import EGCGError
from egcg_core.app_logging import AppLogger
from egcg_core.config import cfg
from . import script_writers


class ClusterExecutor(AppLogger):
    script_writer = None
    finished_statuses = None
    unfinished_statuses = None

    def __init__(self, *cmds, prelim_cmds=None, **cluster_config):
        """
        :param list cmds: Full path to a job submission script
        """
        self.job_queue = cfg['executor']['job_queue']
        self.job_id = None
        w = self._get_writer(jobs=len(cmds), **cluster_config)
        if cfg.query('executor', 'pre_job_source'):
            if not prelim_cmds:
                prelim_cmds = []
            else:
                prelim_cmds = list(prelim_cmds)
            prelim_cmds.append('source ' + cfg['executor']['pre_job_source'])
        w.write_jobs(cmds, prelim_cmds)
        qsub = cfg.query('executor', 'qsub', ret_default='qsub')
        self.cmd = qsub + ' ' + w.script_name

    def start(self):
        self.job_id = self._submit_job()
        self.info('Submitted "%s" as job %s' % (self.cmd, self.job_id))

    def join(self):
        sleep(10)
        while not self._job_finished():
            sleep(30)
        return self._job_exit_code()

    def _get_writer(self, job_name, working_dir, walltime=None, cpus=1, mem=2, jobs=1, log_commands=True):
        return self.script_writer(job_name, working_dir, self.job_queue, cpus, mem, walltime, jobs, log_commands)

    def _job_status(self):
        raise NotImplementedError

    def _job_exit_code(self):
        raise NotImplementedError

    def _submit_job(self):
        p = self._get_stdout(self.cmd)
        if p is None:
            raise EGCGError('Job submissions failed')
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
        s = self._get_stdout('sacct -n -j {j} -o {o}'.format(j=self.job_id, o=output_format))
        return list(set(s.split('\n')))[0]

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
