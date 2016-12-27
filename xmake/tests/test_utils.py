'''
Created on 20.02.2014

@author: D051236
'''

import os

if __name__ == '__main__':
    import sys
    dirname = os.path.dirname(os.path.realpath(__file__))
    sys.path.append(dirname + '/../')
    sys.path.append(dirname + '/../../externals')

import StringIO
import unittest
from utils import IterableAwareCfgParser


class Test(unittest.TestCase):

    def setUp(self):
        self.examinee = IterableAwareCfgParser()
        self.content_fp = StringIO.StringIO()
        ex = self.examinee

        ex.add_section('s')
        [ex.set('s', opt, val) for (opt, val) in ('simple', 'foo'), ('with_space', 'b a r'), ('list', ['a', 'b'])]
        ex.write(self.content_fp)

    def test_get_should_return_existing_values(self):
        self._assert_get_returns_proper_values(self.examinee)

    def test_get_should_return_existing_values_after_reading_from_file(self):
        examinee = IterableAwareCfgParser()
        self.content_fp.pos = 0   # reset file pointer to start
        examinee.readfp(self.content_fp)
        self._assert_get_returns_proper_values(examinee)

    def _assert_get_returns_proper_values(self, cfg_parser):
        self.assertEqual(cfg_parser.get('s', 'simple'), 'foo')
        self.assertEqual(cfg_parser.get('s', 'with_space'), 'b a r')
        self.assertEqual(cfg_parser.get('s', 'list'), ['a', 'b'])


class TestToolsCfg(unittest.TestCase):
    def setUp(self):
        tools_cfg_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'samples', 'tools.cfg')
        self.examinee = IterableAwareCfgParser()
        self.examinee.read(tools_cfg_file)

    def test_tools_cfg_no_runtimes(self):
        name = 'cmake_framework'
        key = 'groupId'
        key_with_runtime = key + '.linuxx86_64'
        self.assertFalse(self.examinee.has_option(name, 'runtimes'))
        self.assertFalse(self.examinee.has_option(name, key_with_runtime))
        self.assertTrue(self.examinee.has_option(name, key))
        self.assertTrue(self.examinee.get(name, key) == 'com.sap.aa.cmake_framework')

    def test_tools_cfg_with_runtime(self):
        name = 'cmake@linuxppc64'
        key = 'groupId'
        key_with_runtime = key + '.linuxppc64'

        self.assertTrue(self.examinee.has_option(name, 'runtimes'))
        self.assertTrue(self.examinee.get(name, 'runtimes') == 'linuxppc64')
        self.assertFalse(self.examinee.has_option(name, key_with_runtime))
        self.assertTrue(self.examinee.has_option(name, key))
        self.assertTrue(self.examinee.get(name, key) == 'com.sap.org.cmake')

if __name__ == "__main__":
    unittest.main()
