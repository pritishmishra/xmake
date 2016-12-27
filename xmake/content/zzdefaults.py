'''
Created on 17.03.2015

@author: D021770
'''
import log
import spi

from utils import is_existing_directory, is_existing_file
from os.path import join

class content(spi.ContentPlugin):


    def __init__(self, build_cfg, pid):
        self._build_cfg=build_cfg
        self._id=pid
        
    def matches(self):
        if not is_existing_directory(self._build_cfg.cfg_dir()):
            return True
        if is_existing_file(join(self._build_cfg.component_dir(),".xmake.cfg")):
            return True
        return False
        
    def setup(self):
            if self.matches():
                if not is_existing_directory(self._build_cfg.cfg_dir()):
                    log.info("  no cfg folder found...")
                else:
                    log.info("  .xmake.cfg found in project root...")
                self._setup()
                return True
            return False
            
    def _setup(self):
        log.info("  assuming some defaults")
        self._build_cfg._build_script_name="generic"
        self._build_cfg.set_base_version('1.0.0')
        if is_existing_file(join(self._build_cfg.component_dir(),".xmake.cfg")):
            log.info("    found .xmake.cfg")
            if not is_existing_directory(self._build_cfg.src_dir()):
                self._build_cfg.set_src_dir(self._build_cfg.component_dir())
                log.info("    using flat source dir: "+self._build_cfg.src_dir())
            
        