'''
Created on 23.07.2014

@author: d021770
'''

###############################################################################################
#
# Service Provider Interfaces (SPI) provided by the xMake framework for its extension plugins.
#
###############################################################################################
from xmake_exceptions import XmakeException
from buildplugin import default_variant_coords
from utils import validate_path, is_existing_file
import utils
import ExternalTools

import log
import os.path
import shutil
import sys
import inspect
from os.path import join,isdir
from os import listdir



###################################################################
# Build Plugin Meta Class
###################################################################

class MetaBuildPlugin(type):
    def __new__(cls, cls_name, bases, cls_dict):
        if cls_dict.get("__module__") != __name__: # class is not defined in this module
            # replace _ObjectBase with object in list of base classes
            bases = tuple(object if base is _ObjectBase else base for base in bases)

            if cls_name != "build":
                if not any(issubclass(base, BuildPlugin) for base in bases): # class is not a build plugin
                    if any(isinstance(base, type) for base in bases):
                        # new-style class
                        return type(cls_name, bases, cls_dict)
                    else:
                        # old-style class
                        from types import ClassType
                        return ClassType(cls_name, bases, cls_dict)

            # inject base class, if none is specified
            if bases in ((), (object,)):
                bases = (BuildPlugin,)

        return super(MetaBuildPlugin, cls).__new__(cls, cls_name, bases, cls_dict)

###################################################################
# Object Base Class
###################################################################

class _ObjectBase(object):
    """
    Base class to be aliased as 'object' in global scope of build plugins to
    allow them to inherit from 'object' and still get BuildPlugin as actual
    base class.
    """
    __metaclass__ = MetaBuildPlugin

###################################################################
# Build Plugin Base Class
###################################################################

class BuildPlugin(object):
    __metaclass__ = MetaBuildPlugin

    def __init__(self, build_cfg):
        self.build_cfg = build_cfg

    def set_option(self,o,v):
        log.warning("unknown build plugin option; "+o)

    def set_option_string(self,opt):
        opts=opt.split(',') # should be improved to support commas in option strings
        self.set_options(opts)

    # convenience method called by the standard implementation of set_option_string.
    # Implement only one of those methods.
    def set_options(self,opts):
        raise XmakeException('ERR: build plugin %s does not support option setting' % self.__class__)

    def run(self):
        raise XmakeException('ERR: build plugin %s does not define a method "run" with empty formal parameter list to execute the build' % self.__class__)

    def variant_cosy_gav(self):
        return None

    def variant_coords(self):
        return default_variant_coords(self.build_cfg)

    def _clean_if_requested(self):
        if not self.build_cfg.do_clean() or not os.path.isdir(self._wrk_dir()): return
        log.info( "purging build directory")
        utils.rmtree(self._wrk_dir())
        os.mkdir(self._wrk_dir())

    def _wrk_dir(self):
        return self.build_cfg.gen_dir()

    def _is_plain(self):
        return self.build_cfg.src_dir()==self.build_cfg.component_dir()

    def _handle_configured_tools(self,h):
        ct=self.build_cfg.configured_tools()
        if len(ct)>0:
            log.info( 'found tool resolutions')
            def add_arg(key):
                d=ct[key].inst_dir()
                log.info( '  configured tool '+ct[key].label()+' resolved to '+str(d))
                h(key,d)
            map(add_arg, ct.keys())
        else:
            log.info( 'no configured tool resolutions found')

    def _handle_dependencies(self,h):
        d=self.build_cfg.dependency_config()
        if d is not None and len(d)>0:
            log.info( 'found dependency resolutions for multi component builds...')
            def add_arg(key):
                if 'dir' in d[key]:
                    log.info( '   dependency '+key+' resolved to '+d[key]['dir'])
                    h(key,d[key]['dir'])
                else:
                    log.warning( 'omitting dependency '+key+' because of missing result dir resolution')
            map(add_arg, d.keys())
        else:
            log.info( 'no multi component dependency resolutions found')

    def extension(self,aid,gid='com.sap.prd.xmake.extensions'):
        ga=gid+':'+aid+':zip'
        if not self.build_cfg.tools().is_declared_tool(aid):
            self.build_cfg.tools()._getTools()[aid]=PythonExtension(self.build_cfg.tools(),aid,ga)
        return self.build_cfg.tools()[aid]


    def deploy_variables(self):
        return {}

    def import_roots(self):
        return {}

    def import_variables(self):
        return {}

    def required_tool_versions(self):
        pass

    def plugin_imports(self):
        pass

    # override any of these to get notifications of phase completions
    def after_PRELUDE(self, build_cfg): pass
    def after_MODULES(self, build_cfg): pass
    def after_IMPORT(self, build_cfg): pass
    def after_BUILD(self, build_cfg): pass
    def after_EXPORT(self, build_cfg): pass
    def after_CREATE_STAGING(self, build_cfg): pass
    def after_DEPLOY(self, build_cfg): pass
    def after_CLOSE_STAGING(self, build_cfg): pass
    def after_PROMOTE(self, build_cfg): pass
    def after_FORWARD(self, build_cfg): pass

###################################################################
# Java Build Plugin Base Class
###################################################################

class JavaBuildPlugin(BuildPlugin):
    def __init__(self, build_cfg):
        self.build_cfg = build_cfg
        self.java_exec_env=log.ExecEnv()
        self._java_version = '1.8.0_20-sap-01'
        self._java_home = ''
        self._need_tools_import=False

    def java_set_option(self,o,v):
        raise XmakeException('ERR: build plugin %s does not define a method "java_set_option" with empty formal parameter list to execute the build' % self.__class__)

    def set_option(self,o,v):
        if o=='java-version':
            log.info( '  using java version ' + v)
            self._java_version = v
        else: self.java_set_option(o,v)

    def set_options(self, opts):
        versionOption = True
        for opt in opts:
            if versionOption:
                self.set_option('version', opt)
                versionOption = False
            else:
                splittedOpt=opt.split('=', 1);
                if len(splittedOpt)>1: self.set_option(splittedOpt[0], splittedOpt[1])
                else: self.set_option(None,opt);

    def java_required_tool_versions(self):
        pass

    def is_to_download(self):
        if self.build_cfg.runtime()=="ntamd64" or self.build_cfg.runtime()=="linuxx86_64"  or self.build_cfg.runtime()=="linux_x86_64": return True
        return False
        
    def need_tools(self):
        needed_tools=list()
        if self.is_to_download():
            self._need_tools_import=True
            def _map_installation(d,version):
                # if root directory only containn 1 subdir, then the jdk java_home is this subdir otherwise the jdk_javahome is the install dir d
                installationDirectoryContent=listdir(d)
                if(len(installationDirectoryContent)!=1): return d
                javaHomeToBeReturned=join(d,installationDirectoryContent[0]);
                if(isdir(javaHomeToBeReturned)): return javaHomeToBeReturned
                return d;
            needed_tools=[{'toolid': 'com.oracle.download.java:jdk', 'version': self._java_version, 'type':'tar.gz', "classifier":("linux-x64" if ExternalTools.OS_Utils.is_UNIX() else "windows-x64"), 'custom_installation': _map_installation}] 

        java_needed_tools=self.java_need_tools() if hasattr(self, 'java_need_tools') else None
        if java_needed_tools and len(java_needed_tools):
            needed_tools.extend(java_needed_tools)
        
        return needed_tools if len(needed_tools) else None

    def required_tool_versions(self):
        required=dict()
        if self.is_to_download(): required['java']=self._java_version
        java_required=self.java_required_tool_versions()
        if java_required is not None:
            required.update(java_required)
        if required: return required
        return None


    def java_run(self):
        raise XmakeException('ERR: build plugin %s does not define a method "java_run" with empty formal parameter list to execute the build' % self.__class__)

    def java_log_execute(self, args, handler=None):
        _java_exe="java{extension}".format(extension=("" if ExternalTools.OS_Utils.is_UNIX() else ".exe"))
        _args=[os.path.join(self._java_home, 'bin', _java_exe) if self._java_home else _java_exe]
        _args.extend(args)
        
        return self.java_exec_env.log_execute(_args,handler=handler)

        
    def java_set_environment(self,warn):
        if self.is_to_download():
            # if imported by need_tools (self._need_tools_import boolean) the toolid is not java anymore : but com.oracle.download.java:jdk  
            self._java_home = self.build_cfg.tools()['com.oracle.download.java:jdk' if self._need_tools_import else 'java'][self._java_version]
            self.java_exec_env.env['JAVA_HOME'] = self._java_home
            java_bin = os.path.join(self._java_home, 'bin')
            path = self.java_exec_env.env['PATH']
            if path == None:
                self.java_exec_env.env['PATH'] = java_bin
            elif path.find(java_bin) < 0:
                self.java_exec_env.env['PATH'] = os.pathsep.join([java_bin,path])
            
        elif warn:
            log.warning("Using default infrastructure Java version",log.INFRA)

    def run(self):
        self.java_set_environment(True);
        return self.java_run()

    #######################################################################################
    # build result forwarding
    # by default the build script cheks for a forwarding plugin forward.py.

    def forward_buildresults(self):
        f=join(self.build_cfg.cfg_dir(),"forward.py")
        if is_existing_file(f):
            p=self.acquire_forwarding_script(self.build_cfg, f)
            if p is not None:
                p.run()
        else:
            log.warning("no forwarding script 'forward.py' found in cfg folder")

    def acquire_forwarding_script(self, build_cfg, plugin_path):
        #dynamically load custom build script
        log.info( 'loading forwarding plugin '+plugin_path)
        plugin_code = compile(open(plugin_path, "rt").read(), plugin_path, "exec")
        plugin_dict = {
                "__name__": "forwardplugin",
                "object": _ObjectBase,
        }
        exec plugin_code in plugin_dict

        try:
            forward_script_class = plugin_dict["forward"]
        except KeyError:
            log.error( "custom forwarding script must define a class 'forward' - no such class def found at: " + plugin_path)
            raise XmakeException("failed to instantiate 'forward' (no such class def found)")

        #check for existence of c'tor w/ one formal parameter
        if not len(inspect.getargspec(forward_script_class.__init__)[0]) == 2:
            log.error( "custom forward class must implement a c'tor w/ exactly one formal parameter (which is of type BuildConfig)")
            raise XmakeException("failed to instantiate 'forward' (no c'tor def w/ correct amount of formal parameters (which is one) found)")
        if not len(inspect.getargspec(forward_script_class.run)[0]) == 1:
            log.error( "custom forward class must implement a method 'run' w/ exactly one formal parameter (which is of type BuildConfig)")
            raise XmakeException("failed to instantiate 'forward' (no method 'run' def w/ correct amount of formal parameters (which is one) found)")

        forward_script = forward_script_class(build_cfg)

        return forward_script


class VariantBuildPlugin(BuildPlugin):
    def __init__(self, build_cfg):
        BuildPlugin.__init__(self,build_cfg)
        self._variant_cosy_gav=None

    def set_option(self,o,v):
        if o=="cosy":
            if len(v.split(':'))==2:
                log.info( '  using coordinate system '+v)
                self._variant_cosy_gav=v
            else:
                raise XmakeException('ERR: invalid coordinate system specification '+str(v)+': expected <name>:<version>')
        else:
            BuildPlugin.set_option(self,o,v)

    def variant_cosy_gav(self):
        return self._variant_cosy_gav

###################################################################
# Tool Base Class
###################################################################

class Tool(object):
    def __init__(self, tools, toolid):
        self._tools = tools
        self._toolid = toolid
        self._tags=[]

    def toolid(self):
        return self._toolid

    def imports(self, version):
        assert version is not None
        assert isinstance(version, str)
        return []

    def tool(self,version):
        assert version is not None
        assert isinstance(version, str)
        raise XmakeException('ERR: tool %s does not define a function "tool"' % (self.toolid))

    def has_tag(self,tag):
        try:
            self._tags.index(tag)
            return True
        except ValueError:
            return False

    def tags(self): return self._tags

    def __getitem__(self,version):
        return self.tool(version)

#
# Base Class for Tools based on a simple downloaded archives
# If not found centrally on the tools depot or in a local installation directory, the tool
# is requested for download and installed in a local installation directory if it is not yet available.
# The download is skipped completely, if the tool is already available.
# The local installation directory is retrieved from the Tools object and can be shared among multiple, potentially
# parallel build executions
#
class ArchiveBasedTool(Tool):
    def __init__(self, tools, toolid):
        Tool.__init__(self,tools,toolid)
        self._archive=True
#        def retrieve(version):
#            return join(self._tools.import_tools_dir(),self._installation_archive(version))
#        self._appcache=appcache.AppCache('tool '+toolid, join(tools.tool_install_dir(),toolid),retrieve)

    def tool(self, version):
        d=self._tools.tool_installation_cache().get(self._tools.mapToolGAVStr(self._imports(version)[0]),
                                       lambda aid: join(self._tools.import_tools_dir(),self._installation_archive(aid[-1])),archive=self._archive)
#        d=self._appcache.get(version)
        return self._map_installation(d,version)

    def imports(self,version):
        return self._imports(version)

    # return the GA part of the zipped distribution, classifier is optionally possible
    # use the short notation of the artifact imported (3 or 4 parts), the version will implicitly be added later
    def _import(self):
        raise XmakeException("method _import must be implemented and return the base GA without version")

    # the distribution archive is installed into the local installation directory using a directory structure consisting
    # of the group/artifact id and the version. By default the root of the unzipped archive is returned as tool hint.
    # Implementing this method a sub folder may be selected to be returned
    def _map_installation(self,d,version):
        return d

    def _imports(self, version):
        return [ self._import()+':'+version]

    def _installation_archive(self,version):
        imp=self._imports(version)[0].split(':')
        if len(imp)==5:
            return imp[1]+'-'+imp[4]+'-'+imp[3]+'.'+imp[2]
        return imp[1]+'-'+imp[3]+'.'+imp[2]

    # implement this method if there is a chance to find the tool on the central tools depot mirror
    def _global_lookup(self,version):
        return None
#
#
#
class StandardTool(ArchiveBasedTool):
    def __init__(self, tools, toolid, ga, path=None, archive=True):
        ArchiveBasedTool.__init__(self,tools,toolid)
        self._archive=archive
        imp=ga.split(':')
        if len(imp)<=2:  # add default type
            ga=ga+":"+zip

        self._ga=ga
        if hasattr(path, '__call__'):
            self._path=path
        else:
            self._path=validate_path(path)

    def _import(self):
        return self._ga

    def _map_installation(self,d,version):
        if self._path==None:
            return d
        if hasattr(self._path, '__call__'):
            return self._path(d, version)
        return join(d,self._path)

class PythonExtension(StandardTool):
    def tool(self, version):
        p=StandardTool.tool(self,version)
        if not p in sys.path:
            sys.path.append(p)
        return p


###################################################################
# Content Plugin Base Class
###################################################################

class ContentPlugin(object):

    def __init__(self, build_cfg):
        self.build_cfg = build_cfg

    # evaluate the component source
    # should return whether it mazches the content (true) or not (false).

    def matches(self):
        return False

    def setup(self):
        raise XmakeException('ERR: content plugin %s not implemented' % self.__class__)

    def validate_project(self):
        return False

