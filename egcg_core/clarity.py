import re
from genologics.lims import Lims
from egcg_core.config import cfg
from egcg_core.app_logging import logging_default as log_cfg
from egcg_core.exceptions import EGCGError

app_logger = log_cfg.get_logger('clarity')
try:
    from egcg_core.ncbi import get_species_name
except ImportError:
    app_logger.warning('Could not import egcg_core.ncbi. Is sqlite3 available?')

    def get_species_name(query_species):
        raise EGCGError('Could not import egcg_core.ncbi.get_species_name - sqlite3 seems to be unavailable.')


_lims = None


def connection():
    global _lims
    if not _lims:
        _lims = Lims(**cfg.get('clarity'))
    return _lims


def get_valid_lanes(flowcell_name):
    """
    Get all valid lanes for a given flowcell
    :param str flowcell_name: a flowcell id, e.g. HCH25CCXX
    :return: list of numbers of non-failed lanes
    """
    containers = connection().get_containers(type='Patterned Flowcell', name=flowcell_name)
    if len(containers) != 1:
        app_logger.warning('%s Flowcell(s) found for name %s', len(containers), flowcell_name)
        return None

    flowcell = containers[0]
    valid_lanes = []
    for placement_key in flowcell.placements:
        lane = int(placement_key.split(':')[0])
        artifact = flowcell.placements.get(placement_key)
        if not artifact.udf.get('Lane Failed?', False):
            valid_lanes.append(lane)
    valid_lanes = sorted(valid_lanes)
    app_logger.info('Valid lanes for %s: %s', flowcell_name, str(valid_lanes))
    return valid_lanes


def find_project_name_from_sample(sample_name):
    samples = get_samples(sample_name)
    if samples:
        project_names = set([s.project.name for s in samples])
        if len(project_names) == 1:
            return project_names.pop()
        else:
            app_logger.error('%s projects found for sample %s', len(project_names), sample_name)


def find_run_elements_from_sample(sample_name):
    sample = get_sample(sample_name)
    if sample:
        run_log_files = connection().get_artifacts(
            sample_name=sample.name,
            process_type='AUTOMATED - Sequence'
        )
        for run_log_file in run_log_files:
            p = run_log_file.parent_process
            run_id = p.udf.get('RunID')
            lanes = p.input_per_sample(sample.name)
            for artifact in lanes:
                lane = artifact.position.split(':')[0]
                if not artifact.udf.get('Lane Failed?', False):
                    yield run_id, lane


def get_species_from_sample(sample_name):
    samples = get_samples(sample_name)
    if samples:
        species_strings = set([s.udf.get('Species') for s in samples])
        nspecies = len(species_strings)
        if nspecies != 1:
            app_logger.error('%s species found for sample %s', nspecies, sample_name)
            return None
        species_string = species_strings.pop()
        if species_string:
            return get_species_name(species_string)


def get_genome_version(sample_id, species=None):
    s = get_sample(sample_id)
    if not s:
        return None
    genome_version = s.udf.get('Genome Version', None)
    if not genome_version and species:
        return cfg.query('species', species, 'default')
    return genome_version


def sanitize_user_id(user_id):
    if isinstance(user_id, str):
        return re.sub("[^\w_\-.]", "_", user_id)


substitutions = (
    (None, None),
    (re.compile('_(\d{2})$'), ':\g<1>'),  # '_01' -> ':01'
    (re.compile('__(\w):(\d{2})'), ' _\g<1>:\g<2>')  # '__L:01' -> ' _L:01'
)


def get_list_of_samples(sample_names):
    max_query = 100
    results = []
    for start in range(0, len(sample_names), max_query):
        results.extend(_get_list_of_samples(sample_names[start:start+max_query]))
    return results


def _get_list_of_samples(sample_names, sub=0):
    pattern, repl = substitutions[sub]
    _sample_names = list(sample_names)
    if pattern and repl:
        _sample_names = [pattern.sub(repl, s) for s in _sample_names]

    lims = connection()
    samples = lims.get_samples(name=_sample_names)
    lims.get_batch(samples)

    if len(samples) != len(sample_names):  # haven't got all the samples because some had _01/__L:01
        sub += 1
        remainder = sorted(set(_sample_names).difference(set([s.name for s in samples])))
        if sub < len(substitutions):
            samples.extend(_get_list_of_samples(remainder, sub))
        else:  # end recursion
            app_logger.warning('Could not find %s in Lims' % remainder)

    return samples


def get_samples(sample_name):
    lims = connection()
    samples = lims.get_samples(name=sample_name)
    # FIXME: Remove the hack when we're sure our sample id don't have colon
    if len(samples) == 0:
        sample_name_sub = re.sub("_(\d{2})$", ":\g<1>", sample_name)
        samples = lims.get_samples(name=sample_name_sub)
    if len(samples) == 0:
        sample_name_sub = re.sub("__(\w)_(\d{2})", " _\g<1>:\g<2>", sample_name)
        samples = lims.get_samples(name=sample_name_sub)
    return samples


def get_sample(sample_name):
    samples = get_samples(sample_name)
    if len(samples) != 1:
        app_logger.warning('%s Sample(s) found for name %s', len(samples), sample_name)
        return None
    return samples[0]


def get_user_sample_name(sample_name, lenient=False):
    """
    Query the LIMS and return the name the user gave to the sample
    :param str sample_name: our internal sample ID
    :param bool lenient: If True, return the sample name if no user sample name found
    :return: the user's sample name, None or the input sample name
    """
    user_sample_name = get_sample(sample_name).udf.get('User Sample Name')
    if user_sample_name:
        return sanitize_user_id(user_sample_name)
    elif lenient:
        return sample_name


def get_sample_gender(sample_name):
    sample = get_sample(sample_name)
    if sample:
        gender = sample.udf.get('Sex')
        if not gender:
            gender = sample.udf.get('Gender')
        return gender


def get_sample_genotype(sample_name, output_file_name):
    sample = get_sample(sample_name)
    if sample:
        file_id = sample.udf.get('Genotyping results file id')
        if file_id:
            file_content = connection().get_file_contents(id=file_id)
            with open(output_file_name, 'w') as open_file:
                open_file.write(file_content)
            return output_file_name
        else:
            app_logger.warning('Cannot download genotype results for %s', sample_name)


def get_expected_yield_for_sample(sample_name):
    """
    Query the LIMS and return the number of bases expected for a sample
    :param sample_name: the sample name
    :return: number of bases
    """
    sample = get_sample(sample_name)
    if sample:
        nb_gb = sample.udf.get('Yield for Quoted Coverage (Gb)')
        if nb_gb:
            return nb_gb * 1000000000


def get_run(run_id):
    runs = connection().get_processes(type='AUTOMATED - Sequence', udf={'RunID': run_id})
    if not runs:
        return None
    elif len(runs) != 1:
        app_logger.error('%s runs found for %s', len(runs), run_id)
    return runs[0]


def route_samples_to_delivery_workflow(sample_names):
    lims = connection()
    samples = [get_sample(sample_name) for sample_name in sample_names]
    artifacts = [sample.artifact for sample in samples]
    workflow_uri = lims.get_uri('configuration', 'workflows', '401')
    lims.route_artifacts(artifacts, workflow_uri=workflow_uri)


def get_plate_id_and_well(sample_name):
    sample = get_sample(sample_name)
    if sample:
        plate, well = sample.artifact.location
        return plate.name, well
    else:
        return None, None


def get_sample_names_from_plate(plate_id):
    containers = connection().get_containers(type='96 well plate', name=plate_id)
    if containers:
        samples = {}
        placements = containers[0].get_placements()
        for key in placements:
            sample_name = placements.get(key).samples[0].name
            samples[key] = sanitize_user_id(sample_name)
        return list(samples.values())


def get_sample_names_from_project(project_id):
    samples = connection().get_samples(projectname=project_id)
    sample_names = [sample.name for sample in samples]
    return sample_names


def get_output_containers_from_sample_and_step_name(sample_name, step_name):
    lims = connection()
    sample = get_sample(sample_name)
    sample_name = sample.name
    containers = set()
    arts = [a.id for a in lims.get_artifacts(sample_name=sample_name)]
    prcs = lims.get_processes(type=step_name, inputartifactlimsid=arts)
    for prc in prcs:
        arts = prc.input_per_sample(sample_name)
        for art in arts:
            containers.update([o.container for o in prc.outputs_per_input(art.id, Analyte=True)])
    return containers


def get_samples_arrived_with(sample_name):
    sample = get_sample(sample_name)
    samples = set()
    if sample:
        container = sample.artifact.container
        if container.type.name == '96 well plate':
            samples = get_sample_names_from_plate(container.name)
    return samples


def get_samples_for_same_step(sample_name, step_name):
    sample = get_sample(sample_name)
    sample_name = sample.name
    containers = get_output_containers_from_sample_and_step_name(sample_name, step_name)
    samples = set()
    for container in containers:
        samples.update(get_sample_names_from_plate(container.name))
    return samples


def get_samples_genotyped_with(sample_name):
    return get_samples_for_same_step(sample_name, 'Genotyping Plate Preparation EG 1.0')


def get_samples_sequenced_with(sample_name):
    return get_samples_for_same_step(sample_name, 'Sequencing Plate Preparation EG 1.0')


def get_released_samples():
    released_samples = []
    processes = connection().get_processes(type='Data Release EG 1.0')
    for process in processes:
        for artifact in process.all_inputs():
            released_samples.extend([sanitize_user_id(s.name) for s in artifact.samples])

    return sorted(set(released_samples))


def get_sample_release_date(sample_id):
    s = get_sample(sample_id)
    if not s:
        return None
    procs = connection().get_processes(type='Data Release EG 1.0', inputartifactlimsid=s.artifact.id)
    if not procs:
        return None
    elif len(procs) != 1:
        app_logger.warning('%s Processes found for sample %s: Return latest one', len(procs), sample_id)
        return sorted([p.date_run for p in procs], reverse=True)[0]
    return procs[0].date_run


def get_project(project_id):
    lims = connection()
    projects = lims.get_projects(name=project_id)
    if len(projects) != 1:
        app_logger.warning('%s Project(s) found for name %s', len(projects), project_id)
        return None
    return projects[0]
