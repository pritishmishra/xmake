'''
Created on 23.12.2013

@author: Christian Cwienk (d051236)
'''

import multiprocessing, os
from os.path import join

import ExternalTools, utils
import spi
import log
from ExternalTools import tool_gav, is_gav
import utils
from xmake_exceptions import XmakeException
from const import XMAKE_NEXUS
from urlparse import urlparse

COMMONREPO='Common'
NPMREPO='NPM'
DOCKERREPO='Docker'

XMAKE_CFG="xmake.cfg"

class ConfiguredTool(object):
    def __init__(self,name,version,tags=[],tid=None):
        self._name=name
        self._tid=name if tid==None else tid
        self._version=version
        self._inst_dir=None
        self._tags=tags

    def label(self): return self._tid if self._tid==self._name else (self._tid+'['+self._name+']')
    def name(self): return self._name
    def toolid(self): return self._tid
    def version(self):  return self._version
    def inst_dir(self): return self._inst_dir

    def has_tag(self,tag):
        try:
            self._tags.index(tag)
            return True
        except ValueError:
            return False

    def tags(self): return self._tags

class PythonDependency(object):
    def __init__(self,name,gav):
        relative=True
        self._name=name
        if is_gav(gav):
            gav=tool_gav(gav,True)
            self._gav=gav
            if len(self._gav)==6:
                self._path=gav[5]
                self._gav=gav[:5]
            else:
                self._path=None
        else:
            self._gav=None
            self._path=gav
            relative=False
        self._path=utils.validate_path(self._path,relative)

    def name(self): return self._name
    def gav(self): return self._gav
    def gavstr(self):
        return ':'.join(self._gav if len(self._gav[3])>0 else [ self._gav[0], self._gav[1], self._gav[2], self._gav[4]])
    def path(self): return self._path

    def has(self,build_cfg):
        comp=self._gav
        if comp==None: return True
        return build_cfg.tools().tool_installation_cache().has((comp[0],comp[1],comp[4]))

    def get(self,build_cfg):
        comp=self._gav
        if comp==None: return self.path()
        d=build_cfg.tools().tool_installation_cache().get((comp[0],comp[1],comp[4]),
                                       lambda aid: self.installation_archive(build_cfg),'python dependency')
        if self._path==None: return d
        return join(d,self._path)

    def installation_archive(self,build_cfg):
        return join(build_cfg.import_python_dir(),self._installation_archive())

    def _installation_archive(self):
        imp=self._gav
        if len(imp[3])==0:
            return imp[1]+'-'+imp[4]+'.'+imp[2]
        return imp[1]+'-'+imp[4]+'-'+imp[3]+'.'+imp[2]


class BuildConfig:
    '''a xmake build configuration contains all required settings that describe a build.

    some values (such as the project root directory) are configurable, others (such as the
    location of the configuration directory (<projroot>/cfg) are not configurable and are derived
    from other values
    '''
    def __init__(self):
        self._args=None
        self._xmake_file=None
        self._xmake_cfg=None

        self._tools = None
        self._tools_to_be_installed = {}
        self._configured_tools=dict()
        self._configured_plugindeps=dict()
        self._component_dir = None

        self._runtime=utils.runtime()
        self._family = "unix" if ExternalTools.OS_Utils.is_UNIX() else "windows"
        try:
            self.xmake_nbcpu = multiprocessing.cpu_count()
        except NotImplementedError as e:
            log.error("the number of CPUs in the system is not available: %s." % e.message, log.INFRA)

        ###
        # initialise default values
        self._import_repos={ COMMONREPO: ['https://nexus.wdf.sap.corp:8443/nexus/content/groups/build.milestones/'],
                             NPMREPO:    ['http://nexus.wdf.sap.corp:8081/nexus/content/groups/build.milestones.npm/'],
                             DOCKERREPO: ['dockerdevregistry.wdf.sap.corp:5000']
                           }
        self._export_repos={ COMMONREPO: 'https://nexus.wdf.sap.corp:8443/nexus/content/repositories/deploy.snapshots/',
                             DOCKERREPO: 'dockerdevregistry.wdf.sap.corp:5000'
                           }
        self._forwarding_dir = None
        self._profiling = None

        self._import_scripts = lambda:[join(self.cfg_dir(), 'import.ais')]
        self._export_script = lambda: join(self.cfg_dir(), 'export.ads')
        self._deploy_users = {}
        self._deploy_passwords = {}
        self._deploy_cred_keys = {}

        self._variant_cosy = None
        self._variant_cosy_gav = None
        self._variant_coords = None
        self._variant_vector = None


        self._build_mode = None
        self._build_platform = None
        self._variant_info = dict()

        self._externalplugin_setup = None
        self._content_plugin = None

        self._label = None
        self._do_import = False
        self._do_export = False
        self._do_create_staging = False
        self._do_close_staging = False
        self._do_deploy = False
        self._do_promote = False
        self._do_drop_staging = False
        self._staging_repoid_parameter=None
        self._do_custom_deploy = False
        self._do_clean = False
        self._do_purge_all = False
        self._skip_build = False
        self._skip_test = False
        self._build_script_file = None
        self._build_script_settings = None # settings from build.cfg
        self._build_script_options = None # dict
        self._build_script_name = 'vmake' #default to vmake
        self._build_script_version = None
        self._build_script = None
        self._scm_snapshot_url = None
        self._productive = False
        self._release = None
        self._debug_xmake=False
        self._alternate_path=None
        self._externalplugins_nexus_url=None
        self._get_version=None
        self._set_version=None
        self._created_staging_repoid=None


        self._src_dir = None
        self._genroot_dir = None
        self._externalplugins_dir = None # root directory of all external plugins
        self._externalplugin_dir = None # directory of selected external plugin
        self._build_args = []
        self._version = None
        self._base_version = None
        self._version_suffix = None
        self._base_group = None
        self._base_artifact = None

        self._xmake_version=None

        self._additional_metadata = []
        self._dependency_file_arg = None
        self._dependency_file = None
        self._dependency_config = None
        self._suppress_variant_handling = False

    def xmake_file(self): return self._xmake_file

    def runtime(self): return self._runtime
    def family(self): return self._family
    def runtime_gid(self,gid,is_variant=True): return utils.runtime_gid(gid,rt=self.runtime()) if is_variant==True else gid
    def runtime_classifier(self,c,is_variant=True): return utils.runtime_classifier(c,rt=self.runtime()) if is_variant==True else c
    def bit_count(self): return utils.get_bit_count(self.runtime())

    def is_tool_debug(self): return self._debug_xmake

    def tools(self): return self._tools

    def add_tool_to_be_installed(self,tid,gav):
        if not self._tools_to_be_installed.has_key(tid):
            self._tools_to_be_installed[tid]=[]
        self._tools_to_be_installed[tid].append(gav)
    def tools_to_be_installed(self): return self._tools_to_be_installed

    def configured_tools(self): return self._configured_tools
    def configured_plugin_deps(self): return self._configured_plugindeps

    def component_dir(self): return self._component_dir
    def label(self): return self._label if self._label else 'gen'
    def label_name(self): return 'gen_'+self.label() if self.label()!='gen' else 'gen'
    def do_clean(self): return self._do_clean
    def do_purge_all(self): return self._do_purge_all
    def skip_build(self): return True if (self.get_next_version() is not None or self.get_project_version() == True) else  self._skip_build
    def skip_test(self): return self._skip_test
    def build_args(self): return self._build_args


    def build_platform(self): return self._build_platform
    def build_mode(self): return self._build_mode

    def suppress_variant_handling(self): return self._suppress_variant_handling
    def variant_info(self): return self._variant_info
    def variant_cosy_gav(self): return self._variant_cosy_gav
    def variant_cosy(self): return self._variant_cosy
    def variant_coords(self): return self._variant_coords
    def variant_vector(self): return self._variant_vector

    def content_plugin(self):
        return self._content_plugin

    def externalplugin_setup(self):
        return self._externalplugin_setup

    def custom_build_script_file(self): return join(self.cfg_dir(), 'build.py')
    def build_script_name_file(self): return join(self.cfg_dir(),'build.scriptname')

    def build_script_file(self):
        script_file = self.custom_build_script_file() if self._build_script_file is None else self._build_script_file
        return script_file# if os.path.isfile(script_file) else None # To support external plugin folder
    def build_script(self): return self._build_script
    def build_script_settings(self): return self._build_script_settings
    def build_script_options(self): return self._build_script_options
    def build_script_name(self): return self._build_script_name
    def build_script_version(self): return self._build_script_version
    def build_script_ext_dir(self): return join(self.component_dir(), 'bse')
    def get_project_version(self): return self._get_version
    def get_next_version(self): return self._set_version

    def get_staging_repoid_parameter(self): return self._staging_repoid_parameter
    def set_staging_repoid_parameter(self,repoId):
        self._staging_repoid_parameter=repoId
        return self
    def get_created_staging_repoid(self): return self._created_staging_repoid
    def set_created_staging_repoid(self,created_staging_repoid):
        self._created_staging_repoid=created_staging_repoid
        return self

    def add_build_script_option(self,o,v):
        if self._build_script_options is None:
            self._build_script_options={}
        self._build_script_options[o]=v

    def add_default_build_script_option(self,o,v):
        if self._build_script_options is None:
            self._build_script_options={}
        if not self._build_script_options.has_key(o):
            self._build_script_options[o]=v

    def vmake_instdir(self): return self._tools.vmake_instdir()
    def import_scripts(self): return self._import_scripts()
    def export_script(self): return self._export_script()
    def import_root_dir(self): return join(self.component_dir(), 'import')
    def import_file(self,suffix=None): return join(self.genroot_dir(), 'xmake.imported-artifacts'+(suffix if suffix!= None else ''))
    def import_dir(self): return join(self.import_root_dir(),'content')
    def import_tools_dir(self): return join(self.import_root_dir(),'tools')  # folder used to store imported tools
    def import_python_dir(self): return join(self.import_root_dir(),'python')  # folder used to store imported python dependencies
    def export_dir(self): return join(self.genroot_dir(), 'export')
    def export_file(self): return join(self.export_dir(), 'export.df')
    def deployment_info_log(self): return join(self.genroot_dir(), 'deploymentInfo.log')
    def cfg_dir(self): return join(self.component_dir(), 'cfg')
    def src_dir(self): return self._src_dir if self._src_dir is not None else join(self.component_dir(), 'src')
    def genroot_dir(self): return self._genroot_dir if self._genroot_dir is not None else join(self.component_dir(), self.label_name())
    def externalplugins_dir(self): return self._externalplugins_dir if self._externalplugins_dir is not None else join(self.component_dir(), '.xmake', 'externalplugins')
    def externalplugin_dir(self): return self._externalplugin_dir
    def module_genroot_dir(self): return join(self.genroot_dir(), 'modules')
    def forwarding_dir(self): return self._forwarding_dir
    def forwarding_destination(self):
        if self._forwarding_dir is None: return None
        if self.suppress_variant_handling(): return self._forwarding_dir
        p=self._forwarding_dir
        for x in self.variant_vector(): p=join(p,x)
        return p
    def profilings(self):
        if self._profiling:
            profilings = self._profiling.split(',')
            if len(profilings[-1])==0:
                profilings.pop()
            return profilings
        return self._profiling
    def gen_dir(self): return join(self.genroot_dir(), 'out')

    def set_src_dir(self,d):
        self._src_dir=d
    def export_repo(self,t=COMMONREPO): return utils.get_entry(self._export_repos, t)
    def import_repos(self,t=COMMONREPO):
        repos = utils.get_entry(self._import_repos, t)
        if self.productive() or self.is_release() or self.is_milestone():
            return [repos[0]] if repos and len(repos)>0 else repos
        return repos
    def deploy_cred_key(self,t=COMMONREPO): return utils.get_entry(self._deploy_cred_keys,t)

    def add_import_repo(self,r,t=COMMONREPO):
        if self.productive() or self.is_release() or self.is_milestone():
            repos = utils.get_entry(self._import_repos, t)
            if repos and len(repos) >= 1:
                raise XmakeException('only one repository url is authorized for productive or/and release build. See {} urls passed in --import-repo argument'.format(t))
        utils.add_list_entry(self._import_repos, t, r)

    def set_import_repos(self,r,t=COMMONREPO):
        if self.productive() or self.is_release() or self.is_milestone():
            if r and len(r) >= 1:
                raise XmakeException('only one repository url is authorized for productive or/and release build. See {} urls passed in --import-repo argument'.format(t))
        self._import_repos[t]=r

    def set_export_repo(self,r,t=COMMONREPO):
        self._export_repos[t]=r
    def set_deploy_cred_key(self,r,t=COMMONREPO):
        self._deploy_cred_keys[t]=r
    def set_deploy_user(self,r,t=COMMONREPO):
        self._deploy_users[t]=r
    def set_deploy_password(self,r,t=COMMONREPO):
        self._deploy_passwords[t]=r

    def deploy_user(self,t=COMMONREPO): return utils.get_entry(self._deploy_users,t)
    def deploy_password(self,t=COMMONREPO): return utils.get_entry(self._deploy_passwords,t)

    def set_export_script(self,s):
        self._export_script=lambda:s

    def do_import(self): return self._do_import
    def do_export(self): return self._do_export
    def do_create_staging(self): return self._do_create_staging
    def do_close_staging(self): return self._do_close_staging
    def do_drop_staging(self): return self._do_drop_staging
    def do_deploy(self): return self._do_deploy
    def do_promote(self): return self._do_promote
    def do_custom_deploy(self): return self._do_custom_deploy
    def set_custom_deploy(self, v): self._do_custom_deploy=v

    def version_suffix(self): return self._version_suffix
    def base_version(self): return self._base_version
    def base_group(self): return self._base_group
    def base_artifact(self): return self._base_artifact
    def set_base_version(self,v): self._base_version=v
    def set_base_group(self,v): self._base_group=v
    def set_base_artifact(self,v): self._base_artifact=v
    def set_version(self,v): self._version=v
    def version(self): return self._version

    def scm_snapshot_url(self): return self._scm_snapshot_url
    def productive(self): return self._productive
    def is_release(self): return self._release
    def is_milestone(self):
        return  not self.is_release() and   self._productive and (self._version_suffix == None or
                    not (self._version_suffix == 'SNAPSHOT' or self._version_suffix.endswith("-SNAPSHOT")))
    def release_metadata_file(self): return join(self.genroot_dir(), 'xmake.release-metadata') if self.scm_snapshot_url() is not None else None
    def version_properties_file(self): return join(self.export_dir(), 'version.properties')

    def temp_dir(self): return join(self.genroot_dir(), 'tmp')

    def project_version_file(self): return join(self.temp_dir(), 'project.version')
    def promote_props_file(self): return join(self.temp_dir(), 'promote.properties')
    def close_stage_props_file(self): return join(self.temp_dir(), 'close_stage.properties')
    def staging_props_file(self): return join(self.temp_dir(), 'staging.properties')
    def addtional_metadata(self): return self._additional_metadata
    def add_metadata_file(self,m): self._additional_metadata.append(m)

    def dependency_file(self): return self._dependency_file
    def dependency_config(self): return self._dependency_config if self._dependency_config is not None else dict()
    def dependency_save_file(self): return join(self.genroot_dir(), 'multi-component-resolutions')
    def result_base_dir(self): return join(self.genroot_dir(),'results')

    def xmake_version(self): return self._xmake_version

    # config api for content plugins
    def set_build_plugin(self,p):
        if isinstance(p, str):
            if p.endswith('.py'):
                self._build_script_file=p
            else:
                self._build_script_name=p
        else:
            if issubclass(type(p), spi.BuildPlugin):
                self._build_script=p
            else:
                raise XmakeException("unknown kind of build plugin spec: "+str(p))

    def xmake_cfg(self):
        if self._xmake_cfg is None:
            cfg=None
            if utils.is_existing_directory(self.cfg_dir()):
                cfg=join(self.cfg_dir(),XMAKE_CFG)

            if cfg is None or not utils.is_existing_file(cfg):
                cfg=join(self.component_dir(),"."+XMAKE_CFG)

            if utils.is_existing_file(cfg):
                log.info("found xmake.cfg...")
                config = utils.IterableAwareCfgParser()
                config.read(cfg)
                self._xmake_cfg=config
        return self._xmake_cfg

    def alternate_path(self):
        v=self._alternate_path
        if v is None:return v
        f=join(self.component_dir(),v)
        if utils.is_existing_directory(f):
            return v
        relPath = ''
        dirs = v.split('.')
        relPath=os.sep.join(dirs)
        return relPath
    
    def externalplugins_nexus_url(self):
        if self._externalplugins_nexus_url: return self._externalplugins_nexus_url
        
        o=urlparse(self.import_repos()[0] if self.import_repos() else XMAKE_NEXUS)
        return "{scheme}://{netloc}".format(scheme=o.scheme,netloc=o.netloc)
    