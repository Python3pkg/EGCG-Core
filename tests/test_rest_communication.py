import json
import pytest
from unittest.mock import patch
from tests import FakeRestResponse, TestEGCG
from egcg_core import rest_communication
from egcg_core.exceptions import RestCommunicationError
from egcg_core.config import cfg
cfg.load_config_file(TestEGCG.etc_config)


def rest_url(endpoint):
    return 'http://localhost:4999/api/0.1/' + endpoint + '/'


def ppath(extension):
    return 'egcg_core.rest_communication.' + extension


test_endpoint = 'an_endpoint'
test_request_content = {'data': ['some', {'test': 'content'}]}

patched_response = patch(
    'requests.request',
    return_value=FakeRestResponse(status_code=200, content=test_request_content)
)
auth = ('a_user', 'a_password')


def query_args_from_url(url):
    query_string = url.split('?')[1]
    d = {}
    for q in query_string.split('&'):
        k, v = q.split('=')
        if v.startswith('{') and v.endswith('}'):
            v = json.loads(v)
        d[k] = v

    return json.loads(json.dumps(d))


def test_api_url_query_strings():
    assert rest_communication.api_url('an_endpoint') == rest_url('an_endpoint')
    exp = '?where={"this":"that"}&embedded={"things":1}&aggregate=True&sort=-_created'
    obs = rest_communication.api_url(
        'an_endpoint',
        where={'this': 'that'},
        embedded={'things': 1},
        aggregate=True,
        sort='-_created'
    ).replace(rest_url('an_endpoint'), '')
    assert sorted(obs.lstrip('?').split('&')) == sorted(exp.lstrip('?').split('&'))


def test_parse_query_string():
    query_string = 'http://a_url?this=that&other={"another":"more"}'
    no_query_string = 'http://a_url'
    dodgy_query_string = 'http://a_url?this=that?other=another'

    p = rest_communication._parse_query_string

    assert p(query_string) == {'this': 'that', 'other': '{"another":"more"}'}
    assert p(no_query_string) == {}

    with pytest.raises(RestCommunicationError) as e:
        p(dodgy_query_string)
        assert str(e) == 'Bad query string: ' + dodgy_query_string

    with pytest.raises(RestCommunicationError) as e2:
        p(query_string, requires=['things'])
        assert str(e2) == query_string + ' did not contain all required fields: ' + str(['things'])


@patched_response
def test_req(mocked_response):
    json_content = ['some', {'test': 'json'}]

    response = rest_communication._req('METHOD', rest_url(test_endpoint), json=json_content)
    assert response.status_code == 200
    assert json.loads(response.content.decode('utf-8')) == response.json() == test_request_content
    mocked_response.assert_called_with('METHOD', rest_url(test_endpoint), auth=auth, json=json_content)


def test_get_documents_depaginate():
    docs = (
        FakeRestResponse(content={'data': ['this', 'that'], '_links': {'next': {'href': 'an_endpoint?max_results=101&page=2'}}}),
        FakeRestResponse(content={'data': ['other', 'another'], '_links': {'next': {'href': 'an_endpoint?max_results=101&page=3'}}}),
        FakeRestResponse(content={'data': ['more', 'things'], '_links': {}})
    )
    patched_req = patch(ppath('_req'), side_effect=docs)
    with patched_req as mocked_req:
        assert rest_communication.get_documents('an_endpoint', all_pages=True, max_results=101) == [
            'this', 'that', 'other', 'another', 'more', 'things'
        ]
        assert all([a[0][1].startswith(rest_url('an_endpoint')) for a in mocked_req.call_args_list])
        assert [query_args_from_url(a[0][1]) for a in mocked_req.call_args_list] == [
            {'page': '1', 'max_results': '101'},
            {'page': '2', 'max_results': '101'},
            {'page': '3', 'max_results': '101'}
        ]


@patched_response
def test_test_content(mocked_response):
    data = rest_communication.get_content(test_endpoint, max_results=100, where={'a_field': 'thing'})
    assert data == test_request_content
    assert mocked_response.call_args[0][1].startswith(rest_url(test_endpoint))
    assert query_args_from_url(mocked_response.call_args[0][1]) == {
        'max_results': '100', 'where': {'a_field': 'thing'}, 'page': '1'
    }


def test_get_documents():
    with patched_response:
        data = rest_communication.get_documents(test_endpoint, max_results=100, where={'a_field': 'thing'})
        assert data == test_request_content['data']


def test_get_document():
    expected = test_request_content['data'][0]
    with patched_response:
        observed = rest_communication.get_document(test_endpoint, max_results=100, where={'a_field': 'thing'})
        assert observed == expected


@patched_response
def test_post_entry(mocked_response):
    rest_communication.post_entry(test_endpoint, payload=test_request_content)
    mocked_response.assert_called_with('POST', rest_url(test_endpoint), auth=auth, json=test_request_content)


@patched_response
def test_put_entry(mocked_response):
    rest_communication.put_entry(test_endpoint, 'an_element_id', payload=test_request_content)
    mocked_response.assert_called_with('PUT', rest_url(test_endpoint) + 'an_element_id', auth=auth, json=test_request_content)


test_patch_document = {
    '_id': '1337', '_etag': 1234567, 'uid': 'a_unique_id', 'list_to_update': ['this', 'that', 'other']
}


@patch('egcg_core.rest_communication.get_document', return_value=test_patch_document)
@patched_response
def test_patch_entry(mocked_response, mocked_get_doc):
    patching_payload = {'list_to_update': ['another']}
    rest_communication.patch_entry(
        test_endpoint,
        payload=patching_payload,
        id_field='uid',
        element_id='a_unique_id',
        update_lists=['list_to_update']
    )

    mocked_get_doc.assert_called_with(test_endpoint, where={'uid': 'a_unique_id'})
    mocked_response.assert_called_with(
        'PATCH',
        rest_url(test_endpoint) + '1337',
        headers={'If-Match': 1234567},
        auth=auth,
        json={'list_to_update': ['this', 'that', 'other', 'another']}
    )


test_post_or_patch_payload = {'uid': '1337', 'list_to_update': ['more'], 'another_field': 'that'}
test_post_or_patch_payload_no_uid = {'list_to_update': ['more'], 'another_field': 'that'}
test_post_or_patch_doc = {
    'uid': 'a_uid', '_id': '1337', '_etag': 1234567, 'list_to_update': ['things'], 'another_field': 'this'
}


def test_post_or_patch():
    patched_post = patch(ppath('post_entry'), return_value=True)
    patched_patch = patch(ppath('_patch_entry'), return_value=True)
    patched_get = patch(ppath('get_document'), return_value=test_post_or_patch_doc)
    patched_get_none = patch(ppath('get_document'), return_value=None)

    with patched_get as mget, patched_patch as mpatch:
        success = rest_communication.post_or_patch(
            'an_endpoint',
            [test_post_or_patch_payload],
            id_field='uid',
            update_lists=['list_to_update']
        )
        mget.assert_called_with('an_endpoint', where={'uid': '1337'})
        mpatch.assert_called_with(
            'an_endpoint',
            test_post_or_patch_doc,
            test_post_or_patch_payload_no_uid,
            ['list_to_update']
        )
        assert success is True

    with patched_get_none as mget, patched_post as mpost:
        success = rest_communication.post_or_patch(
            'an_endpoint', [test_post_or_patch_payload], id_field='uid', update_lists=['list_to_update']
        )
        mget.assert_called_with('an_endpoint', where={'uid': '1337'})
        mpost.assert_called_with('an_endpoint', test_post_or_patch_payload)
        assert success is True
