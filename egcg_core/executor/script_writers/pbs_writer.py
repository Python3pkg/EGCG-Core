from .script_writer import ClusterWriter


class PBSWriter(ClusterWriter):
    """Writes a Bash script runnable on PBS"""
    suffix = '.pbs'
    array_index = 'PBS_ARRAY_INDEX'

    header = (
        '#!/bin/bash\n',
        '#PBS -N {job_name}',
        '#PBS -l ncpus={cpus},mem={mem}gb',
        '#PBS -q {queue}',
        '#PBS -j oe',
        '#PBS -o {log_file}'
    )
    walltime_header = '#PBS -l walltime={walltime}:00:00'
    array_header = '#PBS -J 1-{jobs}'

    def __init__(self, job_name, working_dir, job_queue, log_commands=True, **cluster_config):
        super().__init__(job_name, working_dir, job_queue, log_commands, **cluster_config)
        if len(self.job_name) > 15:
            self.job_name = self.job_name[:15]  # job names longer than 15 chars break PBS
