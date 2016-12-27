'''
Created on 29 janv. 2016

@author: I079877
'''
if __name__ == '__main__':
    import sys
    import os
    dirname = os.path.dirname(os.path.realpath(__file__))
    sys.path.append(dirname + '/../../')
    sys.path.append(dirname + '/../../../externals')

import unittest
from mock import patch, Mock, MagicMock
from phases import  promote
from config import BuildConfig
import ConfigParser


class Test(unittest.TestCase):



    @patch('phases.promote.open')
    @patch('phases.promote.StagingAPI')
    @patch('phases.promote.log')
    def test_storePromoteProps_base(self, log_mock, StagingAPI_mock, open_mock):
        configParser_mock = Mock()
        ConfigParser.ConfigParser = MagicMock(return_value=configParser_mock)
        api = StagingAPI_mock()
        api.getrepositorystatus = MagicMock(return_value= {'repositoryURI': 'http://mo-49a5bdc06.mo.sap.corp:8081/nexus/content/repositories/repoIdtotto', 'releaseRepositoryId': 'deploy.milestones'})
        buildConfig = BuildConfig()
        buildConfig.promote_props_file = MagicMock(return_value= "promote.properties")
        buildConfig.version = MagicMock(return_value= "4.5.0")
        buildConfig.base_group = MagicMock(return_value= "com.sap.prd.dita")
        buildConfig.base_artifact = MagicMock(return_value= "com.sap.prd.dita.projectmap.api")

        promote._storePromoteProps(api, buildConfig, "toto", "a", "4.5.0")
        configParser_mock.set.assert_any_call('promote','release.metadata.url','http://mo-49a5bdc06.mo.sap.corp:8081/nexus/content/repositories/deploy.milestones/com/sap/prd/dita/com.sap.prd.dita.projectmap.api/4.5.0/com.sap.prd.dita.projectmap.api-4.5.0-releaseMetadata.zip')
        configParser_mock.set.assert_any_call('promote','base.group','com.sap.prd.dita')
        configParser_mock.set.assert_any_call('promote','base.artifact','com.sap.prd.dita.projectmap.api')
        configParser_mock.set.assert_any_call('promote','base.version','4.5.0')
        configParser_mock.set.assert_any_call('promote','base.treeish','a')

        assert(configParser_mock.set.call_count == 5)
        assert (open_mock.call_count == 1)

    @patch('phases.promote.open')
    @patch('phases.promote.StagingAPI')
    @patch('phases.promote.log')
    def test_storePromoteProps_nogav(self, log_mock, StagingAPI_mock, open_mock):
        configParser_mock = Mock()
        ConfigParser.ConfigParser = MagicMock(return_value=configParser_mock)
        api = StagingAPI_mock()
        api.getrepositorystatus = MagicMock(return_value= {'repositoryURI': 'http://mo-49a5bdc06.mo.sap.corp:8081/nexus/content/repositories/repoIdtotto', 'releaseRepositoryId': 'deploy.milestones'})
        buildConfig = BuildConfig()
        buildConfig.promote_props_file = MagicMock(return_value= "promote.properties")
        buildConfig.version = MagicMock(return_value= "4.5.0")
        buildConfig.base_group = MagicMock(return_value= None)
        buildConfig.base_artifact = MagicMock(return_value= None)

        promote._storePromoteProps(api, buildConfig, "toto", "a", "4.5.0")
        assert(configParser_mock.set.call_count == 2)
        assert (open_mock.call_count == 1)



    @patch('phases.promote.open')
    @patch('phases.promote.StagingAPI')
    @patch('phases.promote.log')
    def test_storePromoteProps_fail(self, log_mock, StagingAPI_mock, open_mock):
        configParser_mock = Mock()
        ConfigParser.ConfigParser = MagicMock(return_value=configParser_mock)
        api = StagingAPI_mock()
        api.getrepositorystatus = MagicMock(return_value= {})
        buildConfig = BuildConfig()
        buildConfig.promote_props_file = MagicMock(return_value= "promote.properties")
        buildConfig.version = MagicMock(return_value= "4.5.0")
        buildConfig.base_group = MagicMock(return_value= "com.sap.prd.dita")
        buildConfig.base_artifact = MagicMock(return_value= "com.sap.prd.dita.projectmap.api")

        promote._storePromoteProps(api, buildConfig, "toto", "a", "4.5.0")
        log_mock.error.assert_called_once_with('impossible to store promote properties. Can not have repository status: {} ')

        assert(configParser_mock.set.call_count == 0)
        assert (open_mock.call_count == 0)
if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(Test)
    unittest.TextTestRunner(verbosity=2).run(suite)

