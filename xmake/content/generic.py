'''
Created on 17.03.2015

@author: D021770
'''
import log
import spi

from os.path import join, isfile
from utils import is_existing_file, get_first_line

class content(spi.ContentPlugin):
    def __init__(self, build_cfg, pid):
        self._build_cfg=build_cfg
        self._id=pid
        
    def matches(self):
        f=join(self._build_cfg.cfg_dir(),"build.cfg")
        if is_existing_file(f):
            return True
        return False
        
    def setup(self):
            if self.matches():
                log.info("  found build.cfg...")
                log.info("  setting defaults for generic project")
                self._setup()
                return True
            return False
            
    def _setup(self):
        self._build_cfg._build_script_name="generic"
        version_file = join(self._build_cfg.cfg_dir(), 'VERSION')
        if not isfile(version_file):
            base_version = "1.0.0"
        else: 
            base_version=get_first_line(version_file,'no version defined in VERSION file: ' + version_file)
        self._build_cfg.set_base_version(base_version)