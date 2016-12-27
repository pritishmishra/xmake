'''
Created on 29 janv. 2016

@author: I079877
'''
import os

if __name__ == '__main__':
    import sys
    dirname = os.path.dirname(os.path.realpath(__file__))
    sys.path.append(dirname + '/../../')
    sys.path.append(dirname + '/../../../externals')

import unittest
from mock import patch, Mock, MagicMock, call
from phases import  prelude
from config import BuildConfig
import ConfigParser


class Test(unittest.TestCase):

    @patch('phases.prelude.os')
    def test_create_gendir(self, os_mock):
        my_env = {}

        def setitem(name, val):
            my_env[name] = val

        buildConfig = BuildConfig()

        buildConfig._genroot_dir = r"C:\Users\i079877\TEMP"
        prelude.exists = MagicMock(return_value=False)
        prelude.makedirs = MagicMock(return_value=None)
        os_mock.environ.__setitem__.side_effect = setitem
        prelude.create_gendir(buildConfig)

        assert(prelude.exists.call_count == 2)
        assert(prelude.makedirs.call_count == 2)
        os_mock.environ.__setitem__.assert_has_calls([call('TMP', buildConfig.temp_dir()), call('TEMP', buildConfig.temp_dir()), call('TMPDIR', buildConfig.temp_dir())], any_order=True)

    @patch('phases.prelude.log')
    @patch('phases.prelude.ConfiguredTool')
    @patch('phases.prelude.Tools')
    @patch('phases.prelude.os')
    def test_setup_tool_cfg(self, os_mock, Tools_mock, ConfiguredTool_mock, log_mock):

        # Prepares mocks
        def info(text):
            pass  # print text # for debug only

        def existing_file(f):
            return True

        log_mock.info = info
        log_mock.error = info
        log_mock.warning = info
        prelude.XmakeException = info
        prelude.is_existing_file = existing_file

        buildConfig = BuildConfig()
        buildConfig.cfg_dir = MagicMock(return_value=os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'samples'))
        buildConfig.component_dir = MagicMock(return_value=os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'samples'))
        tools = Tools_mock()
        tools.is_declared_tool = lambda tid: False if tid != 'msvc' else True
        buildConfig._tools = tools

        # Runs test
        prelude.setup_tool_cfg(buildConfig)

        # Asserts
        assert (ConfiguredTool_mock.call_count > 0)


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(Test)
    unittest.TextTestRunner(verbosity=2).run(suite)
