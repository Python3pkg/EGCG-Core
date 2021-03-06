import subprocess
from time import sleep
from egcg_core.exceptions import EGCGError
from egcg_core.app_logging import AppLogger
from egcg_core.config import cfg
from . import script_writers

running_executors = {}


def stop_running_jobs():
    for job_id in running_executors:
        running_executors[job_id].cancel_job()

    for job_id in list(running_executors):
        running_executors[job_id].join()


class ClusterExecutor(AppLogger):
    script_writer = script_writers.ScriptWriter
    finished_statuses = None
    unfinished_statuses = None

    def __init__(self, *cmds, prelim_cmds=None, **cluster_config):
        """
        :param list cmds: Full path to a job submission script
        """
        self.interval = cfg.query('executor', 'join_interval', ret_default=30)
        self.job_id = None
        self.job_name = cluster_config.get('job_name')
        self.cmds = cmds
        self.prelim_cmds = prelim_cmds
        self.writer = self._get_writer(job_queue=cfg['executor']['job_queue'], **cluster_config)

    def write_script(self):
        if self.prelim_cmds:
            self.writer.register_cmds(*self.prelim_cmds, parallel=False)

        pre_job_source = cfg.query('executor', 'pre_job_source')
        if pre_job_source:
            self.writer.register_cmd('source ' + pre_job_source)

        self.writer.line_break()
        self.writer.register_cmds(*self.cmds, parallel=True)
        self.writer.add_header()
        self.writer.save()

    def start(self):
        """Write the jobs into a script, submit it and capture qsub's output as self.job_id."""
        self.write_script()
        self._submit_job()
        running_executors[self.job_id] = self  # register to running_executors
        self.info('Submitted "%s" as job %s' % (self.writer.script_name, self.job_id))

    def join(self):
        """Wait until the job has finished, then return its exit status."""
        sleep(5)
        while not self._job_finished():
            sleep(self.interval)
        running_executors.pop(self.job_id, None)  # unregister from running_executors
        return self._job_exit_code()

    def _get_writer(self, job_name, working_dir, job_queue, walltime=None, cpus=1, mem=2, log_commands=True):
        return self.script_writer(job_name, working_dir, job_queue, log_commands=log_commands, cpus=cpus, mem=mem, walltime=walltime)

    def _job_statuses(self):
        return ()

    def _job_exit_code(self):
        raise NotImplementedError

    def _submit_job(self):
        self.job_id = self._run_and_retry(cfg['executor']['qsub'] + ' ' + self.writer.script_name)
        if self.job_id is None:
            raise EGCGError('Job submission failed')

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

    def _run_and_retry(self, cmd, retry=3):
        attempt = 0
        while attempt < retry:
            msg = self._get_stdout(cmd)
            if msg is not None:
                return msg
            sleep(5)
            attempt += 1

    def cancel_job(self):
        if not self._job_finished():
            self._cancel_job()

    def _cancel_job(self):
        raise NotImplementedError


class PBSExecutor(ClusterExecutor):
    script_writer = script_writers.PBSWriter
    unfinished_statuses = 'BEHQRSTUW'
    finished_statuses = 'FXM'

    def _qstat(self):
        data = self._run_and_retry('qstat -xt {j}'.format(j=self.job_id)).split('\n')
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

    def _cancel_job(self):
        msg = self._run_and_retry('qdel ' + self.job_id)
        self.info(msg)


class SlurmExecutor(ClusterExecutor):
    script_writer = script_writers.SlurmWriter
    unfinished_statuses = ('CONFIGURING', 'COMPLETING', 'PENDING', 'RUNNING', 'RESIZING', 'SUSPENDED',)
    finished_statuses = ('BOOT_FAIL', 'CANCELLED', 'COMPLETED', 'DEADLINE', 'FAILED', 'NODE_FAIL',
                         'PREEMPTED', 'TIMEOUT')

    def _submit_job(self):
        # sbatch stdout: "Submitted batch job {job_id}"
        super()._submit_job()
        self.job_id = self.job_id.split()[-1].strip()

    def _sacct(self, output_format):
        data = self._run_and_retry('sacct -nX -j {j} -o {o}'.format(j=self.job_id, o=output_format))
        return set(d.strip() for d in data.split('\n'))

    def _squeue(self):
        s = self._run_and_retry('squeue -h -j {j} -o %T'.format(j=self.job_id))
        if s:
            return set(s.split('\n'))

    def _job_statuses(self):
        s = self._squeue()
        if s:  # job is in squeue, so use that
            return s
        return set(s.rstrip('+') for s in self._sacct('State'))  # job no longer in squeue, so use sacct

    def _job_exit_code(self):
        exit_status = 0
        states = set()
        reports = self._sacct('State,ExitCode')
        for r in reports:
            state, exit_code = r.split()
            state = state.rstrip('+')
            states.add(state)
            exit_code = int(exit_code.split(':')[0])
            if state == 'CANCELLED' and not exit_code:  # cancelled jobs can still be exit status 0
                self.debug('Found a cancelled job - using exit status 9')
                exit_code = 9
            exit_status += exit_code

        self.info('Got %s states from %s (%s) with %s jobs: %s', len(states), self.job_name, self.job_id,
                  len(reports), states)
        return exit_status

    def _cancel_job(self):
        msg = self._run_and_retry('scancel ' + self.job_id)
        self.info(msg)
