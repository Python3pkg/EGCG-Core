from .executor import Executor
from .stream_executor import StreamExecutor
from .array_executor import ArrayExecutor
from .cluster_executor import PBSExecutor, SlurmExecutor
from egcg_core.config import default as cfg
from egcg_core.exceptions import EGCGError


def local_execute(*cmds, parallel=True):
    if len(cmds) == 1:
        if parallel:
            e = StreamExecutor(cmds[0])
        else:
            e = Executor(cmds[0])
    else:
        e = ArrayExecutor(cmds, stream=parallel)

    e.start()
    return e


def cluster_execute(*cmds, env=None, prelim_cmds=None, **cluster_config):
    if env == 'pbs':
        cls = PBSExecutor
    elif env == 'slurm':
        cls = SlurmExecutor
    else:
        raise EGCGError('Unknown execution environment: ' + env)

    e = cls(*cmds, prelim_cmds=prelim_cmds, **cluster_config)
    e.start()
    return e


def execute(*cmds, env=None, prelim_cmds=None, **cluster_config):
    """
    :param list[str] cmds: A list where each item is a list of strings to be passed to Executor
    :param str env:
    :param cluster_config:
    :return: Executor
    """
    if env is None:
        env = cfg.query('executor', 'job_execution', ret_default='local')

    if env == 'local':
        return local_execute(*cmds)
    else:
        return cluster_execute(*cmds, env=env, prelim_cmds=prelim_cmds, **cluster_config)
