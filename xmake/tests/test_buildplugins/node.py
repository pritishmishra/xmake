import io,os
import sys
import subprocess

dirname = os.path.dirname(os.path.realpath(__file__))
if __name__ == '__main__':
  sys.path.append(dirname + '/../../')
  sys.path.append(dirname + '/../../../externals')

sys.path.append(dirname + '/../')

import logging

import log
from ExternalTools import Tools

import unittest
import inspect
from StringIO import StringIO
from buildplugins import node

from mock import patch, Mock, MagicMock, call
from test_helpers import stubBuildConfig, stubToolsCache
import appcache

class Test(unittest.TestCase):

  def setUp(self):
    # prepares fake BuildConfig object
    cfg_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'samples', 'node')
    component_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'samples','node')
    self.cfg = stubBuildConfig(cfg_dir, component_dir)
    self.old_logger = log.logger

  @patch('phases.prelude.Tools')
  def test_it_prints_npm_version_after_import(self, Tools_mock):
    # mock logger to assert logged text
    with patch('logging.RootLogger') as logger:
      log.logger = logger
      # mock appcache to use fake node installation, which prints CURRENT NPM VERSION IS 1.0.0 when --version is specified
      fake_npm_home = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'samples','node', 'npm_home_stub')
      self.cfg = stubToolsCache(self.cfg, ('com.sap.prd.distributions.org.nodejs.linux', 'nodejs', '0.12.0'), fake_npm_home)
      self.cfg.cfg_dir = MagicMock(return_value=os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'samples'))
      
      # setup buildplugin, and run it's after_IMPORT method.
      d = node.build(self.cfg)

      tools_executable=Tools.executable
      def my_executable(self, tool, suf="exe"):
          return tools_executable(self,tool,"cmd") 

      with patch.object(Tools, 'executable', new=my_executable):
          # Tools.executable() must be patched for windows as called with "exe" from the node build plugin
          d.after_IMPORT(self.cfg)
      log.logger.log.assert_called_with(logging.INFO,"CURRENT NPM VERSION IS 1.0.0")
          
  def tearDown(self):
    # revert any monkey patch done
    log.logger = self.old_logger

if __name__ == '__main__':
  unittest.main()
