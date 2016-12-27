if __name__ == '__main__':
    import sys
    import os
    dirname = os.path.dirname(os.path.realpath(__file__))
    sys.path.append(dirname + '/../')
    sys.path.append(dirname + '/../../externals')

import unittest
from mock import patch, Mock, MagicMock, call
from nexusstaging import StagingAPI
import urllib2

class Test(unittest.TestCase):

    def test_create_staging_api_instance_with_missing_profile_id(self):
      with self.assertRaisesRegexp(Exception, 'profileId is not set'):
        StagingAPI('http://here/my/rest/url')

    def test_create_staging_api_instance_with_profile_id_in_nexus_rest_service_url(self):
      StagingAPI('http://here/my/rest/url/profiles/myProfileId')

    def test_create_staging_api_instance_with_profile_id_provided_explicitly(self):
      StagingAPI('http://here/my/rest_url', profileId='myProfile')

    def test_create_staging_api_instance_with_non_matching_profile_ids_provided_via_nexus_rest_service_url_and_explicitly(self):
      with self.assertRaisesRegexp(Exception, 'profileId provided explicitly (.*) and also implicitely via nexus url (.*)\. The values does not match.'):
        StagingAPI('http://here/my/rest_url/profiles/myProfile1', profileId='myProfile2')

    def test_create_staging_api_instance_with_matching_profile_ids_provided_via_nexus_rest_service_url_and_explicitly(self):
      StagingAPI('http://here/my/rest_url/profiles/myProfile', profileId='myProfile')

    @patch('nexusstaging.urllib2')
    @patch('nexusstaging.StagingAPI.getrepositorystatus')
    @patch('nexusstaging.StagingAPI._request')
    @patch('nexusstaging.log')
    def test_start(self, log_mock, _request_mock, getrepositorystatus_mock, urllib2_mock):
        _request_mock.return_value = '<response><data><stagedRepositoryId>MyRepoId</stagedRepositoryId></data></response>'
        getrepositorystatus_mock.return_value = {'notifications': '0', 'type': 'open'}

        api = StagingAPI('http://here/my/rest/url', profileId='blabla')
        result = api.start({'description': 'My first staging repo'})

        getrepositorystatus_mock.assert_called_once_with('MyRepoId', None)
        assert result == 'MyRepoId'

    @patch('nexusstaging.urllib2')
    @patch('nexusstaging.StagingAPI._request')
    @patch('nexusstaging.log')
    def test_drop(self, log_mock, _request_mock, urllib2_mock):

        api = StagingAPI('http://here/my/rest/url', profileId='blabla')
        _request_mock.side_effect = ['', 404]

        result = api.drop('MyRepoId')
        assert (_request_mock.call_count == 2)
        assert result == True

    @patch('nexusstaging.urllib2')
    @patch('nexusstaging.StagingAPI.getrepositorystatus')
    @patch('nexusstaging.StagingAPI._request')
    @patch('nexusstaging.log')
    def test_finish(self, log_mock, _request_mock, getrepositorystatus_mock, urllib2_mock):
        getrepositorystatus_mock.return_value = {'notifications': '0', 'type': 'closed'}
        _request_mock.return_value = ''

        api = StagingAPI('http://here/my/rest/url', profileId='blabla')
        result = api.finish('MyRepoId')

        getrepositorystatus_mock.assert_called_once_with('MyRepoId')
        assert (_request_mock.call_count == 1)
        assert result == True

    @patch('nexusstaging.urllib2')
    @patch('nexusstaging.log')
    def test_promote(self, log_mock, urllib2_mock):

        api = StagingAPI('http://here/my/rest/url', profileId='blabla')

        api.getrepositorystatus = Mock(side_effect=[{'notifications': '0', 'type': 'released'}])
        api._request =  Mock(side_effect=[''])
        #api._requestManyTimes = Mock(side_effect=[True])

        result = api.promote('MyRepoId', '')

        assert (api.getrepositorystatus.called_once_with('MyRepoId'))
        assert (api._request.call_count == 1)
        #assert (api._requestManyTimes.call_count == 1)
        assert result == True

    @patch('nexusstaging.urllib2')
    @patch('nexusstaging.open')
    @patch('nexusstaging.MultiPartForm')
    @patch('nexusstaging.log')
    def test_upload(self, log_mock, multiPartForm_mock, open_mock, urllib2_mock):
        api = StagingAPI('http://here/my/rest/url', profileId='blabla')
        api._request = Mock(side_effect=['{"repositoryId": "MyRepoId"}'])
        api._requestManyTimes = Mock(side_effect=[True])
        result = api.upload('MyRepoId', {'group': 'mygroup',
                                         'artifact': 'myartifact',
                                         'version': '1.0',
                                         'package': 'jar',
                                         'classifier': 'c',
                                         'extension': 'e',
                                         'filename': 'myartifact.jar',
                                         'path': '/home/me/repo/mygroup/myartifact/1.0/myartifact.jar',
                                         'relpath': 'mygroup/myartifact/1.0/myartifact.jar'
                                        }, 'blabla')
        assert (open_mock.call_count == 1)
        assert (api._request.call_count == 1)
        assert result == 'MyRepoId'

    @patch('nexusstaging.urllib2')
    @patch('nexusstaging.open')
    @patch('nexusstaging.MultiPartForm')
    @patch('nexusstaging.log')
    def test_deployByRepositoryId(self, log_mock, multiPartForm_mock, open_mock, urllib2_mock):
        api = StagingAPI('http://here/my/rest/url', profileId='blabla')
        api._formbased_post_file = Mock(side_effect=[201])
        api.repository_content = Mock(side_effect=[[{'text': 'myartifact.jar'}]])
        result = api.deployByRepositoryId('MyRepoId', {'group': 'mygroup',
                                         'artifact': 'myartifact',
                                         'version': '1.0',
                                         'package': 'jar',
                                         'classifier': 'c',
                                         'extension': 'e',
                                         'filename': 'myartifact.jar',
                                         'path': '/home/me/repo/mygroup/myartifact/1.0/myartifact.jar',
                                         'relpath': 'mygroup/myartifact/1.0/myartifact.jar'
                                        }, 'blabla')
        assert (open_mock.call_count == 1)
        assert (api._formbased_post_file.call_count == 1)
        assert (api.repository_content.call_count == 1)
        assert result == True

    @patch('nexusstaging.log')
    def test_request_with_headers_and_bytearray(self, log_mock):
        single_build_opener_mock = MagicMock()
        urllib2.build_opener = MagicMock(return_value = single_build_opener_mock)
        single_request_mock = MagicMock()
        urllib2.Request = MagicMock(return_value = single_request_mock)
        req_handler_mock = MagicMock()
        req_handler_mock.read = MagicMock(return_value='response!!')
        req_handler_mock.getcode = MagicMock(return_value=200)
        single_build_opener_mock.open = MagicMock(return_value=req_handler_mock)

        url = 'http://my/prefered/url'
        httpHeaders = {'h1': 'value_h1', 'h2': 'value_h2'}
        byteRequest = bytearray((1,2,3,4))

        api = StagingAPI('http://here/my/rest/url', profileId='blabla')
        responseValue = api._request(url, httpHeaders = httpHeaders, byteRequest=byteRequest)

        assert (urllib2.build_opener.call_count == 1)
        assert (urllib2.Request.called_once_with(url, data=byteRequest))
        assert (httpHeaders['Content-Length']=='{}'.format(len(byteRequest)))
        assert (single_build_opener_mock.open.call_count == 1)
        single_build_opener_mock.open.assert_called_once_with(single_request_mock, timeout=1800)

        assert (req_handler_mock.read.call_count == 1)
        assert (req_handler_mock.getcode.call_count == 1)
        assert (responseValue=='response!!')

        responseValue = api._request(url, httpHeaders = httpHeaders, returnOnlyHttpCode=True, byteRequest=byteRequest)
        assert (responseValue==200)

        # error cases
        errorToRaise = urllib2.HTTPError(url, 400, '', httpHeaders, None)
        errorToRaise.read = MagicMock()
        single_build_opener_mock.open = Mock(side_effect = errorToRaise)

        log_mock.reset()
        responseValue = api._request(url, httpHeaders = httpHeaders, byteRequest=byteRequest)
        assert (log_mock.error.call_count>0)
        assert (responseValue == None)

        log_mock.reset()
        responseValue = api._request(url, httpHeaders = httpHeaders, byteRequest=bytearray(''.join(str(x) for x in range(0,1000))))
        assert (log_mock.error.call_count>0)
        assert (responseValue == None)

        log_mock.reset()
        responseValue = api._request(url, httpHeaders = httpHeaders, returnOnlyHttpCode=True, byteRequest=byteRequest)
        assert (log_mock.error.call_count>0)
        assert (responseValue == 400)

        errorToRaise = urllib2.URLError('blabla')
        single_build_opener_mock.open = Mock(side_effect = errorToRaise)
        log_mock.reset()
        responseValue = api._request(url, httpHeaders = httpHeaders, byteRequest=byteRequest)
        assert (log_mock.error.call_count>0)
        assert (responseValue == None)

        errorToRaise = urllib2.URLError('blabla')
        single_build_opener_mock.open = Mock(side_effect = errorToRaise)
        log_mock.reset()
        responseValue = api._request(url, httpHeaders = httpHeaders, returnOnlyHttpCode=True, byteRequest=byteRequest)
        assert (log_mock.error.call_count>0)
        assert (responseValue == None)

    @patch('nexusstaging.urllib2')
    @patch('nexusstaging.log')
    def test_request_with_bytearray(self, log_mock, urllib2_mock):
        single_request_mock = MagicMock()
        urllib2_mock.Request = MagicMock(return_value=single_request_mock)
        single_build_opener_mock = MagicMock()
        urllib2_mock.build_opener = MagicMock(return_value = single_build_opener_mock)
        req_handler_mock = MagicMock()
        req_handler_mock.read = MagicMock(return_value='response!!')
        single_build_opener_mock.open = MagicMock(return_value=req_handler_mock)

        url = 'http://my/prefered/url'
        byteRequest = bytearray((1,2,3,4))

        api = StagingAPI('http://here/my/rest/url', profileId='blabla')
        responseValue = api._request(url, byteRequest=byteRequest)

        assert (urllib2_mock.build_opener.call_count == 1)
        assert (urllib2_mock.Request.called_once_with(url, data=byteRequest))

        assert single_request_mock.add_header.called_once_with('Content-Length', '{}'.format(len(byteRequest)))
        assert (single_build_opener_mock.open.call_count == 1)

        assert (req_handler_mock.read.call_count == 1)
        assert (req_handler_mock.getcode.call_count == 1)
        assert (responseValue=='response!!')

if __name__ == '__main__':
    unittest.main()
