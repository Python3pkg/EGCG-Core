from os import makedirs
from os.path import join
import shutil
from egcg_core.executor import script_writers
from tests import TestEGCG


class TestScriptWriter(TestEGCG):
    array_index = 'JOB_INDEX'
    exp_header = []

    def setUp(self):
        self.working_dir = join(self.assets_path, 'test_script_writer_wd')
        makedirs(self.working_dir, exist_ok=True)
        self.script_writer = script_writers.ScriptWriter('a_job_name', self.working_dir, 'a_job_queue')

    def tearDown(self):
        shutil.rmtree(self.working_dir)

    def _compare_writer_lines(self, expected):
        self.compare_lists(
            [l.rstrip('\n') for l in self.script_writer.lines],
            [l.rstrip('\n') for l in self.exp_header + expected]
        )

    def test_write_line(self):
        self.script_writer.write_line('a_line')
        self._compare_writer_lines(['a_line'])

    def test_write_job(self):
        self.script_writer.write_jobs(['a_cmd'])
        self._compare_writer_lines(['a_cmd'])

    def test_write_job_prelim_cmds(self):
        self.script_writer.write_jobs(['a_cmd'], prelim_cmds=['a_prelim_cmd'])
        self._compare_writer_lines(['a_prelim_cmd', '', 'a_cmd'])

    def test_start_array(self):
        self.script_writer._start_array()
        self._compare_writer_lines(['case ${array_index} in'.format(array_index=self.array_index)])

    def test_finish_array(self):
        self.script_writer._finish_array()
        self._compare_writer_lines(
            [
                '*) echo "Unexpected {array_index}: ${array_index}"'.format(array_index=self.array_index),
                'esac'
            ]
        )

    def test_write_array_cmd(self):
        self.script_writer._write_array_cmd(1337, 'an_array_cmd')
        self.script_writer._write_array_cmd(
            1338, 'another_array_cmd', log_file=join(self.assets_path, 'a_log_file')
        )
        self._compare_writer_lines(
            [
                '1337) an_array_cmd\n' + ';;',
                '1338) another_array_cmd > ' + join(self.assets_path, 'a_log_file') + ' 2>&1''\n;;'
            ]
        )

    def test_write_job_array(self):
        self.script_writer.write_jobs(['a_cmd', 'another_cmd'])
        expected = [
            'case ${array_index} in'.format(array_index=self.array_index),
            '1) a_cmd > ' + self.script_writer.log_file + '1 2>&1' + '\n' + ';;',
            '2) another_cmd > ' + self.script_writer.log_file + '2 2>&1' + '\n' + ';;',
            '*) echo "Unexpected {array_index}: ${array_index}"'.format(array_index=self.array_index),
            'esac'
        ]
        self._compare_writer_lines(expected)

    def test_write_job_array_prelim_cmds(self):
        self.script_writer.write_jobs(['a_cmd', 'another_cmd'], prelim_cmds=['a_prelim_cmd'])
        expected = [
            'a_prelim_cmd',
            '',
            'case ${array_index} in'.format(array_index=self.array_index),
            '1) a_cmd > ' + self.script_writer.log_file + '1 2>&1' + '\n' + ';;',
            '2) another_cmd > ' + self.script_writer.log_file + '2 2>&1' + '\n' + ';;',
            '*) echo "Unexpected {array_index}: ${array_index}"'.format(array_index=self.array_index),
            'esac'
        ]
        self._compare_writer_lines(expected)

    def test_save(self):
        self.script_writer.write_line('a_line')
        self.script_writer._save()
        assert 'a_line\n' in open(self.script_writer.script_name, 'r').readlines()

    def test_trim_field(self):
        assert self.script_writer._trim_field('a_field_name_too_long_for_pbs', 15) == 'a_field_name_to'


class TestPBSWriter(TestScriptWriter):
    array_index = 'PBS_ARRAY_INDEX'

    def setUp(self):
        super().setUp()
        self.script_writer = script_writers.PBSWriter(
            'a_job_name',
            self.working_dir,
            'a_job_queue',
            walltime=3,
            cpus=2,
            mem=1,
            jobs=1,
            log_commands=True
        )
        self.exp_header = [
            '#!/bin/bash\n',
            '#PBS -l ncpus=2,mem=1gb',
            '#PBS -q a_job_queue',
            '#PBS -j oe',
            '#PBS -o ' + join(self.working_dir, 'a_job_name.log'),
            '#PBS -l walltime=3:00:00',
            '#PBS -N a_job_name',
            'cd ' + self.script_writer.working_dir,
            ''
        ]

    def test_write_header(self):
        self.compare_lists(self.script_writer.lines, self.exp_header)

    def test_write_header_no_walltime(self):
        script_writer = script_writers.PBSWriter(
            'a_job_name',
            self.working_dir,
            'a_job_queue',
            walltime=None,
            cpus=2,
            mem=1,
            jobs=1,
            log_commands=True
        )
        exp_header = [
            '#!/bin/bash\n',
            '#PBS -l ncpus=2,mem=1gb',
            '#PBS -q a_job_queue',
            '#PBS -j oe',
            '#PBS -o ' + join(self.working_dir, 'a_job_name.log'),
            '#PBS -N a_job_name',
            'cd ' + self.script_writer.working_dir,
            ''
        ]
        self.compare_lists(script_writer.lines, exp_header)


class TestSlurmWriter(TestScriptWriter):
    array_index = 'SLURM_ARRAY_TASK_ID'

    def setUp(self):
        super().setUp()
        self.script_writer = script_writers.SlurmWriter(
            'a_job_name',
            self.working_dir,
            'a_job_queue',
            walltime=3,
            cpus=2,
            mem=1,
            jobs=1,
            log_commands=True
        )
        self.exp_header = [
            '#!/bin/bash\n',
            '#SBATCH --mem=1g',
            '#SBATCH --cpus-per-task=2',
            '#SBATCH --partition=a_job_queue',
            '#SBATCH --output=' + join(self.working_dir, 'a_job_name.log'),
            '#SBATCH --time=3:00:00',
            '#SBATCH --job-name="a_job_name"',
            'cd ' + self.script_writer.working_dir,
            ''
        ]

    def test_write_header(self):
        self.compare_lists(self.script_writer.lines, self.exp_header)

    def test_write_header_no_walltime(self):
        script_writer = script_writers.SlurmWriter(
            'a_job_name',
            self.working_dir,
            'a_job_queue',
            walltime=None,
            cpus=2,
            mem=1,
            jobs=1,
            log_commands=True
        )
        exp_header = [
            '#!/bin/bash\n',
            '#SBATCH --mem=1g',
            '#SBATCH --cpus-per-task=2',
            '#SBATCH --partition=a_job_queue',
            '#SBATCH --output=' + join(self.working_dir, 'a_job_name.log'),
            '#SBATCH --job-name="a_job_name"',
            'cd ' + self.script_writer.working_dir,
            ''
        ]
        self.compare_lists(script_writer.lines, exp_header)
