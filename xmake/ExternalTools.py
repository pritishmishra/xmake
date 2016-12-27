'''
configuration w/ regards to external tools (e.g. installation directories)

Created on 17.12.2013

@author: Christian Cwienk (d051236)
'''

import os
import imp
import subprocess
import shutil
import inspect
import appcache
import log
import utils
import urllib
import contextlib
import tempfile

from glob import glob
from os import name, path, system, unlink, environ
from os.path import islink, realpath, dirname, join
from os.path import expanduser
from os.path import isfile
from utils import is_existing_directory, runtime_ga
from const import XMAKE_NEXUS

import spi, inst

from xmake_exceptions import XmakeException
from utils import has_method

class OS_Utils(object):
    @staticmethod
    def is_UNIX(): 
        return os.name == 'posix'
    @staticmethod 
    def rm_dir(path):
        if OS_Utils.is_UNIX():
            if islink(path): unlink(path)
            else:
                shutil.rmtree(path)
            return
        #work around issue w/ shutil.rmtree w/ symbolic links in NT
        system('rd /s /q ' + realpath(path))
    @staticmethod
    def find_in_PATH(file_name):
        '''looks up the given file_name in the PATH
        returns a non-empty list of found entries or None if the file was not found'''

        lookup_cmd = 'which' if OS_Utils.is_UNIX() else 'where'
        p = subprocess.Popen([lookup_cmd, file_name], stdout=subprocess.PIPE)
        (stdout, _) = p.communicate()   #don't care about stderr
        rc = p.returncode
        if rc != 0: return None #file was not found at all
        return [x.strip() for x in stdout.split('\n')]

    @staticmethod 
    def exec_script(cmd):
        #print 'INFO: calling '+' '.join(cmd)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        (stdout, stderr) = p.communicate()   #don't care about stderr
        rc = p.returncode
        return (rc, stdout, stderr)

# some hard-coded paths for tools
# do NOT use them directly outside this file - they are intended to be exposed by the Tools type
_TOOLS_DEPOT_NT = r'\\production.wdf.sap.corp\depot\tools'
_TOOLS_DEPOT_UNIX = '/sapmnt/depot/tools'

_VMAKE_INSTDIR_NT = r'c:\SAPDevelop\buildtools\dev'
_VMAKE_INSTDIR_UNIX = '/SAPDevelop/buildtools/dev'

#
def is_gav(gav):
    if isinstance(gav, (list, tuple)): return True
    comp=gav.split(':')
    return len(comp)>2

# gid:aid:type:classifier:version
def tool_gav(gav,add=False):
    if isinstance(gav, (list, tuple)):
        comp=gav
    else:
        comp=gav.split(':')
    gid= comp[0]
    aid= comp[1]
    r=[]
    if len(comp)==3:
        ty='zip'
        cf=''
        v=comp[2]
    else:
        ty= comp[2]
        if len(comp)==4:
            cf=''
            v = comp[3]
        else:
            cf= comp[3]
            v = comp[4]
            if len(comp)>5:
                r=comp[5:]

    v=[gid,aid,ty,cf,v]
    if add: v.extend(r)
    return v

def tool_package_url(gav,repo,nexus=XMAKE_NEXUS):
    if not isinstance(gav, (list, tuple)):
        comp=tool_gav(gav)
    else:
        comp=gav
    #https://nexus.wdf.sap.corp:8443/nexus/service/local/artifact/maven/redirect?r=build.snapshots&g=com.sap.prd.jobbase&a=component&v=1.6.5&c=JobDB&e=doc
    
    url=  ('/'.join([nexus,
                    'nexus/service/local/artifact/maven/redirect?']))
    if comp[3].strip()=='':
        url+= ('&'.join(['r='+repo,
                         'g='+comp[0],
                         'a='+comp[1],
                         'v='+comp[4],
                         'e='+comp[2]]))
    else:
        url+= ('&'.join(['r='+repo,
                         'g='+comp[0],
                         'a='+comp[1],
                         'v='+comp[4],
                         'c='+comp[3],
                         'e='+comp[2]]))
    return url
    #https://nexus.wdf.sap.corp:8443/nexus/service/local/repositories/deploy.milestones/content/com/sap/prd/jobbase/component/1.6.5/component-1.6.5-JobDB.doc

def tool_installation_archive(gav):
    if not isinstance(gav, (list, tuple)):
        gav=tool_gav(gav)
    if gav[3].strip()!='':
        return imp[1]+'-'+imp[4]+'-'+imp[3]+'.'+imp[2]
    return imp[1]+'-'+imp[3]+'.'+imp[2]

def tool_retrieve(gav,repo):
    gav=tool_gav(gav)
    v=gav[4]
    url=tool_package_url(gav)
    return tool_retrieve_url(url,v,repo)

def tool_retrieve_url(url,v,repo):
    log.info('retrieving '+url)
    try:
        filename=None
        contentType=None
        with contextlib.closing(urllib.urlopen(url,proxies={})) as response:
            contentType=response.info().type
            with tempfile.NamedTemporaryFile(delete=False) as out_file:
                    filename=out_file.name
                    shutil.copyfileobj(response, out_file)

        if isfile(filename) and not contentType.startswith('text/html'):
            log.info('   retrieved file is '+filename+'('+contentType+')')
            global xmake_loaded
            xmake_loaded=filename 
            return filename
    except IOError as e:
        log.error('cannot fetch URL: '+str(e))
        raise XmakeException("repository "+repo+" cannot be reached")
    log.info('version '+v+' not found in repository '+repo)
    shutil.copyfile(filename, filename+'.html')
    log.info( '----- provided error page -------')
    log.log_file_content(filename)
    log.info( '---------------------------------')
    raise XmakeException("version "+v+" for xmake not found in repository "+repo)

#
# The ToolWrapper class wraps any possible implementation combination of a tool class and provides a
# guaranteed interface for use by the framework. There it maps those methods to the various possibilities
# for tool class implementations.
#
class ToolWrapper(spi.Tool):
    def __init__(self, tools, toolid, module):
        spi.Tool.__init__(self,tools,toolid)

        if not hasattr(module, 'tool'):raise XmakeException('ERR: tool %s does not define a class "tool"' % (toolid))

        if not issubclass(module.tool, spi.Tool):
            log.warning( "tool class is not a subclass of spi.Tool: "+toolid)
        if not has_method(module.tool,'__init__', 2):
            log.error( "custom tool class for %s must implement a c'tor w/ exactly two formal parameter (which is of type Tools)" % (toolid))
            raise XmakeException("failed to instantiate 'tool' (no c'tor def w/ correct amount of formal parameters (which is one) found)")
        self.impl=module.tool(tools,toolid)
        
        if not has_method(self.impl, 'tool',1):raise XmakeException('ERR: tool %s does not define a method "tool" with one formal parameters' % (toolid))
        method = self.impl.tool
       
        self.has_imports=False
        if hasattr(self.impl, 'imports'):
            method = self.impl.imports
            if not callable(method):raise XmakeException('ERR: tool %s does not define a method "imports"' % (toolid))
            argcount=len(inspect.getargspec(method)[0])
            if argcount != 2: raise XmakeException('ERR: tool %s does not define a method "imports" with one formal parameters' % (toolid))
            self.has_imports=True
            
    def imports(self, version):
        assert version is not None
        assert isinstance(version, str)
        if not self.has_imports:
            return []
        return self.impl.imports(version) 
           
    def tool(self,version):
        assert version is not None
        assert isinstance(version, str)
        return self.impl.tool(version)
        
class Tools:
    '''
    provides access to available tools (in a platform-indenpendent way). Some standard tools are provided from share
    (e.g. artifact_deployer) - this is recognisable by the fact that there is an explicit method for retrieving them.
    --
    in addition to that, a generic way to access tools available on the current machine is provided (access using ['key'] /
    __getitem__()) 
    '''
    def __init__(self, tools_root = _TOOLS_DEPOT_UNIX if OS_Utils.is_UNIX() else _TOOLS_DEPOT_NT):
        self._tools_root = tools_root
        self._home = inst.get_user_home()
        self._xmake_inst_dir = inst.get_python_package_dir()
        self._xmake_tool_plugin_dir= inst.get_tool_plugin_dir()
        self.import_tools_dir=lambda:None
        self.runtime=utils.runtime

        if environ.has_key('XMAKE_TOOL_INSTALLATION_ROOT'):
            d=environ['XMAKE_TOOL_INSTALLATION_ROOT']
            if not is_existing_directory(d):
                log.error( "env var 'XMAKE_TOOL_INSTALLATION_ROOT' was set, but does not point to an existing directory. Either unset or change it")
                raise XmakeException("encountered invalid value of env var 'XMAKE_TOOL_INSTALLATION_ROOT'")
            self._tool_install_dir=d
        else:
            self._tool_install_dir=path.join(inst.get_xmake_user_home(),'tools')
            
        self._toolcache=appcache.AppCache('tool', self._tool_install_dir)
        log.info( 'local tool installation in '+self._tool_install_dir)
        if environ.has_key('XMAKE_TOOLS_ROOT'):
            tools_root = environ['XMAKE_TOOLS_ROOT']
            if not is_existing_directory(tools_root):
                log.error( "env var 'XMAKE_TOOLS_ROOT' was set, but does not point to an existing directory. Either unset or change it")
                raise XmakeException("encountered invalid value of env var 'XMAKE_TOOLS_ROOT'")
        self._tools_root=tools_root

        self.__tools_dict = self._toolsdict()

    def xmake_inst_dir(self):
        return self._xmake_inst_dir
    def xmake_tool_plugin_dir(self):
        return self._xmake_tool_plugin_dir
    
    def mapToolGAVStr(self,gavstr):
        imp=gavstr.split(':')
        return (imp[0],imp[1],imp[-1])
    def hasToolGAV(self,gavstr):
        coord=self.mapToolGAVStr(gavstr)
        return self.tool_installation_cache().has(coord)
                                      
    def user_home(self): return self._home
    def tool_installation_cache(self): return self._toolcache
    
    def tools_depot(self): return self._tools_root
    def packaged_tools_dir(self, tool=None):
        if tool is None:
            return inst.get_packaged_tools_dir()
        return path.join(inst.get_packaged_tools_dir(),tool)

    def commonrepo_root(self, tool=None):
        local=path.join(self.tools_depot(), 'gen', 'java', 'SAPSource', 'commonrepo')
        return local if tool is None else path.join(local,tool)
    
    def commonrepo_sapmake_cosy(self): return path.join(path.join(self.commonrepo_root(), 'coordinatesystems', 
                                                                  'com.sap.commonrepo.coordinatesystems', 
                                                                  'vmake', '1', 'vmake.variant-coordinate-system'))
    def commonrepo_cosy(self): return self.commonrepo_sapmake_cosy()

    def commonrepo_tools_dir(self,tool=None):
        local = self.packaged_tools_dir(tool)
        if path.exists(local):
            return local
        if environ.has_key("XMAKECOMMONREPOTOOLS"):
            local = environ.get("XMAKECOMMONREPOTOOLS")
            if path.exists(local):
                return local if tool is None else path.join(local,tool)
            
        return self.commonrepo_root(tool)
       
    def tool_suffix(self, suf='cmd'):
        return "" if OS_Utils.is_UNIX() else "."+suf
    def executable(self, tool, suf='cmd'):
        return tool+self.tool_suffix(suf)
    
    def artifact_deployer(self): return path.join(self.commonrepo_tools_dir('artifactdeployer'), 'bin', self.executable('artifactdeployer'))
    def artifact_importer(self): return path.join(self.commonrepo_tools_dir('artifactimporter'), 'bin', self.executable('artifactimporter'))
    def prodpassaccess(self):
        local = self.packaged_tools_dir('prodpassaccess')
        if path.exists(local):
            return path.join(local, 'bin', self.executable('prodpassaccess'))
        return path.join(self.tools_depot(), 'gen', 'java', 'SAPSource', 'access', 'prodpassaccess', 'bin', self.executable('prodpassaccess'))

    def vmake_instdir(self):
        if environ.has_key('VMAKETOOL'): return environ['VMAKETOOL']
        return _VMAKE_INSTDIR_UNIX if OS_Utils.is_UNIX() else _VMAKE_INSTDIR_NT

    def is_declared_tool(self,tid): return self.__tools_dict.has_key(tid)
    def declare_tool(self,tid,ga,path=None,archive=True):
        self.__tools_dict[tid]=spi.StandardTool(self,tid,ga,path,archive)
    def declare_runtime_tool(self,tid,ga,vmode='group',path=None,archive=True):
        self.__tools_dict[tid]=spi.StandardTool(self,tid,runtime_ga(ga,vmode,rt=self.runtime()),path,archive)
    
    def _getTools(self):
        return self.__tools_dict
    
    def _toolsdict(self):
        tools={}
        files=glob(join(self.xmake_tool_plugin_dir(), '*.py'))
        def load_tool(f):
            module=imp.load_source('tool',f)
            tool_name=path.basename(f)[:-3]
            # print "INFO: found tool definition " + tool_name
            tools[tool_name] = ToolWrapper(self,tool_name,module)
        map(load_tool, files)
        return tools

    def __getitem__(self,toolidstr):
        assert toolidstr is not None
        assert isinstance(toolidstr, str)
        if not toolidstr in self.__tools_dict.keys(): self._not_found(toolidstr)
        return self.__tools_dict.get(toolidstr)


    def _fail_if_not_windows(self, tool):
        if OS_Utils.is_UNIX(): raise XmakeException("tool '%s' is only available on Windows (NT)" % (tool))
    def _not_found(self,toolstr): raise XmakeException("tool '%s' not found (not available on local machine or not known to xmake" % (toolstr))


    def _tool_load(self,gav):
        comp=tool_gav(gav)
        return self.tool_installation_cache().get((comp[0],comp[1],comp[4]),
                                            lambda aid: tool_retrieve(comp))
