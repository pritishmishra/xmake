'''
Created on 27.03.2015

@author: I050906
'''

import log
import spi
import re
import xml.etree.ElementTree as ET

from os.path import join
from utils import is_existing_file
from xmake_exceptions import XmakeException

class content(spi.ContentPlugin):
    def __init__(self, build_cfg, pid):
        self._build_cfg=build_cfg
        self._id=pid
        
    def matches(self):
        relPath = "pom.xml"
        if self._build_cfg.alternate_path() is not None: relPath = join(self._build_cfg.alternate_path(),"pom.xml") 
        f=join(self._build_cfg.component_dir(),relPath)
        if is_existing_file(f):
            return True
        return False
        
    def setup(self):
            if self.matches():
                log.info("  found pom.xml...")
                log.info("  setting defaults for maven project")
                self._setup()
                return True
            return False
            
    def _setup(self):
        self._build_cfg._build_script_name="maven"
        log.info('For maven project version will be resolved at build time')
        self._build_cfg.set_base_version("NONE")
