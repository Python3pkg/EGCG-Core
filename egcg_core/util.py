import os
import os.path
import shutil
from glob import glob
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
