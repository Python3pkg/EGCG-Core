import requests
from urllib.parse import urljoin
from egcg_core.config import cfg
from egcg_core.app_logging import logging_default as log_cfg
from egcg_core.exceptions import RestCommunicationError

cfg = cfg['rest_api']
app_logger = log_cfg.get_logger(__name__)

table = {' ': '', '\'': '"', 'None': 'null'}


def _translate(s):
    for k, v in table.items():
        s = s.replace(k, v)
    return s


def api_url(endpoint, **query_args):
    url = '{base_url}/{endpoint}/'.format(
        base_url=cfg['url'].rstrip('/'), endpoint=endpoint
    )
    if query_args:
        query = '?' + '&'.join(['%s=%s' % (k, v) for k, v in query_args.items()])
        url += _translate(query)
    return url


def _parse_query_string(query_string, requires=None):
    if '?' not in query_string:
        return {}
    if query_string.count('?') != 1:
        raise RestCommunicationError('Bad query string: ' + query_string)
    href, query = query_string.split('?')
    query = dict([x.split('=') for x in query.split('&')])
    if requires and not all([r in query for r in requires]):
        raise RestCommunicationError('%s did not contain all required fields: %s' % (query_string, requires))
    return query


def _req(method, url, quiet=False, **kwargs):
    auth = None
    if 'username' in cfg and 'password' in cfg:
        auth = (cfg['username'], cfg['password'])

    r = requests.request(method, url, auth=auth, **kwargs)
    # e.g: 'POST <url> ({"some": "args"}) -> {"some": "content"}. Status code 201. Reason: CREATED
    report = '%s %s (%s) -> %s. Status code %s. Reason: %s' % (
        r.request.method, r.request.path_url, kwargs, r.content.decode('utf-8'), r.status_code, r.reason
    )
    if r.status_code in (200, 201):
        if not quiet:
            app_logger.debug(report)
    elif r.status_code == 401:
        raise RestCommunicationError('Invalid auth credentials')
    else:
        app_logger.error(report)
    return r


def get_content(endpoint, paginate=True, quiet=False, **query_args):
    if paginate:
        query_args.update(
            max_results=query_args.pop('max_results', 100),  # default to page size of 100
            page=query_args.pop('page', 1)
        )
    url = api_url(endpoint, **query_args)
    return _req('GET', url, quiet=quiet).json()


def get_documents(endpoint, paginate=True, all_pages=False, quiet=False, **query_args):
    content = get_content(endpoint, paginate, quiet, **query_args)
    elements = content['data']

    if all_pages and 'next' in content['_links']:
        next_query = _parse_query_string(content['_links']['next']['href'], requires=('max_results', 'page'))
        query_args.update(next_query)
        elements.extend(get_documents(endpoint, all_pages=True, quiet=quiet, **query_args))

    return elements


def get_document(endpoint, idx=0, **query_args):
    documents = get_documents(endpoint, **query_args)
    if documents:
        return documents[idx]
    else:
        app_logger.warning('No document found in endpoint %s for %s', endpoint, query_args)


def post_entry(endpoint, payload):
    r = _req('POST', api_url(endpoint), json=payload)
    if r.status_code != 200:
        return False
    return True


def put_entry(endpoint, element_id, payload):
    r = _req('PUT', urljoin(api_url(endpoint), element_id), json=payload)
    if r.status_code != 200:
        return False
    return True


def _patch_entry(endpoint, doc, payload, update_lists=None):
    """
    Patch a specific database item (specified by doc) with the given data payload.
    :param str endpoint:
    :param dict doc: The entry in the database to patch (contains the relevant _id and _etag)
    :param dict payload: Data with which to patch doc
    :param list update_lists: Doc items listed here will be appended rather than replaced by the patch
    """
    url = urljoin(api_url(endpoint), doc['_id'])
    _payload = dict(payload)
    headers = {'If-Match': doc.get('_etag')}
    if update_lists:
        for l in update_lists:
            content = doc.get(l, [])
            new_content = [x for x in _payload.get(l, []) if x not in content]
            _payload[l] = content + new_content
    r = _req('PATCH', url, headers=headers, json=_payload)
    if r.status_code == 200:
        return True
    return False


def patch_entry(endpoint, payload, id_field, element_id, update_lists=None):
    """
    Retrieve a document at the given endpoint with the given unique ID, and patch it with some data.
    :param str endpoint:
    :param dict payload:
    :param str id_field: The name of the unique identifier (e.g. 'run_element_id', 'proc_id', etc.)
    :param element_id: The value of id_field to retrieve (e.g. '160301_2_ATGCATGC')
    :param list update_lists:
    """
    doc = get_document(endpoint, where={id_field: element_id})
    if doc:
        return _patch_entry(endpoint, doc, payload, update_lists)
    return False


def patch_entries(endpoint, payload, update_lists=None, **query_args):
    """
    Retrieve many documents and patch them all with the same data.
    :param str endpoint:
    :param dict payload:
    :param list update_lists:
    :param query_args: Database query args to pass to get_documents
    """
    docs = get_documents(endpoint, **query_args)
    if docs:
        success = True
        nb_docs = 0
        for doc in docs:
            if _patch_entry(endpoint, doc, payload, update_lists):
                nb_docs += 1
            else:
                success = False
        app_logger.info('Updated %s documents matching %s', nb_docs, query_args)
        return success
    return False


def post_or_patch(endpoint, input_json, id_field=None, update_lists=None):
    """
    For each document supplied, either post to the endpoint if the unique id doesn't yet exist there, or
    patch if it does.
    :param str endpoint:
    :param input_json: A single document or list of documents to post or patch to the endpoint.
    :param str id_field: The field to use as the unique ID for the endpoint.
    :param list update_lists:
    """
    success = True
    for payload in input_json:
        _payload = dict(payload)
        doc = get_document(endpoint, where={id_field: _payload[id_field]})
        if doc:
            _payload.pop(id_field)
            s = _patch_entry(endpoint, doc, _payload, update_lists)
        else:
            s = post_entry(endpoint, _payload)
        success = success and s
    return success
