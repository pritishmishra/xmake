import io,os

if __name__ == '__main__':
    import sys
    dirname = os.path.dirname(os.path.realpath(__file__))
    sys.path.append(dirname + '/../../')
    sys.path.append(dirname + '/../../../externals')

import unittest
from buildplugins import dockerbuild
from config import BuildConfig
from mock import patch, MagicMock, call

class Test(unittest.TestCase):
    def _test_tag_image(self,version,forced,docker_mock):
        def docker(args,handler=None,dir=None,echo=True,home=None):
            if len(args) and '-v' in args:
                handler("Docker version "+version+", build ab77bde/"+version)
        docker_mock.docker=MagicMock(side_effect=docker)

        def tag_name(build_cfg,gid,aid,tmp=False):
            return "tag_name"
        docker_mock.tag_name=MagicMock(side_effect=tag_name)

        cfg =  BuildConfig()
        cfg._runtime = "linux"
        cfg.cfg_dir = MagicMock(return_value=os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'samples'))
        cfg.component_dir = MagicMock(return_value=os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'samples','docker'))

        d=dockerbuild.build(cfg)
        d.tag_image(True)

        docker_mock.tag_image.assert_called_once_with(None, "tag_name", forced)

    @patch('buildplugins.dockerbuild.open')
    @patch('buildplugins.dockerbuild.shutil')
    @patch('buildplugins.dockerbuild.log')
    @patch('buildplugins.dockerbuild.docker')
    @patch('buildplugins.maven.os')
    def test_tag_image_1_8_2_e17(self, os_mock, docker_mock, log_mock, shutil_mock, open_mock):
        self._test_tag_image("1.8.2-el7",True,docker_mock)

    @patch('buildplugins.dockerbuild.open')
    @patch('buildplugins.dockerbuild.shutil')
    @patch('buildplugins.dockerbuild.log')
    @patch('buildplugins.dockerbuild.docker')
    @patch('buildplugins.maven.os')
    def test_tag_image_1_9_1(self, os_mock, docker_mock, log_mock, shutil_mock, open_mock):
        self._test_tag_image("1.9.1",True,docker_mock)

    @patch('buildplugins.dockerbuild.open')
    @patch('buildplugins.dockerbuild.shutil')
    @patch('buildplugins.dockerbuild.log')
    @patch('buildplugins.dockerbuild.docker')
    @patch('buildplugins.maven.os')
    def test_tag_image_1_10_0(self, os_mock, docker_mock, log_mock, shutil_mock, open_mock):
        self._test_tag_image("1.10.0",False,docker_mock)

    @patch('buildplugins.dockerbuild.open')
    @patch('buildplugins.dockerbuild.shutil')
    @patch('buildplugins.dockerbuild.log')
    @patch('buildplugins.dockerbuild.docker')
    @patch('buildplugins.maven.os')
    def test_tag_image_1_12_0(self, os_mock, docker_mock, log_mock, shutil_mock, open_mock):
        self._test_tag_image("1.12.0",False,docker_mock)

    #@patch('buildplugins.dockerbuild.shutil')
    #@patch('buildplugins.dockerbuild.docker')
    #def test_check_from_replacement(self, docker_mock, shutil_mock):
    #    cfg = BuildConfig()
    #    cfg._runtime = "linux"
    #    cfg.cfg_dir = MagicMock(return_value=os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'samples'))
    #    cfg.component_dir = MagicMock(return_value=os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'samples','docker'))
    #    cfg.import_repos = MagicMock(return_value=['artifactory.wdf.sap.corp:50001'])
    #    
    #    output_fake_file = MagicMock()
    #    
    #    def foo(arg, arg2=''):
    #        if arg is 'Dockerfile':
    #            return io.BytesIO('FROM docker.wdf.sap.corp:50001/com-sap-prd-docker/rh70lib2hanabase:1.0')
    #        return output_fake_file
    #
    #    with patch('buildplugins.dockerbuild.open', side_effect=foo, create=True):
    #        dockerbuild.build(cfg)
    #    calls = [ call.__enter__(),
    #              call.__enter__().write('FROM artifactory.wdf.sap.corp:50001/com-sap-prd-docker/rh70lib2hanabase:1.0'),
    #              call.__exit__(None, None, None) ]
    #    output_fake_file.assert_has_calls(calls)

if __name__ == '__main__':
    unittest.main()
