'''
Created on 16.02.2015

@author: D021770
'''

import utils
import log
from os.path import join,expanduser,dirname,realpath,isfile

_reported=False

def get_installation_dir():
    return dirname(get_python_package_dir())

def get_python_package_dir():
    return dirname(realpath(__file__))

def get_packaged_tools_dir():
    return join(get_installation_dir(),'tools')

def get_tool_plugin_dir():
    return join(get_python_package_dir(), 'tools')
def get_content_plugin_dir():
    return join(get_python_package_dir(), 'content')
def get_build_plugin_dir():
    return join(get_python_package_dir(), 'buildplugins')

def get_user_home():
    return expanduser("~")
def get_xmake_user_home():
    return join(get_user_home(),'.xmake')

def get_technical_xmake_version():
    x=join(get_installation_dir(),'sourceversion.txt')
    if not isfile(x):
        global _reported
        if not _reported:
            _reported=True
            log.warning('not using an officially installed xmake version')
        return None
    return utils.get_first_line(x,'cannot read sourceversion.txt')

def get_logical_xmake_version():
    x=join(get_installation_dir(),'version.txt')
    if not isfile(x):
        return None
    return utils.get_first_line(x,'cannot read version.txt')

def show_version_info():
    instdir=get_installation_dir()

    msg='loaded' if isfile(join(instdir,'.loaded')) else 'installed'
    log.info( 'version info for '+msg+" xmake")
    log.info( '  installation directory is '+instdir)
    log.info( '  technical version is '+str(get_technical_xmake_version()))
    log.info( '  logical version is '+str(get_logical_xmake_version()))
    n=join(instdir,'changelog')
    if (isfile(n)):
        log.info( '  Changelog:')
        log.log_file_content(n)
    else:
        log.info( '  no changelog available')
