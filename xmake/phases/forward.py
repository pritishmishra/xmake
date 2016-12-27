'''
Created on 23.07.2014

@author: D051236
'''

import utils
import log
import os

def execute_forward(build_cfg):
    
    if build_cfg.forwarding_dir() is not None:
        build_script = build_cfg.build_script() 
        utils.flush()
        build_script.forward_buildresults()
        utils.flush()
        with open(os.path.join(build_cfg.genroot_dir(),'forward.path'),"w") as f:
            f.write(build_cfg.forwarding_destination())
            
        log.info( "build result forwarding succeeded")
    else:
        log.info( "build result forwarding step skipped because of missing option -F")
