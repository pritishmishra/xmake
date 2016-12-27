'''
Created on 10.02.2015

@author: D021770
'''

import log
import spi

import json
from os.path import join
from utils import is_existing_file
from xmake_exceptions import XmakeException

class content(spi.ContentPlugin):


    def __init__(self, build_cfg, pid):
        self._build_cfg=build_cfg
        self._id=pid
        
    def matches(self):
        f=join(self._build_cfg.component_dir(),"package.json")
        if is_existing_file(f):
            return True
        f=join(self._build_cfg.src_dir(),"package.json")
        if is_existing_file(f):
            return True
        return False
        
    def setup(self):
            if self.matches():
                log.info("  found package.json...")
                log.info("  setting defaults for nodejs project")
                self.node_setup()
                return True
            return False
            
    def node_setup(self):
        self._build_cfg._build_script_name="node"
        
        f=join(self._build_cfg.component_dir(),"package.json")
        if is_existing_file(f):
            self._build_cfg.set_src_dir(self._build_cfg.component_dir())
        else:
            f=join(self._build_cfg.src_dir(),"package.json")
        
        with open(f,"r") as d:
            pkg=json.load(d)
        if self._build_cfg.base_version() is None:
            if 'version' not in pkg:
                raise XmakeException('no version entry in package json') 
            self._build_cfg.set_base_version(str(pkg['version']))
            
        
