from .executor import Executor
from .stream_executor import StreamExecutor
from .array_executor import ArrayExecutor
from .cluster_executor import PBSExecutor, SlurmExecutor
from egcg_core.config import default as cfg
from egcg_core.exceptions import EGCGError


def local_execute(*cmds, parallel=True):
    """
    Execute commands locally
    :param cmds:
    :param parallel: Whether to execute multiple cmds in parallel or sequentially
    :return: Executor
    """
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
    """
    Execute commands on a compute cluster
    :param cmds:
    :param env: The kind of resource manager being run
    :param prelim_cmds: Any commands to execute before starting a job array
    :param cluster_config:
    :return: ClusterExecutor
    """
    if env is None:
        env = cfg.query('executor', 'job_execution')

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
    if env == 'local':
        return local_execute(*cmds)
    else:
        return cluster_execute(*cmds, env=env, prelim_cmds=prelim_cmds, **cluster_config)
