from os import makedirs
from shutil import rmtree
from os.path import join, dirname, basename
from tests import TestEGCG
from egcg_core import util

fastq_dir = join(TestEGCG.assets_path, 'fastqs')


def test_find_files():
    expected = [join(TestEGCG.assets_path, f) for f in ('ftest.txt', 'ftest_2.txt')]
    assert util.find_files(TestEGCG.assets_path, 'ftest*.txt') == expected


def test_find_file():
    assert util.find_file(TestEGCG.assets_path, 'ftest.txt') == join(TestEGCG.assets_path, 'ftest.txt')


def test_str_join():
    assert util.str_join('this', 'that', 'other', separator='/') == 'this/that/other'


def test_find_fastqs():
    fastqs = util.find_fastqs(fastq_dir, '10015AT', '10015AT0001')
    for file_name in ['10015AT0001_S6_L004_R1_001.fastq.gz', '10015AT0001_S6_L004_R2_001.fastq.gz',
                      '10015AT0001_S6_L005_R1_001.fastq.gz', '10015AT0001_S6_L005_R2_001.fastq.gz']:
        assert join(fastq_dir, '10015AT', '10015AT0001', file_name) in fastqs


def test_find_fastqs_with_lane():
    fastqs = util.find_fastqs(fastq_dir, '10015AT', '10015AT0001', lane=4)
    for file_name in ['10015AT0001_S6_L004_R1_001.fastq.gz', '10015AT0001_S6_L004_R2_001.fastq.gz']:
        assert join(fastq_dir, '10015AT', '10015AT0001', file_name) in fastqs


def test_find_all_fastqs():
    fastqs = util.find_all_fastqs(fastq_dir)
    for file_name in ('10015AT0001_S6_L004_R1_001.fastq.gz', '10015AT0001_S6_L004_R2_001.fastq.gz',
                      '10015AT0002_merged_R1.fastq.gz', '10015AT0002_merged_R2.fastq.gz'):
        assert file_name in [basename(f) for f in fastqs]


def test_find_all_fastq_pairs():
    observed = util.find_all_fastq_pairs(join(fastq_dir, '10015AT', '10015AT0001'))
    expected = [('10015AT0001_S6_L004_R1_001.fastq.gz', '10015AT0001_S6_L004_R2_001.fastq.gz'),
                ('10015AT0001_S6_L005_R1_001.fastq.gz', '10015AT0001_S6_L005_R2_001.fastq.gz')]
    assert [(basename(f), basename(g)) for f, g in observed] == expected


def test_same_fs():
    test = join(TestEGCG.assets_path, 'ftest.txt')
    test_2 = join(TestEGCG.assets_path, 'ftest_2.txt')
    test_nonexistent = join(TestEGCG.assets_path, 'ftest_nonexistent.txt')

    assert util.same_fs(test, None) is False
    assert util.same_fs(test, test_2)
    assert util.same_fs(test, test_nonexistent)


class TestMoveDir(TestEGCG):
    def setUp(self):
        self.test_dir = join(self.assets_path, 'move_dir')
        self._setup_source_dir()

    def _setup_source_dir(self):
        example_files = (
            ('ftest1.txt',),
            ('a_subdir', 'ftest2.txt'),
            ('a_subdir', 'a_subsubdir', 'ftest2-1.txt'),
            ('another_subdir', 'ftest3.txt'),
        )
        for path in example_files:
            full_path = join(self.test_dir, 'from', *path)
            makedirs(dirname(full_path), exist_ok=True)
            open(full_path, 'w').close()

    def tearDown(self):
        rmtree(util.find_file(self.test_dir, 'to'))

    def test_move_dir(self):
        frm = join(self.test_dir, 'from')
        to = join(self.test_dir, 'to')
        assert util.find_file(frm, 'ftest1.txt')
        assert not util.find_file(to)

        util.move_dir(frm, to)

        assert not util.find_file(frm, 'ftest1.txt')
        assert util.find_file(to, 'ftest1.txt')

        self._setup_source_dir()  # test moving a second time
        exit_status = util.move_dir(frm, to)
        assert exit_status == 0
