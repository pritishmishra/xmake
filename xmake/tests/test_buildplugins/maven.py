if __name__ == '__main__':
    import sys
    import os
    dirname = os.path.dirname(os.path.realpath(__file__))
    sys.path.append(dirname + '/../../')
    sys.path.append(dirname + '/../../../externals')

import unittest
from buildplugins import maven
from config import BuildConfig
from mock import patch, Mock, MagicMock, call

class Test(unittest.TestCase):

    def return_signing_env(self,key):
        if key=='SIGNING_PROXY_URL': return 'https://signproxy.wdf.sap.corp:28443/sign'
        elif key=='SIGNING_KEYSTORE_PATH': return '/keystore'
        elif key=='SIGNING_KEYSTORE_PASSWORD': return 'KEYSTORE_PASSWORD'
        elif key=='SIGNING_TRUSTSTORE_PATH': return '/truststore'
        elif key=='SIGNING_TRUSTSTORE_PASSWORD': return 'TRUSTSTORE_PASSWORD'

    def test_check_version_compliance(self):

        matrix = ({"release":"indirect-shipment", "version": "0.6.3.25", "assert": True, "returnedValue": "0.6.3.25"},
                    {"release":"direct-shipment", "version": "1.0.3", "assert": True, "returnedValue": "1.0.3"},
                    {"release":"direct-shipment", "version": "v1.0.3", "assert": False, "returnedValue": "v1.0.3"},
                    {"release":"direct-shipment", "version": "0.6.3", "assert": False, "returnedValue": "0.6.3"},
                    {"release":"direct-shipment", "version": "1.2", "assert": False, "returnedValue": "1.2"},
                    {"release":"direct-shipment", "version": "1.2.3-sap", "assert": False, "returnedValue": "1.2.3-sap"},
                    {"release":"direct-shipment", "version": "1.2.3.sap", "assert": False, "returnedValue": "1.2.3.sap"},
                    {"release":"direct-shipment", "version": "1.2.3-sap-01", "assert": False, "returnedValue": "1.2.3-sap-01"},
                    {"release":"direct-shipment", "version": "1.2.3.sap-01", "assert": False, "returnedValue": "1.2.3.sap-01"},
                    {"release":"direct-shipment", "version": "300.2.1", "assert": True, "returnedValue": "300.2.1"},
                    {"release":"indirect-shipment", "version": "v1.0.3", "assert": False, "returnedValue": "v1.0.3"},
                    {"release":"indirect-shipment", "version": "1.2", "assert": True, "returnedValue": "1.2.0"},
                    {"release":"indirect-shipment", "version": "1.2.3-sap", "assert": True, "returnedValue": "1.2.3-sap"},
                    {"release":"indirect-shipment", "version": "1.2.3.sap", "assert": True, "returnedValue": "1.2.3.sap"},
                    {"release":"indirect-shipment", "version": "1.2.3-sap-01", "assert": True, "returnedValue": "1.2.3-sap-01"},
                    {"release":"indirect-shipment", "version": "1.2.3.sap-01", "assert": True, "returnedValue": "1.2.3.sap-01"},
                    {"release":"indirect-shipment", "version": "0.6.3", "assert": True, "returnedValue": "0.6.3"},
                    {"release":"indirect-shipment", "version": "0.6.3.25", "assert": True, "returnedValue": "0.6.3.25"},
                    {"release":"indirect-shipment", "version": "0.6.3-25", "assert": True, "returnedValue": "0.6.3"},
                  {"release":"indirect-shipment", "version": "9.5", "assert": True, "returnedValue": "9.5.0"},
                  {"release":"indirect-shipment", "version": "9.5-02", "assert": True, "returnedValue": "9.5.0"},
                  {"release":"indirect-shipment", "version": "23.502", "assert": True, "returnedValue": "23.502.0"},
                  {"release":"indirect-shipment", "version": "9.5-sap-02", "assert": True, "returnedValue": "9.5.0-sap-02"},
                  {"release":"indirect-shipment", "version": "1-sap.02", "assert": True, "returnedValue": "1.0.0-sap.02"},
                  {"release":"indirect-shipment", "version": "1.sap.02", "assert": True, "returnedValue": "1.0.0-sap.02"},
                  {"release":"indirect-shipment", "version": "1.1-sap.02", "assert": True, "returnedValue": "1.1.0-sap.02"},
                  {"release":"indirect-shipment", "version": "1.1.sap.02", "assert": True, "returnedValue": "1.1.0-sap.02"},

                  {"release":"indirect-shipment", "version": "1-sap", "assert": True, "returnedValue": "1.0.0-sap"},
                  {"release":"indirect-shipment", "version": "1.sap", "assert": True, "returnedValue": "1.0.0-sap"},
                  {"release":"indirect-shipment", "version": "1.1-sap", "assert": True, "returnedValue": "1.1.0-sap"},
                  {"release":"indirect-shipment", "version": "1.1.sap", "assert": True, "returnedValue": "1.1.0-sap"},
                  {"release":"indirect-shipment", "version": "0.1.110-sap", "assert": True, "returnedValue": "0.1.110-sap"},
                  {"release":"indirect-shipment", "version": "0.1.110.sap", "assert": True, "returnedValue": "0.1.110.sap"},

                  {"release":"indirect-shipment", "version": "1.2", "assert": True, "returnedValue": "1.2.0"},
                  {"release":"indirect-shipment", "version": "1.2.0.2", "assert": True, "returnedValue": "1.2.0.2"},
                  {"release":"indirect-shipment", "version": "2.18.2.v201304210537-sap-02", "assert": True, "returnedValue": "2.18.2.v201304210537-sap-02"},
                  {"release":"indirect-shipment", "version": "2.18.2.201304210537-sap-02", "assert": True, "returnedValue": "2.18.2.201304210537-sap-02"},
                  {"release":"indirect-shipment", "version": "2.18.2-201304210537-sap-02", "assert": True, "returnedValue": "2.18.2-201304210537-sap-02"},
                  {"release":"indirect-shipment", "version": "1.02", "assert": True, "returnedValue": "1.02.0"},
                  {"release":"indirect-shipment", "version": "300.2.1", "assert": True, "returnedValue": "300.2.1"},
                  {"release":"indirect-shipment", "version": "300.02", "assert": True, "returnedValue": "300.02.0"}

                )


        cfg =  BuildConfig()
        cfg._genroot_dir = r"C:\Users\i079877\TEMP"
        m= maven.build(cfg)

        for elem in matrix :
            cfg.set_base_version(elem["version"])
            cfg._release = elem["release"]
            status = m._check_project_version_compliance()
            self.assertEqual(status[0], elem["assert"], "expected {} but got {} for input {}/{}".format(elem["assert"], status[0] , elem["release"], elem["version"]))
            self.assertEqual(cfg.base_version(), elem["returnedValue"],"expected {} but got {} for input {}/{}".format(elem["returnedValue"], cfg.base_version(), elem["release"], elem["version"]))

    @patch('buildplugins.maven.log')
    @patch('buildplugins.maven.tempfile')
    @patch('buildplugins.maven.join')
    @patch('buildplugins.maven.OS_Utils')
    @patch('buildplugins.maven.shutil')
    @patch('buildplugins.maven.os')
    def test_copy_src_dir_to_must_keep_target_dir(self, os_mock, shutil_mock, OS_Utils_mock, join_mock, tempfile_mock, log_mock):

        #use case target is in directory todir
        def existsIf(dir):
            return True if (dir == 'todir' or dir == 'targetdir') else False
        def return_dir(dir1, dir2):
            if (dir1=='todir' and dir2 == 'target'):
                return 'targetdir'
            if (dir1=='tempdir' and dir2 == 'target'):
                return 'temptargetdir'
            return ''

        os_mock.path.exists = MagicMock(side_effect=existsIf)
        os_mock.path.join = MagicMock(side_effect=return_dir)
        tempfile_mock.mkdtemp = MagicMock(return_value='tempdir')

        m = maven.build(MagicMock())
        m._copy_src_dir_to('todir')
        #ensure target was copied
        shutil_mock.copytree.assert_has_calls([call('targetdir', 'temptargetdir'), call('temptargetdir', 'targetdir')])
        shutil_mock.rmtree.assert_called_once_with('temptargetdir')
        os_mock.mkdir.assert_called_once_with('todir')

        #use case target is not in directory todir
        def existsIf(dir):
            return True if (dir == 'todir') else False

        os_mock.path.exists = MagicMock(side_effect=existsIf)

        os_mock.reset_mock()
        shutil_mock.reset_mock()
        tempfile_mock.mkdtemp.reset_mock()

        m = maven.build(MagicMock())
        m._copy_src_dir_to('todir')
        #ensure target was not copied
        assert tempfile_mock.mkdtemp.call_count == 0
        assert shutil_mock.rmtree.call_count == 0
        os_mock.mkdir.assert_called_once_with('todir')

        #use case no directory at all
        os_mock.path.exists = MagicMock(return_value=False)

        os_mock.reset_mock()
        shutil_mock.reset_mock()
        tempfile_mock.mkdtemp.reset_mock()

        m = maven.build(MagicMock())
        m._copy_src_dir_to('todir')
        #ensure target was not copied
        assert tempfile_mock.mkdtemp.call_count == 0
        assert shutil_mock.rmtree.call_count == 0
        os_mock.mkdir.assert_called_once_with('todir')

    @patch('buildplugins.maven.log')
    @patch('buildplugins.maven.os')
    def test__maven_jarsigner_plugin_options_releaseBuild(self,os_mock, log_mock):
        os_mock.getenv=MagicMock(side_effect=self.return_signing_env)
        os_mock.path.exists = MagicMock(return_value=True)
        os_mock.path.isdir = MagicMock(return_value=False)
        cfg =  BuildConfig()
        cfg._genroot_dir = r"C:\Users\i079877\TEMP"
        m=maven.build(cfg)
        value=m._maven_jarsigner_plugin_options(True)
        to_be_returned=['-Dcodesign.sap.realcodesigning=true', '-Dcodesign.sap.server.url=https://signproxy.wdf.sap.corp:28443/sign', '-Dcodesign.sap.ssl.keystore=/keystore', '-Dcodesign.sap.ssl.keystore.pass=KEYSTORE_PASSWORD', '-Dcodesign.sap.ssl.truststore=/truststore', '-Dcodesign.sap.ssl.truststore.pass=TRUSTSTORE_PASSWORD']
        if value!=to_be_returned: raise Exception("Returned a bad value:"+str(value))

    @patch('buildplugins.maven.log')
    @patch('buildplugins.maven.os')
    def test__maven_jarsigner_plugin_options_disabled(self,os_mock, log_mock):
        os_mock.getenv=MagicMock(side_effect=self.return_signing_env)
        os_mock.path.exists = MagicMock(return_value=True)
        os_mock.path.isdir = MagicMock(return_value=False)
        cfg =  BuildConfig()
        cfg._genroot_dir = r"C:\Users\i079877\TEMP"
        m=maven.build(cfg)
        value=m._maven_jarsigner_plugin_options(False)
        to_be_returned=['-Dcodesign.sap.realcodesigning=false', '-Dcodesign.sap.server.url=https://signproxy.wdf.sap.corp:28443/sign', '-Dcodesign.sap.ssl.keystore=/keystore', '-Dcodesign.sap.ssl.keystore.pass=KEYSTORE_PASSWORD', '-Dcodesign.sap.ssl.truststore=/truststore', '-Dcodesign.sap.ssl.truststore.pass=TRUSTSTORE_PASSWORD']
        if value!=to_be_returned: raise Exception("Returned a bad value:"+str(value))

    @patch('buildplugins.maven.log')
    @patch('buildplugins.maven.os')
    def test__maven_jarsigner_plugin_options_noenv(self,os_mock, log_mock):
        os_mock.getenv=MagicMock(return_value=None)
        os_mock.path.exists = MagicMock(return_value=True)
        os_mock.path.isdir = MagicMock(return_value=False)
        cfg =  BuildConfig()
        cfg._genroot_dir = r"C:\Users\i079877\TEMP"
        m=maven.build(cfg)
        value=m._maven_jarsigner_plugin_options(False)
        if value!=[]: raise Exception("Returned a bad value:"+str(value))

    @patch('buildplugins.maven.log')
    @patch('buildplugins.maven.join')
    @patch('buildplugins.maven.ET')
    def test__get_version_from_effective_pom(self, ET_mock, join_mock, log_mock):
        def t(suffix=''):
            def a(key):
                mock = MagicMock()
                if 'version' in key:
                    mock.text = '1.0.0{}'.format('-' + suffix if suffix else '')
                elif 'groupId' in key:
                    mock.text = 'group'
                elif 'artifactId' in key:
                    mock.text = 'artifact'
                else:
                    mock.text = ''

                return mock

            return a

        root_mock = MagicMock()
        root_mock.tag.split = MagicMock(return_value=['', 'project'])
        pom_mock = MagicMock()
        pom_mock.getroot = MagicMock(return_value=root_mock)
        ET_mock.parse = MagicMock(return_value=pom_mock)

        cfg = BuildConfig()
        cfg._genroot_dir = ''
        m = maven.build(cfg)
        m._mvn = MagicMock()

        # NO SUFFIX
        pom_mock.find = MagicMock(side_effect=t())
        m._get_version_from_effective_pom()
        assert cfg.version() == '1.0.0'

        # SUFFIX in pom version
        # SNAPSHOT
        pom_mock.find = MagicMock(side_effect=t('SNAPSHOT'))
        m._get_version_from_effective_pom()
        assert cfg.version() == '1.0.0'

        # RELEASE
        pom_mock.find = MagicMock(side_effect=t('RELEASE'))
        m._get_version_from_effective_pom()
        assert cfg.version() == '1.0.0'

        # MILESTONE
        pom_mock.find = MagicMock(side_effect=t('MILESTONE'))
        m._get_version_from_effective_pom()
        assert cfg.version() == '1.0.0'

        # NO SUFFIX in pom version but in build_config._version_suffix
        pom_mock.find = MagicMock(side_effect=t())

        # BLALA
        cfg._version_suffix = 'BLABLA'
        m._get_version_from_effective_pom()
        assert cfg.version() == '1.0.0-BLABLA'

if __name__ == '__main__':
    unittest.main()
