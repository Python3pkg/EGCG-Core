from os import makedirs
from shutil import rmtree
from os.path import join
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
    for file_name in ['10015AT0001_S6_L004_R1_001.fastq.gz', '10015AT0001_S6_L004_R2_001.fastq.gz']:
        assert join(fastq_dir, '10015AT', '10015AT0001', file_name) in fastqs


def test_find_all_fastq_pairs():
    fastqs = util.find_all_fastq_pairs(fastq_dir)
    for f1, f2 in [('10015AT0001_S6_L004_R1_001.fastq.gz', '10015AT0001_S6_L004_R2_001.fastq.gz'),
                   ('10015AT0001_S6_L005_R1_001.fastq.gz', '10015AT0001_S6_L005_R2_001.fastq.gz')]:
        fp1 = join(fastq_dir, '10015AT', '10015AT0001', f1)
        fp2 = join(fastq_dir, '10015AT', '10015AT0001', f2)
        assert (fp1, fp2) in fastqs


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
        makedirs(join(self.test_dir, 'from'), exist_ok=True)
        open(join(self.test_dir, 'from', 'ftest.txt'), 'w').close()

    def tearDown(self):
        rmtree(util.find_file(self.test_dir, 'to'))

    def test_move_dir(self):
        frm = join(self.test_dir, 'from')
        to = join(self.test_dir, 'to')
        assert util.find_file(frm, 'ftest.txt')
        assert not util.find_file(to)

        util.move_dir(frm, to)

        assert not util.find_file(frm, 'ftest.txt')
        assert util.find_file(to, 'ftest.txt')
