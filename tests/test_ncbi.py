import sqlite3
from unittest.mock import patch
from tests import FakeRestResponse
from egcg_core import ncbi


fetch_from_eutils = ncbi._fetch_from_eutils
fetch_from_cache = ncbi._fetch_from_cache
cache_species = ncbi._cache_species


def reset_cache():
    ncbi.data_cache = sqlite3.connect(':memory:')
    ncbi.cursor = ncbi.data_cache.cursor()
    ncbi.init_tables()


def test_fetch_from_eutils():
    ncbi_search_data = {'esearchresult': {'idlist': ['1337']}}
    ncbi_fetch_data = '''
        <ScientificName>Genus species</ScientificName>
        <OtherNames><CommonName>a common name</CommonName></OtherNames>
        <Rank>species</Rank>
    '''

    patched_get = patch(
        'egcg_core.ncbi.requests.get',
        side_effect=(
            FakeRestResponse(content=ncbi_search_data),
            FakeRestResponse(content=ncbi_fetch_data),
            FakeRestResponse(content=ncbi_fetch_data),
            FakeRestResponse(content=ncbi_fetch_data)
        )
    )

    with patched_get as mocked_get:
        obs = fetch_from_eutils('a_species')
        assert obs == ('1337', 'Genus species', 'a common name')
        mocked_get.assert_any_call(
            'http://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi',
            params={'db': 'Taxonomy', 'term': 'a_species', 'retmode': 'JSON'}
        )
        mocked_get.assert_any_call(
            'http://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi',
            params={'db': 'Taxonomy', 'id': '1337'}
        )


def test_cache():
    assert fetch_from_cache('a species') is None
    cache_species('a species', '1337', 'Scientific name', 'a species')
    assert fetch_from_cache('a species') == ('a species', '1337', 'Scientific name', 'a species')
    reset_cache()


def test_get_species_name():
    fetch = 'egcg_core.ncbi._fetch_from_eutils'
    assert fetch_from_cache('a species') is None
    with patch(fetch, return_value=(None, None, None)):
        assert ncbi.get_species_name('a species') is None
        assert fetch_from_cache('a species') is None
    reset_cache()
    with patch(fetch, return_value=('1337', 'Scientific name', 'a species')):
        assert ncbi.get_species_name('a species') == 'Scientific name'
        assert fetch_from_cache('a species') == ('a species', '1337', 'Scientific name', 'a species')
    reset_cache()
