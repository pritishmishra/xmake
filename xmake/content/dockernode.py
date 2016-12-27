'''
Created on 10.02.2015

@author: I079877
'''

import log

from content.node import content as nodebase

class content(nodebase):

 
    def __init__(self, build_cfg, pid):
        nodebase.__init__(self, build_cfg, pid)
        
    def matches(self):
        
        if self._build_cfg._build_script_name == "dockernode":
            
            return nodebase.matches(self)
        return False
        
    def setup(self):
            if self.matches():
                log.info("  found package.json...")
                log.info("  setting defaults for dockernode project")
                self._setup()
                return True
            return False
    
    def _setup(self):
        nodebase.node_setup(self)
        #set _build_script_name back to dockernode since it's specified in the config file
        self._build_cfg._build_script_name="dockernode"
        
                
    