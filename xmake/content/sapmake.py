'''
Created on 19.03.2015

@author: I072332
'''
import log, spi
from os.path import join
from utils import is_existing_file
   
class content(spi.ContentPlugin):
  def __init__(self, build_cfg, pid):
    self._build_cfg=build_cfg
    self._id=pid
           
  def matches(self):
    f=join(self._build_cfg.src_dir(),"props.cfg")
    if is_existing_file(f):
      return True
    return False
           
def setup(self):
  if self.matches():
    log.info("  found props.cfg...")
    log.info("  setting defaults for sapmake project")
    self._setup()
    return True
  return False
               
def _setup(self):
  self._build_cfg._build_script_name="sapmake"
  self._build_cfg.set_base_version('1.0.0')
