'''
Created on 10.02.2015

@author: D021770
'''

import log
import spi

from os.path import join
from utils import is_existing_file

class content(spi.ContentPlugin):


    def __init__(self, build_cfg, pid):
        self._build_cfg=build_cfg
        self._id=pid

    def matches(self):
        f=join(self._build_cfg.component_dir(),"src","build.xml")
        if is_existing_file(f):
            return True
        f=join(self._build_cfg.component_dir(),"build.xml")
        if is_existing_file(f):
            return True
        return False

    def setup(self):
            if self.matches():
                log.info("  found build.xml...")
                log.info("  setting defaults for ant project")
                self._setup()
                return True
            return False

    def _setup(self):
        self._build_cfg._build_script_name="ant"
        f=join(self._build_cfg.component_dir(),"src","build.xml")
        if not is_existing_file(f):
            self._build_cfg.set_src_dir(self._build_cfg.component_dir())


