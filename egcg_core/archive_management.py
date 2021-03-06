import os
import re
import subprocess
from egcg_core.app_logging import logging_default as log_cfg
from egcg_core.exceptions import EGCGError

app_logger = log_cfg.get_logger('archive_management')
state_re = re.compile('^(.+): \((0x\w+)\)(.+)?')


class ArchivingError(EGCGError):
    pass


def _get_stdout(cmd):
    p = subprocess.Popen(cmd.split(' '), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    exit_status = p.wait()
    o, e = p.stdout.read(), p.stderr.read()
    msg = '%s -> (%s, %s, %s)' % (cmd, exit_status, o, e)
    if exit_status:
        app_logger.error(msg)
        return None
    else:
        app_logger.debug(msg)
        return o.decode('utf-8').strip()


def archive_states(file_path):
    cmd = 'lfs hsm_state %s' % file_path
    val = _get_stdout(cmd)
    match = state_re.match(val)
    if match:
        file_name = match.group(1)
        assert file_name == file_path
        state_and_id = match.group(3)
        if state_and_id:
            state, archive_id = state_and_id.split(',')
            states = state.strip().split()
            return states
        else:
            return []
    else:
        raise ValueError()


def is_of_state(state, file_path, known_states=None):
    if known_states:
        return state in known_states
    else:
        return state in archive_states(file_path)


def is_register_for_archiving(file_path, known_states=None):
    return is_of_state('exists', file_path, known_states)


def is_archived(file_path, known_states=None):
    return is_of_state('archived', file_path, known_states)


def is_released(file_path, known_states=None):
    return is_of_state('released', file_path, known_states)


def is_dirty(file_path, known_states=None):
    return is_of_state('dirty', file_path, known_states)


def release_file_from_lustre(file_path):
    # store the states to avoid quering multiple times
    states = archive_states(file_path)
    if is_dirty(file_path, states):
        raise ArchivingError('File %s is in a dirty state' % file_path)
    if not is_archived(file_path, states):
        raise ArchivingError('Cannot release %s from lustre because it is not archive to tape' % file_path)
    if not is_released(file_path, states):
        cmd = 'lfs hsm_release %s' % file_path
        val = _get_stdout(cmd)
        if val is not None:
            return is_released(file_path)
    else:
        app_logger.debug('Trying to release a %s already released from lustre' % file_path)
        return True


def register_for_archiving(file_path):
    if is_register_for_archiving(file_path):
        return True
    cmd = 'lfs hsm_archive %s' % file_path
    val = _get_stdout(cmd)
    if val is None or not is_register_for_archiving(file_path):
        raise ArchivingError('Registering %s for archiving to tape failed' % file_path)
    return True


def recall_from_tape(file_path):
    states = archive_states(file_path)
    if is_dirty(file_path, states):
        raise ArchivingError('File %s is in a dirty state' % file_path)
    if is_archived(file_path, states) and is_released(file_path, states):
        cmd = 'lfs hsm_restore %s' % file_path
        val = _get_stdout(cmd)
        if val is not None:
            return True


def archive_directory(directory):
    """Recursively archive all the files in a directory"""
    success = True
    for f in os.listdir(directory):
        fp = os.path.join(directory, f)
        if os.path.isdir(fp):
            success = success and archive_directory(fp)
        elif os.path.isfile(fp):
            success = success and register_for_archiving(fp)
    return success
