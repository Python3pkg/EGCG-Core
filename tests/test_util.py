import hashlib
import os
from os import makedirs
from shutil import rmtree
from os.path import join, basename
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

    def _create_test_file(self, f, content=None):
        with open(f, 'w') as of:
            if content:
                of.write(content)
            else:
                of.write('This is a test file')

    def _md5(self, f):
        hash_md5 = hashlib.md5()
        with open(f, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def setUp(self):
        self.test_dir = join(self.assets_path, 'move_dir')
        makedirs(join(self.test_dir, 'from'), exist_ok=True)
        makedirs(join(self.test_dir, 'from', 'subdir'), exist_ok=True)
        self._create_test_file(join(self.test_dir, 'from', 'ftest.txt'))
        self._create_test_file(join(self.test_dir, 'from', 'subdir', 'ftest.txt'))

        makedirs(join(self.test_dir, 'external'), exist_ok=True)
        self._create_test_file(join(self.test_dir, 'external', 'external.txt'), 'External file')
        os.symlink(join(self.test_dir, 'external', 'external.txt'), join(self.test_dir, 'from', 'external_renamed.txt'))

        makedirs(join(self.test_dir, 'exists'), exist_ok=True)
        makedirs(join(self.test_dir, 'exists', 'subdir'), exist_ok=True)
        self._create_test_file(join(self.test_dir, 'exists', 'subdir', 'ftest.txt'), 'another file')
        self._create_test_file(join(self.test_dir, 'exists', 'ftest.txt'), 'another file')

    def tearDown(self):
        rmtree(util.find_file(self.test_dir, 'to'))
        rmtree(util.find_file(self.test_dir, 'from'))
        rmtree(util.find_file(self.test_dir, 'exists'))
        rmtree(util.find_file(self.test_dir, 'external'))

    def test_move_dir(self):
        frm = join(self.test_dir, 'from')
        to = join(self.test_dir, 'to')
        md5_from = self._md5(join(frm, 'ftest.txt'))
        assert util.find_file(frm, 'ftest.txt')
        assert not util.find_file(to)

        assert util.move_dir(frm, to) == 0

        assert not util.find_file(frm, 'ftest.txt')
        assert util.find_file(to, 'ftest.txt')
        assert util.find_file(to, 'subdir', 'ftest.txt')
        assert md5_from == self._md5(join(to, 'ftest.txt'))

        assert util.find_file(to, 'external_renamed.txt')

    def _move_dir_exists(self):
        frm = join(self.test_dir, 'from')
        to = join(self.test_dir, 'exists')
        md5_from1 = self._md5(join(frm, 'ftest.txt'))
        md5_from2 = self._md5(join(frm, 'subdir', 'ftest.txt'))

        assert util.find_file(frm, 'ftest.txt')
        assert util.find_file(to, 'ftest.txt')
        assert not md5_from1 == self._md5(join(to, 'ftest.txt'))
        assert not md5_from2 == self._md5(join(to, 'subdir', 'ftest.txt'))

        util.move_dir(frm, to)

        assert not util.find_file(frm, 'ftest.txt')
        assert util.find_file(to, 'ftest.txt')
        assert md5_from1 == self._md5(join(to, 'ftest.txt'))
        assert md5_from2 == self._md5(join(to, 'subdir', 'ftest.txt'))
