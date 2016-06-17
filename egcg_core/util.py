import os
import os.path
import shutil
from glob import glob
from egcg_core.exceptions import EGCGError
from egcg_core.app_logging import logging_default as log_cfg

app_logger = log_cfg.get_logger('util')


def find_files(*path_parts):
    return sorted(glob(os.path.join(*path_parts)))


def find_file(*path_parts):
    files = find_files(*path_parts)
    if files:
        return files[0]


def str_join(*parts, separator=''):
    return separator.join(parts)


def find_fastqs(location, project_id, sample_id, lane=None):
    """
    Find all .fastq.gz files in an input folder 'location/project_id'.
    :param location: Top-level directory
    :param str project_id: Project subdirectory to search
    :param str sample_id: Sample subdirectory to search
    :param lane: Specific lane to search for (optional)
    :return: Full paths to *.fastq.gz files in the sample_project dir.
    :rtype: list[str]
    """
    if lane:
        pattern = '*L00%s*.fastq.gz' % lane
    else:
        pattern = '*.fastq.gz'

    pattern = os.path.join(location, project_id, sample_id, pattern)
    fastqs = find_files(pattern)
    app_logger.info('Found %s fastq files for %s', len(fastqs), pattern)
    return fastqs


def find_all_fastqs(location):
    """
    Return the results of find_fastqs as a flat list.
    :param str location: Top-level directory to search
    :return: Full paths to all *.fastq.gz files for all project and sample ids in the input dir
    """
    fastqs = []
    for name, dirs, files in os.walk(location):
        fastqs.extend([os.path.join(name, f) for f in files if f.endswith('.fastq.gz')])
    app_logger.info('Found %s fastqs in %s', len(fastqs), location)
    return fastqs


def find_all_fastq_pairs(location):
    """
    Return the results of find_all_fastqs as a list or paired fastq files. It does not check the fastq name
    but expects that they will come together after sorting.
    :param str location: Directory to search
    :return: Full paths to all *.fastq.gz files for all sample projects and sample ids in the input dir
    aggregated per pair
    :rtype: list[tuple[str, str]]
    """
    fastqs = find_all_fastqs(location)
    if len(fastqs) % 2 != 0:
        raise EGCGError('Expect a even number of fastq file in %s found %s' % (location, len(fastqs)))
    fastqs.sort()
    return list(zip(*[iter(fastqs)] * 2))


def same_fs(file1, file2):
    if not file1 or not file2:
        return False
    if not os.path.exists(file1):
        return same_fs(os.path.dirname(file1), file2)
    if not os.path.exists(file2):
        return same_fs(file1, os.path.dirname(file2))

    dev1 = os.stat(file1).st_dev
    dev2 = os.stat(file2).st_dev
    return dev1 == dev2


def move_dir(src_dir, dest_dir):
    os.makedirs(dest_dir, exist_ok=True)
    contents = os.listdir(src_dir)
    try:
        for f in contents:
            if os.path.isdir(f):
                move_dir(os.path.join(src_dir, f), os.path.join(dest_dir, f))
            else:
                _move_file_or_link_target(os.path.join(src_dir, f), dest_dir)
        return 0
    except OSError:
        return 1


def _move_file_or_link_target(file_path, dest_dir):
    """Move a file to a destination directory"""
    dest_file = os.path.join(dest_dir, os.path.basename(file_path))
    if os.path.islink(file_path):
        file_path = os.path.realpath(file_path)
    shutil.move(file_path, dest_file)
