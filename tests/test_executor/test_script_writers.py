from os import makedirs
from os.path import join
import shutil
from egcg_core.executor import script_writers
from tests import TestEGCG

working_dir = join(TestEGCG.assets_path, 'test_script_writer_wd')


class TestScriptWriter(TestEGCG):
    def setUp(self):
        makedirs(working_dir, exist_ok=True)
        self.script_writer = script_writers.ScriptWriter('a_job_name', working_dir, 'a_job_queue')
        assert self.script_writer.lines == []

    def tearDown(self):
        shutil.rmtree(working_dir)

    def test_init(self):
        w = self.script_writer
        assert w.job_name == 'a_job_name'
        assert w.script_name == join(working_dir, 'a_job_name.sh')
        assert w.log_commands is True
        assert w.log_file == join(working_dir, 'a_job_name.log')
        assert w.queue == 'a_job_queue'

    def test_register_cmd(self):
        self.script_writer.register_cmd('a_cmd', log_file='a_log_file')
        assert self.script_writer.lines == ['a_cmd > a_log_file 2>&1']

    def test_register_cmds(self):
        self.script_writer.register_cmds('this', 'that')
        assert self.script_writer.lines == ['this', 'that']

    def test_add_job_array(self):
        self.script_writer.add_job_array('this', 'that', 'other')
        assert self.script_writer.lines == [
            'case $JOB_INDEX in',
            '1) this > ' + join(working_dir, 'a_job_name.log1') + ' 2>&1\n;;',
            '2) that > ' + join(working_dir, 'a_job_name.log2') + ' 2>&1\n;;',
            '3) other > ' + join(working_dir, 'a_job_name.log3') + ' 2>&1\n;;',
            '*) echo "Unexpected JOB_INDEX: $JOB_INDEX"',
            'esac'
        ]

    def test_save(self):
        self.script_writer.add_line('a_line')
        self.script_writer.save()
        assert 'a_line\n' in open(self.script_writer.script_name, 'r').readlines()

    def test_trim_field(self):
        assert self.script_writer._trim_field('a_field_name_too_long_for_pbs', 15) == 'a_field_name_to'


class TestClusterWriter(TestScriptWriter):
    writer_cls = script_writers.ClusterWriter
    array_index = 'JOB_INDEX'
    exp_cmds = [
        '',
        'some',
        'preliminary',
        'cmds',
        'case $%s in' % array_index,
        '1) this\n;;',
        '2) that\n;;',
        '3) other\n;;',
        '*) echo "Unexpected %s: $%s"' % (array_index, array_index),
        'esac'
    ]
    exp_header = [
        (
            '#!/bin/bash\n\n'
            '# job name: a_job_name\n'
            '# cpus: 1\n'
            '# mem: 2gb\n'
            '# queue: a_job_queue\n'
            '# log file: ' + join(working_dir, 'a_job_name.log')
        ),
        '# walltime: 3',
        '# job array: 1-3',
        '',
        'cd ' + working_dir
    ]

    def setUp(self):
        super().setUp()
        self.script_writer = self.writer_cls(
            'a_job_name',
            working_dir,
            'a_job_queue',
            cpus=1,
            mem=2,
            queue='a_queue',
            walltime='3'
        )
        assert self.script_writer.lines == []

    def test(self):
        self.script_writer.log_commands = False
        self.script_writer.register_cmds('some', 'preliminary', 'cmds')
        self.script_writer.register_cmds('this', 'that', 'other', parallel=True)
        self.script_writer.write_header()

        obs = self.script_writer.lines
        exp = self.exp_header + self.exp_cmds
        assert obs == exp


class TestPBSWriter(TestScriptWriter):
    writer_cls = script_writers.PBSWriter
    array_index = 'PBS_ARRAY_INDEX'
    exp_header = [
        (
            '#!/bin/bash\n\n'
            '#PBS -N a_job_name\n'
            '#PBS -l ncpus=1,mem=2gb\n'
            '#PBS -q a_job_queue\n'
            '#PBS -j oe\n'
            '#PBS -o ' + join(working_dir, 'a_job_name.log')
        ),
        '#PBS -l walltime=3',
        '#PBS -J 1-3',
        '',
        'cd ' + working_dir
    ]


class TestSlurmWriter(TestScriptWriter):
    writer_cls = script_writers.SlurmWriter
    array_index = 'SLURM_ARRAY_TASK_ID'
    exp_header = [
        (
            '#!/bin/bash\n\n'
            '#SBATCH --job-name=a_job_name\n'
            '#SBATCH --cpus-PER-TASK=1\n'
            '#SBATCH --mem=2gb\n'
            '#SBATCH --partition=a_job_queue\n'
            '#SBATCH --output=' + join(working_dir, 'a_job_name.log')
        ),
        '#SBATCH --time=3:00:00',
        '#SBATCH --array=1-3',
        '',
        'cd ' + working_dir
    ]
