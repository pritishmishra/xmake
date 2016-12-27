'''
Created on 30.08.2014

@author: d021770
'''

import log
import os

from utils import has_method
from xmake_exceptions import XmakeException
from const import XMAKE_BUILD_PLATFORM
from const import XMAKE_BUILD_MODE

def normalize_cosy_gav(gav):
    if gav is None: return None
    c=gav.split(':')
    if (len(c)==2):
        gav='com.sap.commonrepo.coordinatesystems:'+c[0]+':variant-coordinate-system:'+c[1]
    return gav
    
def acquire_custom_variant_data(build_script, build_cfg):
    build_cfg._variant_cosy_gav=normalize_cosy_gav(build_script.variant_cosy_gav())
        
    # optional method for compatibility reasons
    if has_method(build_script, 'variant_cosy'):
        if build_script.variant_cosy_gav()!=None:
            raise XmakeException('build plugin uses old variant_cosy method, therefore it must not return a GAV')
        build_cfg._variant_cosy=build_script.variant_cosy()
        log.warning("build plugin uses legacy mode for variant coordinate system. Please implement 'variant_cosy_gav' instead")
    else:
        build_cfg._variant_cosy=variant_cosy_from_gav(build_script, build_cfg)
        
    if (build_cfg._variant_cosy!=None): 
        build_cfg._suppress_variant_handling=False
        build_cfg._variant_coords= build_script.variant_coords()    
    else:
        build_cfg._suppress_variant_handling=True


def variant_cosy_from_gav(build_script, build_cfg):
    gav=normalize_cosy_gav(build_script.variant_cosy_gav())
    if (gav==None): return None
    e=gav.split(':')
    if (len(e)!=4):
        raise XmakeException('unexpected GAV format for coordinate system: '+gav)
    return os.path.join(build_cfg.import_tools_dir(),e[1]+'-'+e[3]+'.'+e[2])
    
def default_variant_coords(build_cfg):
    coords=dict()
    coords.update(build_cfg.variant_info())
    if coords.has_key(XMAKE_BUILD_PLATFORM):
        if coords[XMAKE_BUILD_PLATFORM]==None:
            raise XmakeException('ERR: platform variant info not set')
    
        if not coords.has_key(XMAKE_BUILD_MODE):
            coords[XMAKE_BUILD_MODE]='dbg'
        if coords[XMAKE_BUILD_MODE]==None: 
            raise XmakeException('ERR: mode variant info not set')
        
    return coords