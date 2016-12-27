from mock import patch, Mock, MagicMock, call
from config import BuildConfig
from ExternalTools import Tools
import appcache

def stubBuildConfig(cfg_dir, component_dir):
  # template to create buildConfig in test cases
  cfg = BuildConfig()
  cfg._runtime = "linux"
  cfg._tools = Tools()
  cfg._tools.import_tools_dir=cfg.import_tools_dir
  cfg._tools.runtime=cfg.runtime
  cfg.cfg_dir = MagicMock(return_value=cfg_dir)
  cfg.component_dir = MagicMock(return_value=component_dir)
  return cfg

def stubToolsCache(cfg, aid, path):
  # stub tool cache to return specfic path for specific aid set
  # if aid is not found in the fake toolscache, it reverts to search the actual app cache.
  appcache_mock = Mock(appcache.AppCache)
  old_toolcache = cfg._tools._toolcache
  cfg._tools._toolcache = appcache_mock
  def patched_get(_aid,retriever=None,msg=None,archive=True):
    if (aid==_aid):
      return path
    else:
      return old_toolcache.get(_aid, retriever=retriever, msg=msg, archive=archive)
  appcache_mock.get = patched_get
  return cfg