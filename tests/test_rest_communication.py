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
    return 'egcg_core.rest_communication.Communicator.' + extension


test_endpoint = 'an_endpoint'
test_request_content = {'data': ['some', {'test': 'content'}]}
test_patch_document = {
    '_id': '1337', '_etag': 1234567, 'uid': 'a_unique_id', 'list_to_update': ['this', 'that', 'other']
}
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


class TestRestCommunication(TestEGCG):
    def setUp(self):
        self.comm = rest_communication.Communicator()

    def test_translate(self):
        assert self.comm._translate('None') == 'null'

    def test_api_url(self):
        assert self.comm.api_url('an_endpoint') == rest_url('an_endpoint')

    def test_parse_query_string(self):
        query_string = 'http://a_url?this=that&other={"another":"more"}&things=1'
        no_query_string = 'http://a_url'
        dodgy_query_string = 'http://a_url?this=that?other=another'

        p = self.comm._parse_query_string

        assert p(query_string) == {'this': 'that', 'other': '{"another":"more"}', 'things': '1'}
        assert p(no_query_string) == {}

        with pytest.raises(RestCommunicationError) as e:
            p(dodgy_query_string)
            assert str(e) == 'Bad query string: ' + dodgy_query_string

        with pytest.raises(RestCommunicationError) as e2:
            p(query_string, requires=['thangs'])
            assert str(e2) == query_string + " did not contain all required fields: ['thangs']"

    @patched_response
    def test_req(self, mocked_response):
        json_content = ['some', {'test': 'json'}]

        response = self.comm._req('METHOD', rest_url(test_endpoint), json=json_content)
        assert response.status_code == 200
        assert json.loads(response.content.decode('utf-8')) == response.json() == test_request_content
        mocked_response.assert_called_with('METHOD', rest_url(test_endpoint), auth=auth, json=json_content)

    def test_get_documents_depaginate(self):
        docs = (
            FakeRestResponse(content={'data': ['this', 'that'], '_links': {'next': {'href': 'an_endpoint?max_results=101&page=2'}}}),
            FakeRestResponse(content={'data': ['other', 'another'], '_links': {'next': {'href': 'an_endpoint?max_results=101&page=3'}}}),
            FakeRestResponse(content={'data': ['more', 'things'], '_links': {}})
        )
        patched_req = patch(ppath('_req'), side_effect=docs)
        with patched_req as mocked_req:
            assert self.comm.get_documents('an_endpoint', all_pages=True, max_results=101) == [
                'this', 'that', 'other', 'another', 'more', 'things'
            ]
            assert all([a[0][1].startswith(rest_url('an_endpoint')) for a in mocked_req.call_args_list])
            assert [a[1] for a in mocked_req.call_args_list] == [
                # Communicator.get_content passes ints
                {'params': {'page': 1, 'max_results': 101}, 'quiet': False},
                # url parsing passes strings, but requests removes the quotes anyway
                {'params': {'page': '2', 'max_results': '101'}, 'quiet': False},
                {'params': {'page': '3', 'max_results': '101'}, 'quiet': False}
            ]

    @patched_response
    def test_get_content(self, mocked_response):
        data = self.comm.get_content(test_endpoint, max_results=100, where={'a_field': 'thing'})
        assert data == test_request_content
        assert mocked_response.call_args[0][1].startswith(rest_url(test_endpoint))
        assert mocked_response.call_args[1] == {
            'auth': ('a_user', 'a_password'),
            'params': {
                'max_results': 100,
                'where': '{"a_field": "thing"}',
                'page': 1
            }
        }

    def test_get_documents(self):
        with patched_response:
            data = self.comm.get_documents(test_endpoint, max_results=100, where={'a_field': 'thing'})
            assert data == test_request_content['data']

    def test_get_document(self):
        expected = test_request_content['data'][0]
        with patched_response:
            observed = self.comm.get_document(test_endpoint, max_results=100, where={'a_field': 'thing'})
            assert observed == expected

    @patched_response
    def test_post_entry(self, mocked_response):
        self.comm.post_entry(test_endpoint, payload=test_request_content)
        mocked_response.assert_called_with('POST', rest_url(test_endpoint), auth=auth, json=test_request_content)

    @patched_response
    def test_put_entry(self, mocked_response):
        self.comm.put_entry(test_endpoint, 'an_element_id', payload=test_request_content)
        mocked_response.assert_called_with('PUT', rest_url(test_endpoint) + 'an_element_id', auth=auth, json=test_request_content)

    @patch(ppath('get_document'), return_value=test_patch_document)
    @patched_response
    def test_patch_entry(self, mocked_response, mocked_get_doc):
        patching_payload = {'list_to_update': ['another']}
        self.comm.patch_entry(
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

    def test_post_or_patch(self):
        test_post_or_patch_payload = {'uid': '1337', 'list_to_update': ['more'], 'another_field': 'that'}
        test_post_or_patch_payload_no_uid = {'list_to_update': ['more'], 'another_field': 'that'}
        test_post_or_patch_doc = {
            'uid': 'a_uid', '_id': '1337', '_etag': 1234567, 'list_to_update': ['things'], 'another_field': 'this'
        }
        patched_post = patch(ppath('post_entry'), return_value=True)
        patched_patch = patch(ppath('_patch_entry'), return_value=True)
        patched_get = patch(ppath('get_document'), return_value=test_post_or_patch_doc)
        patched_get_none = patch(ppath('get_document'), return_value=None)

        with patched_get as mget, patched_patch as mpatch:
            success = self.comm.post_or_patch(
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
            success = self.comm.post_or_patch(
                'an_endpoint', [test_post_or_patch_payload], id_field='uid', update_lists=['list_to_update']
            )
            mget.assert_called_with('an_endpoint', where={'uid': '1337'})
            mpost.assert_called_with('an_endpoint', test_post_or_patch_payload)
            assert success is True

    def test_token_auth(self):
        hashed_token = '{"some": "hashed"}.tokenauthentication'
        self.comm._auth = hashed_token
        with patched_response as p:
            self.comm._req('GET', self.comm.baseurl + 'an_endpoint')
            p.assert_called_with(
                'GET',
                self.comm.baseurl + 'an_endpoint',
                headers={'Authorization': 'Token ' + hashed_token}
            )


def test_default():
    d = rest_communication.default
    assert d.baseurl == 'http://localhost:4999/api/0.1'
    assert d.auth == ('a_user', 'a_password')
