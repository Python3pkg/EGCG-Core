from .script_writer import ClusterWriter


class PBSWriter(ClusterWriter):
    """Writes a Bash script runnable on PBS"""
    suffix = '.pbs'
    array_index = 'PBS_ARRAY_INDEX'

    header = (
        '#!/bin/bash\n\n'
        '#PBS -N {job_name}\n'
        '#PBS -l ncpus={cpus},mem={mem}gb\n'
        '#PBS -q {queue}\n'
        '#PBS -j oe\n'
        '#PBS -o {log_file}'
    )
    walltime_header = '#PBS -l walltime={walltime}:00:00'
    array_header = '#PBS -J 1-{jobs}'
