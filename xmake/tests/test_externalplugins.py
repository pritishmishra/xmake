if __name__ == '__main__':
    import sys
    import os
    dirname = os.path.dirname(os.path.realpath(__file__))
    sys.path.append(dirname + '/../')
    sys.path.append(dirname + '/../../externals')

import unittest
from mock import patch, Mock, MagicMock, call
from xmake_exceptions import XmakeException
from const import XMAKE_NEXUS
import externalplugins


class Test(unittest.TestCase):

    @patch('externalplugins.log')
    @patch('externalplugins.open')
    @patch('externalplugins.os')
    @patch('externalplugins.urllib')
    @patch('externalplugins.shutil')
    @patch('externalplugins.contextlib')
    @patch('externalplugins.tempfile')
    @patch('externalplugins.re')
    @patch('externalplugins.tarfile')
    def test_download_plugin_from_nexus(self, tarfile_mock, re_mock, tempfile_mock, contextlib_mock, shutil_mock, urllib_mock, os_mock, open_mock, log_mock):
        single_tarfile_open_mock = MagicMock()
        tarfile_mock.open = MagicMock(return_value=single_tarfile_open_mock)

        single_tarfile_mock = MagicMock()
        single_tarfile_open_mock.__enter__ = MagicMock(return_value=single_tarfile_mock)
        os_mock.path.isdir = MagicMock(return_value=False)

        externalplugins._download_plugin_from_nexus(XMAKE_NEXUS, 'sampleplugin', nexusRepo='blabla', destDirectory='/my/folder')

        assert(urllib_mock.openurl.called_once_with('http://nexus.wdf.sap.corp:8081/nexus/service/local/artifact/maven/content?g=com.sap.prd.xmake.buildplugins&a=sampleplugin&v=LATEST&r=build.snapshots&e=tar.gz'))
        assert(tarfile_mock.open.call_count == 1)
        assert(single_tarfile_mock.extractall.call_count == 1)
        assert(shutil_mock.rmtree.call_count==0)
        assert (log_mock.error.call_count==0)

    @patch('externalplugins.log')
    @patch('externalplugins.open')
    @patch('externalplugins.os')
    @patch('externalplugins.urllib')
    @patch('externalplugins.shutil')
    @patch('externalplugins.contextlib')
    @patch('externalplugins.tempfile')
    @patch('externalplugins.re')
    @patch('externalplugins.tarfile')
    def test_download_plugin_from_nexus_failed(self, tarfile_mock, re_mock, tempfile_mock, contextlib_mock, shutil_mock, urllib_mock, os_mock, open_mock, log_mock):
        contextlib_mock.closing = MagicMock(side_effect=IOError)
        externalplugins._download_plugin_from_nexus(XMAKE_NEXUS, 'sampleplugin', nexusRepo='blabla', destDirectory='/my/folder')

        assert (urllib_mock.openurl.called_once_with('http://nexus.wdf.sap.corp:8081/nexus/service/local/artifact/maven/content?g=com.sap.prd.xmake.buildplugins&a=sampleplugin&v=LATEST&r=build.snapshots&e=tar.gz'))
        assert (log_mock.warning.call_count>0)

        log_mock.reset()
        contextlib_mock.closing = MagicMock()
        open_mock.side_effect = IOError
        externalplugins._download_plugin_from_nexus(XMAKE_NEXUS, 'sampleplugin', nexusRepo='blabla', destDirectory='/my/folder')
        assert (log_mock.warning.call_count>0)

    @patch('externalplugins.log')
    @patch('externalplugins.open')
    @patch('externalplugins.os')
    @patch('externalplugins.urllib')
    @patch('externalplugins.shutil')
    @patch('externalplugins.contextlib')
    @patch('externalplugins.tempfile')
    @patch('externalplugins.re')
    @patch('externalplugins.tarfile')
    def test_download_plugin_from_nexus_bad_params(self, tarfile_mock, re_mock, tempfile_mock, contextlib_mock, shutil_mock, urllib_mock, os_mock, open_mock, log_mock):
        with self.assertRaises(XmakeException):
            externalplugins._download_plugin_from_nexus(XMAKE_NEXUS, 'sampleplugin', nexusRepo='blabla', destDirectory='')
        with self.assertRaises(XmakeException):
            externalplugins._download_plugin_from_nexus(XMAKE_NEXUS, 'sampleplugin', nexusRepo='blabla')
        with self.assertRaises(XmakeException):
            externalplugins._download_plugin_from_nexus(XMAKE_NEXUS, 'sampleplugin', nexusRepo='', destDirectory='/my/folder')
        with self.assertRaises(XmakeException):
            externalplugins._download_plugin_from_nexus(XMAKE_NEXUS, 'sampleplugin', destDirectory='/my/folder')

    @patch('externalplugins.urllib')
    @patch('externalplugins.log')
    @patch('externalplugins.contextlib')
    @patch('externalplugins.ET')
    def test_list_plugins_from_nexus(self, ET_mock, contextlib_mock, log_mock, urllib_mock):
        single_root_mock = MagicMock()
        single_data_mock = MagicMock()
        single_item_mock = MagicMock()
        single_text_mock = MagicMock()

        ET_mock.fromstring = MagicMock(return_value=single_root_mock)
        single_root_mock.find = MagicMock(return_value=single_data_mock)
        single_data_mock.findall = MagicMock(return_value=[single_item_mock])
        single_item_mock.find = MagicMock(return_value=single_text_mock)
        single_text_mock.text = 'sampleplugin'

        pluginsFound = externalplugins._list_plugins_from_nexus(XMAKE_NEXUS, 'build.snapshots')
        assert(ET_mock.fromstring.called_once)
        assert(single_data_mock.findall.called_once)
        assert(single_item_mock.find.called_once)
        assert(len(pluginsFound) == 1)
        assert('sampleplugin' in pluginsFound)

        #error cases
        log_mock.reset()
        ET_mock.fromstring = MagicMock(return_value=None)
        pluginsFound = externalplugins._list_plugins_from_nexus(XMAKE_NEXUS, 'build.snapshots')
        assert(log_mock.error.called_once)
        assert(len(pluginsFound) == 0)

    @patch('externalplugins.log')
    @patch('externalplugins.contextlib')
    @patch('externalplugins.ET')
    def test_list_plugins_from_nexus_bad_params(self, ET_mock, contextlib_mock, log_mock):
        with self.assertRaises(XmakeException):
            pluginsFound = externalplugins._list_plugins_from_nexus(XMAKE_NEXUS, '')

        with self.assertRaises(XmakeException):
            pluginsFound = externalplugins._list_plugins_from_nexus(XMAKE_NEXUS, None)

    @patch('externalplugins.log')
    @patch('externalplugins._list_plugins_from_nexus')
    @patch('externalplugins._download_plugin_from_nexus')
    def test_install(self, _download_plugin_from_nexus_mock, _list_plugins_from_nexus_mock, log_mock):
        _list_plugins_from_nexus_mock.return_value = ['sampleplugin']

        externalplugins.install(XMAKE_NEXUS, 'c:/users/i050906/Desktop/.xmake/externalplugins/')
        assert (_list_plugins_from_nexus_mock.called)
        assert (_download_plugin_from_nexus_mock.called)

        #case no plugin found
        log_mock.reset()
        _list_plugins_from_nexus_mock.reset()
        _download_plugin_from_nexus_mock.reset()
        _list_plugins_from_nexus_mock.return_value = []

        externalplugins.install(XMAKE_NEXUS, 'c:/users/i050906/Desktop/.xmake/externalplugins/')

        assert (_list_plugins_from_nexus_mock.called)
        assert (_download_plugin_from_nexus_mock.called)
        assert (log_mock.warning.called)

    # def test_discover(self):
        # externalplugins.discover({}, 'c:/users/i050906/Desktop/.xmake/externalplugins/')

if __name__ == '__main__':
    unittest.main()
