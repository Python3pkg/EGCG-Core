from . import ClusterWriter


class SlurmWriter(ClusterWriter):
    """Writes a Bash script runnable on Slurm"""
    suffix = '.slurm'
    array_index = 'SLURM_ARRAY_TASK_ID'

    header = (
        '#!/bin/bash\n',
        '#SBATCH --job-name="{job_name}"',
        '#SBATCH --cpus-per-task={cpus}',
        '#SBATCH --mem={mem}g',
        '#SBATCH --partition={queue}',
        '#SBATCH --output={log_file}'
    )
    walltime_header = '#SBATCH --time={walltime}:00:00'
    array_header = '#SBATCH --array=1-{jobs}'
