import os
import pytest
import shutil
import logging
import subprocess
from unittest.mock import patch, Mock
from tests import TestEGCG
from egcg_core.executor import Executor, StreamExecutor, ArrayExecutor, PBSExecutor, SlurmExecutor
from egcg_core.executor.cluster_executor import ClusterExecutor
from egcg_core.exceptions import EGCGError
from egcg_core.app_logging import LoggingConfiguration
from egcg_core.config import default as cfg

log_cfg = LoggingConfiguration(cfg)
log_cfg.set_log_level(logging.DEBUG)
log_cfg.add_stdout_handler(logging.DEBUG)

get_writer = 'egcg_core.executor.cluster_executor.ClusterExecutor._get_writer'
get_stdout = 'egcg_core.executor.cluster_executor.ClusterExecutor._get_stdout'
sleep = 'egcg_core.executor.cluster_executor.sleep'


class TestExecutor(TestEGCG):
    def _get_executor(self, cmd):
        e = Executor(cmd)
        e.log_cfg = log_cfg
        return e

    def test_cmd(self):
        e = self._get_executor('ls ' + os.path.join(self.assets_path, '..'))
        exit_status = e.join()
        assert exit_status == 0

    def test_dodgy_cmd(self):
        with pytest.raises(EGCGError) as err:
            e = self._get_executor('dodgy_cmd')
            e.join()
            assert 'Command failed: \'dodgy_cmd\'' in str(err)

    def test_process(self):
        e = self._get_executor('ls ' + os.path.join(self.assets_path, '..'))
        assert e.proc is None
        proc = e._process()
        assert proc is e.proc and isinstance(e.proc, subprocess.Popen)


class TestStreamExecutor(TestExecutor):
    def _get_executor(self, cmd):
        e = StreamExecutor(cmd)
        e.log_cfg = log_cfg
        return e

    def test_cmd(self):
        e = self._get_executor(os.path.join(self.assets_path, 'countdown.sh'))
        e.start()
        assert e.join() == 0

    def test_dodgy_command(self):
        e = self._get_executor(os.path.join(self.assets_path, 'countdown.sh') + ' dodgy')
        e.start()
        assert e.join() == 13  # same exit status as the running script

    def test_dodgy_cmd(self):
        with pytest.raises(EGCGError) as err:
            e = self._get_executor('dodgy_cmd')
            e.start()
            e.join()
            assert 'self.proc command failed: \'dodgy_cmd\'' in str(err)


class TestArrayExecutor(TestExecutor):
    def _get_executor(self, cmds):
        e = ArrayExecutor(cmds, stream=True)
        e.log_cfg = log_cfg
        return e

    def test_cmd(self):
        e = self._get_executor(['ls', 'ls -lh', 'pwd'])
        e.start()
        assert e.join() == 0
        assert e.exit_statuses == [0, 0, 0]

    def test_dodgy_cmd(self):
        e = self._get_executor(['ls', 'non_existent_cmd', 'pwd'])
        e.start()
        with pytest.raises(EGCGError) as err:
            e.join()
            assert 'Commands failed' in str(err)


class TestClusterExecutor(TestEGCG):
    @property
    def script(self):
        return os.path.join(self.assets_path, 'countdown.sh')

    def setUp(self):
        os.makedirs(os.path.join(self.assets_path, 'a_run_id'), exist_ok=True)
        self._set_executor(self.script)

    def tearDown(self):
        shutil.rmtree(os.path.join(self.assets_path, 'a_run_id'))

    def _set_executor(self, cmd):
        with patch(get_writer, return_value=Mock(script_name='a_script_name')):
            self.executor = ClusterExecutor(
                cmd,
                job_name='test_job',
                working_dir=os.path.join(self.assets_path, 'a_run_id')
            )
            self.executor.log_cfg = log_cfg

    def test_get_stdout(self):
        popen = 'egcg_core.executor.executor.subprocess.Popen'
        with patch(popen, return_value=Mock(wait=Mock(return_value=None))) as p:
            assert self.executor._get_stdout('ls -d ' + self.assets_path).endswith('tests/assets')
            p.assert_called_with(['ls', '-d', self.assets_path], stdout=-1, stderr=-1)

    def test_cmd(self):
        assert self.executor.cmd == '/bin/sh a_script_name'

    @patch(get_stdout, return_value=None)
    def test_dodgy_cmd(self, mocked_get_stdout):
        with pytest.raises(EGCGError) as e:
            self._set_executor(os.path.join(self.assets_path, 'non_existent_script.sh'))
            self.executor.cmd = '/bin/sh non_existent_script.sh'
            self.executor.start()
            assert str(e) == 'Job submission failed'
        mocked_get_stdout.assert_called_with('/bin/sh non_existent_script.sh')

    def test_join(self):
        e_cls = 'egcg_core.executor.cluster_executor.' + self.executor.__class__.__name__
        job_finished = e_cls + '._job_finished'
        exit_code = e_cls + '._job_exit_code'
        self.executor.finished_statuses = 'FXM'
        with patch(job_finished, return_value=True), patch(exit_code, return_value=0), patch(sleep):
            assert self.executor.join() == 0


class TestPBSExecutor(TestClusterExecutor):
    def _set_executor(self, cmd):
        with patch(get_writer, return_value=Mock(script_name='a_script_name')):
            self.executor = PBSExecutor(
                cmd,
                job_name='test_job',
                working_dir=os.path.join(self.assets_path, 'a_run_id')
            )
            self.executor.log_cfg = log_cfg

    def test_qstat(self):
        with patch(get_stdout, return_value='this\nthat\nother') as p:
            assert self.executor._qstat() == 'other'.split()
            p.assert_called_with('qstat -x None')

    def test_job_status(self):
        qstat = 'egcg_core.executor.cluster_executor.PBSExecutor._qstat'
        fake_report = ('1337', 'a_job', 'a_user', '10:00:00', 'R',  'q')
        with patch(qstat, return_value=fake_report):
            assert self.executor._job_status() == 'R'

    def test_job_finished(self):
        job_status = 'egcg_core.executor.cluster_executor.PBSExecutor._qstat'
        with patch(job_status, return_value=(1, '1', 'user', 'time', 'B', 'queue')):
            assert not self.executor._job_finished()
        with patch(job_status, return_value=(1, '1', 'user', 'time', 'F', 'queue')):
            assert self.executor._job_finished()


class TestSlurmExecutor(TestClusterExecutor):
    def _set_executor(self, cmd):
        with patch(get_writer, return_value=Mock(script_name='a_script_name')):
            self.executor = SlurmExecutor(
                cmd,
                job_name='test_job',
                working_dir=os.path.join(self.assets_path, 'a_run_id')
            )
            self.executor.log_cfg = log_cfg

    def test_sacct(self):
        with patch(get_stdout, return_value='1:0') as p:
            assert self.executor._sacct('ExitCode') == '1:0'
            p.assert_called_with('sacct -n -j None -o ExitCode')

    def test_job_finished(self):
        sacct = 'egcg_core.executor.cluster_executor.SlurmExecutor._sacct'
        patched_squeue = patch('egcg_core.executor.cluster_executor.SlurmExecutor._squeue', return_value='')
        with patch(sacct, return_value='RUNNING'), patched_squeue:
            assert not self.executor._job_finished()
        with patch(sacct, return_value='COMPLETED'), patched_squeue:
            assert self.executor._job_finished()

    def test_job_exit_code(self):
        sacct = 'egcg_core.executor.cluster_executor.SlurmExecutor._sacct'
        with patch(sacct, return_value='CANCELLED 0:0'):
            assert self.executor._job_exit_code() == 9
        with patch(sacct, return_value='COMPLETED 0:x'):
            assert self.executor._job_exit_code() == 0
