'''
implementation of the xmake 'PRELUDE' phase. This phase is by definitionem the
first phase to be executed. It deals w/ command-line parsing and preprocessing

Created on 03.01.2014

@author: Christian Cwienk (d051236)
'''
from os.path import join, isfile, isdir, abspath, pardir, exists, basename
from os import getcwd, makedirs
import logging
import sys, os, re
import imp
import inspect
import platform
import spi
import log
import options
import inst
import utils

from const import XMAKE_BUILD_PLATFORM, XMAKE_BUILD_MODE
from glob import glob
from shutil import copyfile
from optparse import OptionValueError
from utils import IterableAwareCfgParser, is_existing_file, is_existing_directory
from ExternalTools import Tools
from config import BuildConfig, ConfiguredTool, PythonDependency, COMMONREPO
from ExternalTools import OS_Utils, tool_gav, is_gav
from xmake_exceptions import XmakeException

from utils import get_first_line, contains, validate_path, has_method
from buildplugin import acquire_custom_variant_data
from commonrepo import prepare_ai_command, create_import_script, execute_ai, assert_import_file, update_import_file
from commonrepo import append_import_file

import builtinplugins
import externalplugins

XMAKE_FILE_NAME               = '.xmake'

XMAKE_SECTION_SRC             = 'Source'
XMAKE_SRC_PRJ_ROOT            = 'project-root'
XMAKE_SECTION_BUILD           = 'Build'
XMAKE_BUILD_LABEL             = 'label'
XMAKE_BUILD_ARGS              = 'args'
XMAKE_BUILD_GENDIR            = 'gendir'
XMAKE_BUILD_FORWARDING        = 'forwarding'
XMAKE_BUILD_SCRIPT            = 'build_script'
XMAKE_SECTION_MC              = 'MultiComponent'
XMAKE_MC_DEPENDENCIES         = 'dependency-file'
XMAKE_SECTION_REPO            = 'Repo'
XMAKE_REPO_IMPORT_REPOS       = 'import-repos'
XMAKE_REPO_EXPORT_REPO        = 'export-repo'
XMAKE_REPO_DEPLOY_CRED_HANDLE = 'deploy-credential-handle'
XMAKE_REPO_DEPLOY_USER        = 'deploy-user'
XMAKE_SECTION_BV              = "BuildVariant"
XMAKE_SECTION_BPO             = "BuildPluginOptions"

def _gendir_name(label):
    return 'gen_'+label if label != 'gen' else 'gen'

def _lookup_xmake(directory, label):
    gendir_label=_gendir_name(label)
    # first lookup .xmake file if pwd is genroot_dir
    xmake_path = join(directory, XMAKE_FILE_NAME)
    if isfile(xmake_path): return xmake_path
    # look for .xmake file in project root (pwd not genroot_dir or below)
    xmake_path = join(directory, gendir_label, XMAKE_FILE_NAME)
    if isfile(xmake_path): return xmake_path
    if isdir(xmake_path): raise 'expected a file: ' + xmake_path
    parent = abspath(join(directory, pardir))

    if parent == directory: return None
    return _lookup_xmake(parent, gendir_label)

def _lookup_project_root(directory):
    log.info("checking "+directory+" for project root")
    if is_root_directory(directory):
        return directory
    parent = abspath(join(directory, pardir))

    if parent == directory: return None
    return _lookup_project_root(parent)

def is_root_directory(d):
    if is_existing_directory(join(d,'.git')):
        return True
    if is_existing_file(join(d,'.xmake.cfg')):
        return True
    if is_existing_file(join(d,'.XMAKE_VERSION')):
        return True
    if not is_existing_directory(join(d,'cfg')):
        return False
    if is_existing_file(join(d,'cfg',"xmake.cfg")):
        return True
    if is_existing_file(join(d,'cfg',"VERSION")):
        return True
    if is_existing_file(join(d,'cfg',"XNMAKE_VERSION")):
        return True
    return is_existing_directory(join(d,'src'))

def determine_xmake_file(args, build_cfg):
    log.info("determing project root...")
    gendir_label = args.gendir_label if args.gendir_label is not None else build_cfg.label()

    if args.project_root_dir is None:
        log.info("\tno explicit root given")
        # first check for existing xmake file
        xmake_file = _lookup_xmake(getcwd(), gendir_label)
        # if not available and no root explicitly set, fake root arg, if called in standard project directory
        if xmake_file is None:
            log.info("\tno .xmake")
            d=_lookup_project_root(getcwd())
            if d is not None:
                args.project_root_dir=d
        else:
            log.info("\tfound "+xmake_file)
    else:
        log.info("\tgiven root "+args.project_root_dir)
    if args.gendir is not None:
        xmake_file = join(args.gendir, XMAKE_FILE_NAME)
    else:
        if args.project_root_dir is not None:
            xmake_file = join(args.project_root_dir, _gendir_name(gendir_label), XMAKE_FILE_NAME)
        else:
            if xmake_file is None:
                if args.show_version:
                    log.info("no build project found")
                    sys.exit(0)
                raise XmakeException('could not find .xmake file in pwd and parent directories (started from: ' + getcwd() + "')")
    return xmake_file

def parse_xmake_file(args, config_parser, build_cfg):
    xmake_file = determine_xmake_file(args, build_cfg)
    return load_xmake_file(xmake_file,config_parser,build_cfg)

def load_xmake_file(xmake_file, config_parser, build_cfg):
    #skip if no .xmake file is present
    if xmake_file is None or not isfile(xmake_file): return None

    def transfer_cfg(section, cfg_prop, build_cfg_attr):
        if not config_parser.has_option(section, cfg_prop): return
        value = config_parser.get(section, cfg_prop)
        attr='_' + build_cfg_attr
        a=getattr(build_cfg,attr)
        if type(a) is dict:
            a[COMMONREPO]=value
        else:
            setattr(build_cfg, attr, value)

    config_parser.read(xmake_file)

    xmake_to_cfg_attr = [(XMAKE_SECTION_SRC, [(XMAKE_SRC_PRJ_ROOT, 'component_dir')]),
                         (XMAKE_SECTION_BUILD,
                          [(XMAKE_BUILD_ARGS, 'build_args'),
                           (XMAKE_BUILD_LABEL, 'label'),
                           (XMAKE_BUILD_PLATFORM, 'build_platform'),
                           (XMAKE_BUILD_MODE, 'build_mode'),
                           (XMAKE_BUILD_GENDIR, 'genroot_dir'),
                           (XMAKE_BUILD_FORWARDING, 'forwarding_dir'),
                           (XMAKE_BUILD_SCRIPT, 'build_script_file')
                           ]),
                         (XMAKE_SECTION_MC,
                          [(XMAKE_MC_DEPENDENCIES, 'dependency_file'),
                           ])
                         ]

    map(lambda (section, mappings): map(lambda (xmake_attr, cfg_attr): transfer_cfg(section, xmake_attr, cfg_attr), mappings), xmake_to_cfg_attr)
    def transfer_coord(prop):
        build_cfg.variant_info()[prop[0]] = prop[1]
    build_cfg.variant_info().clear()
    if (config_parser.has_section(XMAKE_SECTION_BV)):
        map(transfer_coord, config_parser.items(XMAKE_SECTION_BV))

    def transfer_options(prop):
        build_cfg.add_build_script_option(prop[0], prop[1])
    if (config_parser.has_section(XMAKE_SECTION_BPO)):
        map(transfer_options, config_parser.items(XMAKE_SECTION_BPO))

    for s in config_parser.sections():
        if s.endswith(XMAKE_SECTION_REPO):
            t=s[:-len(XMAKE_SECTION_REPO)]
            if config_parser.has_option(s,XMAKE_REPO_EXPORT_REPO):
                build_cfg.set_export_repo(config_parser.get(s,XMAKE_REPO_EXPORT_REPO),t)
            if config_parser.has_option(s,XMAKE_REPO_IMPORT_REPOS):
                build_cfg.set_import_repos(config_parser.get(s,XMAKE_REPO_IMPORT_REPOS),t)
            if config_parser.has_option(s,XMAKE_REPO_DEPLOY_CRED_HANDLE):
                build_cfg.set_deploy_cred_key(config_parser.get(s,XMAKE_REPO_DEPLOY_CRED_HANDLE),t)
            if config_parser.has_option(s,XMAKE_REPO_DEPLOY_USER):
                build_cfg.set_deploy_user(config_parser.get(s,XMAKE_REPO_DEPLOY_USER),t)

    return xmake_file

def apply_cmdline_args(args, buildtool_args, variant_info, build_cfg):
    '''overwrites existing build cfg settings from previous builds with those from command line args'''

    def transfer_arg(arg, build_cfg_attr):
        value = getattr(args, arg)
        if value is not None:
            setattr(build_cfg, '_' +build_cfg_attr, value)
    #mapping between cli arg attribs and build_cfg attribs
    cli_arg_to_cfg_attr = [('project_root_dir', 'component_dir'),
                           ('gendir_label',     'label'),
                           ('gendir',           'genroot_dir'),
                           ('forwarding',       'forwarding_dir'),
                           ('profiling',        'profiling'),
                           ('mode',             'build_mode'),
                           ('platform',         'build_platform'),
                           ('do_import',        'do_import'),
                           ('build_script',     'build_script_file'),
                           ('alternate_path',   'alternate_path'),
                           ('dependency_file',  'dependency_file'),
                           ('do_export',        'do_export'),
#                            ('do_deploy',        'do_export'), #deployment implies export
                           ('do_deploy',        'do_deploy'),
                           ('do_promote',       'do_promote'),
                           ('do_clean',         'do_clean'),
                           ('do_purge_all',     'do_purge_all'),
                           ('skip_build',       'skip_build'),
                           ('skip_test',        'skip_test'),
                           ('scm_snapshot_url', 'scm_snapshot_url'),
                           ('xmake_version',    'xmake_version'),
                           ('debug_xmake',      'debug_xmake'),
                           ('base_version',     'base_version'),
                           ('release',          'release'),
                           ('get_version',      'get_version'),
                           ('set_version',      'set_version'),
                           ('staging_repoid',   'staging_repoid_parameter'),
                           ('do_create_staging','do_create_staging'),
                           ('do_close_staging', 'do_close_staging'),
                           ('do_drop_staging',  'do_drop_staging'),
                           ('productive',       'productive')]

    if variant_info.has_key(XMAKE_BUILD_MODE):
        build_cfg._build_mode=None
    if variant_info.has_key(XMAKE_BUILD_PLATFORM):
        build_cfg._build_platform=None

    map(lambda (cli, attr): transfer_arg(cli,attr), cli_arg_to_cfg_attr)

    # handle repo specs
    _handle_list(args.import_repos, build_cfg._import_repos,utils.add_list_entry)
    _handle_list(args.export_repos, build_cfg._export_repos,utils.set_single_entry, True)
    _handle_list(args.deploy_cred_keys, build_cfg._deploy_cred_keys,utils.set_single_entry)
    _handle_list(args.deploy_users, build_cfg._deploy_users,utils.set_single_entry)
    _handle_list(args.deploy_passwords, build_cfg._deploy_passwords,utils.set_single_entry)

    # apply deprecated variant value options
    if (build_cfg.build_mode()!=None):
        variant_info[XMAKE_BUILD_MODE]=build_cfg.build_mode()
    if (build_cfg.build_platform()!=None):
        variant_info[XMAKE_BUILD_PLATFORM]=build_cfg.build_platform()

    if build_cfg.component_dir is None:build_cfg.component_dir='.'
    if (len(variant_info)>0):
        build_cfg.variant_info().clear()
        build_cfg.variant_info().update(variant_info)
    build_cfg._build_args = buildtool_args if buildtool_args else None

    def gather_options(value):
        try:
            i=value.index('=')
            c=value[:i]
            value=value[i+1:]
            build_cfg.add_build_script_option(c,value)
        except ValueError:
            raise OptionValueError('option assignment expected instead of "'+value+'"')
    if args.options is not None:
        if build_cfg._build_script_options is not None:
            log.info("resetting remembered build plugin options")
            build_cfg._build_script_options.clear()
        map(gather_options,args.options)

def _handle_list(list,map,add,firstDuplicatedKeyOnly=False):
    if list is not None:
        done=set()
        for e in list:
            i=e.find('=')
            if i>=0:
                t=e[:i]
                r=e[i+1:]
            else:
                t=COMMONREPO
                r=e
            alreadyDone=t in done # status will be re used later for DTXMAKE-1115
            if not alreadyDone: # reset always default values to explicit settings
                done.add(t)
                if map.has_key(t):
                    del map[t]
            # related to jira https://sapjira.wdf.sap.corp/browse/DTXMAKE-1115
            # under some specific circunstances, when the same key is mentionned multiple times, only the first one must be takine in account
            # (see jira item for more information) 
            if firstDuplicatedKeyOnly==False or not alreadyDone:
                add(map,t,r)

def determine_version_suffix(build_cfg, version):
    if not build_cfg.productive() and ( version is None or len(version) == 0):
        version='SNAPSHOT'
    if not version is None: version=version.strip()
    if version is None or len(version) == 0:
        build_cfg._version_suffix = None
    else:
        if version.startswith('-'): version = version[1:]
        build_cfg._version_suffix = version
    return build_cfg.version_suffix()


def _determine_version_from_config(build_cfg, version_suffix):
    config=build_cfg.xmake_cfg()
    if config is not None:
        s='xmake'
        if config.has_section(s):
            if config.has_option(s,'version'):
                build_cfg._base_version=config.get(s,'version')

    version_file = join(build_cfg.cfg_dir(), 'VERSION')
    if not isfile(version_file):
        if build_cfg._base_version is None:
            return False
            #raise XmakeException('VERSION file must exist at: '+ version_file)
        #else:
        base_version=build_cfg._base_version
    else:
        base_version=get_first_line(version_file,'no version defined in VERSION file: ' + version_file)
        build_cfg._base_version = base_version

    version_suffix=determine_version_suffix(build_cfg,version_suffix)

    if version_suffix is None:
        build_cfg._version = base_version
    else:
        build_cfg._version = base_version + "-" + version_suffix
    return True

def write_xmake_file(config_parser, build_cfg, xmake_file):
    def add_section(s):
        if not config_parser.has_section(s):config_parser.add_section(s)
    map(add_section, [XMAKE_SECTION_BUILD, XMAKE_SECTION_SRC])
    def set_if_not_none(section,prop,val):
        if val is None: return
        add_section(section)
        config_parser.set(section,prop,val)

    set_if_not_none(XMAKE_SECTION_SRC, XMAKE_SRC_PRJ_ROOT, build_cfg.component_dir())
    set_if_not_none(XMAKE_SECTION_BUILD, XMAKE_BUILD_LABEL, build_cfg.label())
    set_if_not_none(XMAKE_SECTION_BUILD, XMAKE_BUILD_ARGS, build_cfg.build_args())
    set_if_not_none(XMAKE_SECTION_BUILD, XMAKE_BUILD_PLATFORM, build_cfg.build_platform())
    set_if_not_none(XMAKE_SECTION_BUILD, XMAKE_BUILD_MODE, build_cfg.build_mode())
    set_if_not_none(XMAKE_SECTION_BUILD, XMAKE_BUILD_GENDIR, build_cfg.genroot_dir())
    set_if_not_none(XMAKE_SECTION_BUILD, XMAKE_BUILD_FORWARDING, build_cfg.forwarding_dir())

    keys=set(build_cfg._export_repos.keys())
    keys.update(build_cfg._import_repos.keys())

    def handle_repotype(t):
        s=t+XMAKE_SECTION_REPO
        add_section(s)
        set_if_not_none(s, XMAKE_REPO_EXPORT_REPO, build_cfg.export_repo(t))
        set_if_not_none(s, XMAKE_REPO_IMPORT_REPOS, build_cfg.import_repos(t))
        set_if_not_none(s, XMAKE_REPO_DEPLOY_CRED_HANDLE, build_cfg.deploy_cred_key(t))
        set_if_not_none(s, XMAKE_REPO_DEPLOY_USER, build_cfg.deploy_user(t))
    map(handle_repotype,keys)

    set_if_not_none(XMAKE_SECTION_MC, XMAKE_MC_DEPENDENCIES, build_cfg.dependency_file())
    for k in build_cfg.variant_info().keys():
        config_parser.remove_section(XMAKE_SECTION_BV)
        set_if_not_none(XMAKE_SECTION_BV, k, build_cfg.variant_info()[k])

    if build_cfg._build_script_options is not None and len(build_cfg._build_script_options)!=0:
        config_parser.remove_section(XMAKE_SECTION_BPO)
        for k in build_cfg._build_script_options.keys():
            set_if_not_none(XMAKE_SECTION_BPO, k, build_cfg._build_script_options[k])

    if xmake_file is None:
        if not exists(build_cfg.genroot_dir()): makedirs(build_cfg.genroot_dir())
        xmake_file = join(build_cfg.genroot_dir(), XMAKE_FILE_NAME)
    log.info( 'writing '+xmake_file)
    build_cfg._xmake_file=xmake_file
    config_parser.write(open(xmake_file, 'w'))

########################################################################################

def acquire_custom_build_script(build_cfg):
    log.info( "using custom build script from " + build_cfg.custom_build_script_file())
    return acquire_build_script(build_cfg, build_cfg.custom_build_script_file())

def acquire_build_script(build_cfg, plugin_path):
    #dynamically load custom build script
    log.info( 'loading build plugin '+plugin_path)
    plugin_code = compile(open(plugin_path, "rt").read(), plugin_path, "exec")
    plugin_dict = {
            "__metaclass__": spi.MetaBuildPlugin,
            "__name__": "buildplugin",
            "object": spi._ObjectBase,
    }
    exec plugin_code in plugin_dict

    try:
        build_script_class = plugin_dict["build"]
    except KeyError:
        log.error( "custom build script must define a class 'build' - no such class def found at: " + plugin_path)
        raise XmakeException("failed to instantiate 'build' (no such class def found)")

    if not issubclass(build_script_class, spi.BuildPlugin):
        raise XmakeException("build class must be a subclass of spi.BuildPlugin")

    #check for existence of c'tor w/ one formal parameter
    if not len(inspect.getargspec(build_script_class.__init__)[0]) == 2:
        log.error( "custom build class must implement a c'tor w/ exactly one formal parameter (which is of type BuildConfig)")
        raise XmakeException("failed to instantiate 'build' (no c'tor def w/ correct amount of formal parameters (which is one) found)")

    build_script = build_script_class(build_cfg)

    build_cfg._build_script_file=plugin_path
    return build_script

def acquire_named_build_script(build_cfg):
    name_file = build_cfg.build_script_name_file()
    with open (name_file, 'r') as f:
        lines = f.readlines()
        lines = filter(lambda(x): not x.strip().startswith('#'), lines)
        if not len(lines) > 0: raise XmakeException('no build script name defined in file: ' + name_file)
        script_name = lines[0].strip()

    c = script_name.split(':')
    build_cfg._build_script_name = c[0]
    if len(c)>1:
        build_cfg._build_script_settings = ':'.join(c[1:])

def acquire_build_script_by_name(build_cfg, name):
    pluginPath=join(inst.get_build_plugin_dir(), name+".py")
    if not isfile(pluginPath):
        raise XmakeException('failed to found build plugin for {}'.format(name))

    restrict_build_plugin(build_cfg, name)
    return acquire_build_script(build_cfg, pluginPath)

def dummy():
    script_name=''
    allowed_script_names = {}

    log.info( 'build script is '+script_name)
    if not script_name in allowed_script_names.keys(): raise XmakeException('not an allowed script name: %(name)s - allowed script names are: %(allowed_names)s'
                                                                     % {'name' : script_name, 'allowed_names': ' '.join(allowed_script_names.keys())})

    #return allowed_script_names[script_name](build_cfg)

import buildplugins.vmake
import buildplugins.generic

valid_plugins=set(['dockerbuild','dockerrun','dockernode'])

def restrict_build_plugin(build_cfg, name=None):
    if build_cfg.productive() and not name in valid_plugins and utils.which("docker") is not None:
        """ running on a host with docker access
        In this case only the two buildin docker plugins may be used
        """
        raise XmakeException('on docker hosts only the standard docker build plugins may be used')

def determine_build_script(build_cfg):
    """
        determines (and acquires) the xmake build plugin to use.
    """
    version_file = join(build_cfg.cfg_dir(), 'VERSION')

    # Check if an instance of BuildPlugin is already set
    if build_cfg.build_script() is not None:
        restrict_build_plugin(build_cfg)
        # Version is mandatory for custom build script
        if build_cfg._base_version is None:
            raise XmakeException('VERSION file must exist at: '+ version_file)
        return build_cfg.build_script()

    # Check if there is a cfg/build.py file
    if is_existing_file(build_cfg.custom_build_script_file()):
        restrict_build_plugin(build_cfg)
        # Version is mandatory for custom build script
        if build_cfg._base_version is None:
            raise XmakeException('VERSION file must exist at: '+ version_file)
        return acquire_custom_build_script(build_cfg)

    # Check if there is build plugin file path set in build_cfg (support of -b argument)
    if build_cfg.build_script_file():
        if isfile(build_cfg.build_script_file()):
            restrict_build_plugin(build_cfg)
            if build_cfg._base_version is None:
                raise XmakeException('VERSION file must exist at: '+ version_file)
            return acquire_build_script(build_cfg, build_cfg.build_script_file())
        elif build_cfg.build_script_file() != build_cfg.custom_build_script_file():
            wantedPluginName = None if build_cfg.build_script_name() == 'vmake' else build_cfg.build_script_name()
            candidatePlugins = externalplugins.discover(build_cfg, build_cfg.build_script_file(), wantedPluginName)
            if len(candidatePlugins) > 0:
                bestCandidatePlugin = candidatePlugins[0]
                logmsg = 'selected plugin is {}'.format(bestCandidatePlugin['name'])
                log.info('*'*(len(logmsg)+4))
                log.info('* {} *'.format(logmsg))
                log.info('*'*(len(logmsg)+4))

                setupxmake = externalplugins.load_plugin(bestCandidatePlugin['externalplugin_path'])
                DicoveryPluginClass = setupxmake.get_discovery_plugin()
                ExternalPluginClass = setupxmake.get_plugin()
                build_cfg._externalplugin_dir = bestCandidatePlugin['externalplugin_path']
                build_cfg._externalplugin_setup = setupxmake
                build_cfg._build_script_version = bestCandidatePlugin['build_script_version']
                build_cfg._content_plugin = DicoveryPluginClass(build_cfg)
                build_cfg._content_plugin.setup()

                externalPluginInstance = ExternalPluginClass(build_cfg)

                # Declare tools needed by the selected external plugin
                if hasattr(externalPluginInstance, 'need_tools'):
                    declared_tools = externalPluginInstance.need_tools()
                    if declared_tools:
                        externalplugins.declare_tools(build_cfg, declared_tools)

                return externalPluginInstance

    # Find build plugin with discovery/content plugins
    # Otherwise use the generic plugin
    if build_cfg.build_script_name() is not None:

        candidatePlugins = []
        wantedPluginName = None if build_cfg.build_script_name() == 'vmake' else build_cfg.build_script_name()
        # check built-in plugins
        candidatePlugins.extend(builtinplugins.discover(build_cfg, wantedPluginName))

        # check external plugins
        if len(candidatePlugins) == 0:
            candidatePlugins.extend(externalplugins.discover(build_cfg, build_cfg.externalplugins_dir(), wantedPluginName))
        elif len(candidatePlugins) > 0 and not wantedPluginName:
            candidatePlugins.extend(externalplugins.discover(build_cfg, build_cfg.externalplugins_dir(), wantedPluginName))

        candidatePlugins = _filter_candidate_plugins(candidatePlugins)

        if len(candidatePlugins) > 0:
            bestCandidatePlugin = candidatePlugins[0]
            if len(candidatePlugins) > 1:
                log.warning('found several candidate plugins {}'.format(', '.join(c['name'] for c in candidatePlugins)))
                log.warning('arbitrarily selecting the first one {}'.format(bestCandidatePlugin['name']))
            else:
                logmsg = 'selected plugin is {}'.format(bestCandidatePlugin['name'])
                log.info('*'*(len(logmsg)+4))
                log.info('* {} *'.format(logmsg))
                log.info('*'*(len(logmsg)+4))

            try: # is it an external plugin?
                setupxmake = externalplugins.load_plugin(bestCandidatePlugin['externalplugin_path'])
                DicoveryPluginClass = setupxmake.get_discovery_plugin()
                ExternalPluginClass = setupxmake.get_plugin()
                build_cfg._externalplugin_setup = setupxmake
                build_cfg._build_script_version = bestCandidatePlugin['build_script_version']
                build_cfg._content_plugin = DicoveryPluginClass(build_cfg)
                build_cfg._content_plugin.setup()

                externalPluginInstance = ExternalPluginClass(build_cfg)

                # Declare tools needed by the selected external plugin
                if hasattr(externalPluginInstance, 'need_tools'):
                    declared_tools = externalPluginInstance.need_tools()
                    if declared_tools:
                        externalplugins.declare_tools(build_cfg, declared_tools)

                return externalPluginInstance
            except KeyError:
                try: # is it a plugin with content plugin?
                    build_cfg._content_plugin = bestCandidatePlugin['content_plugin']
                    build_cfg._content_plugin.setup()
                except KeyError: # then it is builtin plugin without content_plugin
                    pass # few lines below, the acquire_build_script_by_name method will do the job
        else:
            log.info('no candidate plugins found. Use generic plugin by default')
            return buildplugins.generic.build(build_cfg)

        if build_cfg.build_script_name() != "maven" and build_cfg._base_version is None:
            raise XmakeException('VERSION file must exist at: '+ version_file)

    if build_cfg.build_script_name() is not None:
        if build_cfg._base_version is None:
            raise XmakeException('VERSION file must exist at: '+ version_file)
        return acquire_build_script_by_name(build_cfg, build_cfg.build_script_name())

    # Otherwise use vmake as default
    restrict_build_plugin(build_cfg)
    if build_cfg._base_version is None:
        raise XmakeException('VERSION file must exist at: '+ version_file)
    log.info( 'using vmake as default build plugin')
    return buildplugins.vmake.build(build_cfg)

def _filter_candidate_plugins(plugins):
    if (len(plugins)>1):
        log.debug('well, {} plugins are compatibles with source'.format(len(plugins)))
        candidatePlugins = []
        for plugin in plugins:
            pluginsToRemove = []
            try:
                pluginsToRemove = plugin['has_priority_over_plugins']
            except KeyError:
                pass

            candidate = []
            candidate.append(plugin)
            candidate.append([p['name'] for p in plugins if (p['name']!=plugin['name'] and p['name'] not in pluginsToRemove)])
            candidatePlugins.append(candidate)

        sorted(candidatePlugins, key=lambda candidate: len(candidate[1])) # sort by number of opponent plugins
        for candidate in candidatePlugins:
            log.debug('\t{} plugin has {} opponent{}: {}'.format(candidate[0]['name'], len(candidate[1]), ('s' if len(candidate[1])>1 else ''), ', '.join(candidate[1])))

        bestCandidatePlugins = [candidate for candidate in candidatePlugins if len(candidate[1])==0]
        if len(bestCandidatePlugins)>0:
            return [p[0] for p in bestCandidatePlugins]

        return [p[0] for p in candidatePlugins]
    return plugins

def determine_tools(build_cfg):
    ''' setup a tool object that relates to a dedicated build configuration.
        This means that the build runtime is taken according to the runtime method of the build config object.
        It also provides to the imported tools dir provided by the build configuration.
    '''
    tools=Tools()
    # route dedicated methods to be used from the build configuration
    tools.import_tools_dir=build_cfg.import_tools_dir
    tools.runtime=build_cfg.runtime
    return tools

def determine_whether_plugin_is_variant_aware(build_cfg):
    build_script = build_cfg.build_script()
    #build plugin is explicitly not variant-aware iff it defines a method 'variant_cosy' that returns None
    acquire_custom_variant_data(build_script, build_cfg)

################################################################################

def setup_config(build_cfg, preliminary=False):
    parser = options.cli_parser()
    variant_info = dict()
    #print 'INFO: running '+dirname(dirname(realpath(__file__)))

    def gather_variants(option, opt_str, value, parser):
        if (opt_str=="-V"):
            try:
                i=value.index('=')
                c=value[:i]
                value=value[i+1:]
            except ValueError:
                raise OptionValueError('coordinate assignment expected instead of "'+value+'"')
        else:
            c=opt_str[10:]
        if (not preliminary): log.info( "variant info "+str(c)+": "+str(value))
        variant_info[c]=value

    parser.add_option('-V', action='callback', callback=gather_variants, type='string', help="variant coordinate in form of an assignment")
    for e in filter(lambda(x): x.startswith('--variant-'),sys.argv):
        parser.add_option(e, action='callback', callback=gather_variants, type='string')

    (args, buildtool_args) = parser.parse_args()
    if args.buildruntime is not None:
        build_cfg._runtime=args.buildruntime
    config = IterableAwareCfgParser()
    if args.show_version:
        inst.show_version_info()
    else:
        if not preliminary and args.do_purge_all:
            victim_cfg = BuildConfig()  #old cfg will be purged
            parse_xmake_file(args, config, victim_cfg)
            apply_cmdline_args(args, buildtool_args, variant_info, victim_cfg)
            gendir = victim_cfg.genroot_dir()
            importdir = victim_cfg.import_root_dir()
            externalpluginsdir = victim_cfg.externalplugins_dir()
            log.info( "option --purge-all was set: purging any remains of previous builds,imports or configurations (in genroot_dir:" +
                       gendir + ", import_dir: " + importdir + ", externalplugins_dir: " + externalpluginsdir + " )")
            if exists(gendir):
                logfile=join(victim_cfg.genroot_dir(),"boot.log")
                content=None
                if exists(logfile):
                    log.info("saving boot.log")
                    with open(logfile,"r") as f:
                        content=f.read()
                OS_Utils.rm_dir(gendir)
                if content!=None:
                    makedirs(victim_cfg.genroot_dir())
                    with open(logfile,"w") as f:
                        f.write(content)
            if exists(importdir):
                OS_Utils.rm_dir(importdir)
            if exists(importdir):
                OS_Utils.rm_dir(importdir)
            if exists(externalpluginsdir):
                OS_Utils.rm_dir(externalpluginsdir)
            victim_cfg = None   #old cfg must not be used any more

    #process existing config and cmd line args

    load_xmake_file(join(inst.get_xmake_user_home(),XMAKE_FILE_NAME),config,build_cfg)
    xmake_file = parse_xmake_file(args, config, build_cfg)
    apply_cmdline_args(args, buildtool_args, variant_info, build_cfg)
    build_cfg._component_dir=abspath(build_cfg.component_dir())
    return (args,config,xmake_file)

###########################################################################

def create_gendir(build_cfg):
    if not exists(build_cfg.gen_dir()):
        makedirs(build_cfg.gen_dir())
    if not exists(build_cfg.temp_dir()):
        makedirs(build_cfg.temp_dir())
    os.environ['TEMP']=os.environ['TMP']=os.environ['TMPDIR']=build_cfg.temp_dir()

def execute_prelude(build_cfg):
    log.info('-'*50)
    log.info('| {0:46} |'.format('read basic configuration'))
    log.info('-'*50)
    (args,config,xmake_file)=setup_config(build_cfg)
    log.setConsoleLevel(logging.DEBUG if build_cfg.is_tool_debug() else logging.INFO)
    log.info('gendir is '+build_cfg.genroot_dir())
    create_gendir(build_cfg)
    log.start_logfile(join(build_cfg.genroot_dir(),"build.log"))
    if args.show_version: sys.exit(0)


    if build_cfg.scm_snapshot_url() is None and build_cfg.productive():
        log.warning('build is running in productive mode but no build metadata is available (--scm-snapshot-url)')
        if build_cfg.do_export():
            log.error('export of contents is prohibited in productive builds that are run without all required metadata options (--scm-snapshot-url)')
            raise XmakeException('missing metadata arguments for productive build')

    #replace project root with absolute directory for the build execution
    if build_cfg._genroot_dir is not None: build_cfg._genroot_dir=abspath(build_cfg._genroot_dir)

    script_file=setup_build_cfg(build_cfg)
    build_cfg._tools = determine_tools(build_cfg)
    setup_tool_cfg(build_cfg)

    log.info('try to determine project version from configuration...')
    version_found = _determine_version_from_config(build_cfg, args.version)
    if version_found:
        setup_plugin_dependencies(build_cfg,script_file)
        log.info('found version {}'.format(build_cfg._version))
    else:
        log.info('no version found')

    if is_existing_file(build_cfg.build_script_name_file()):
        acquire_named_build_script(build_cfg)

    log.info('-'*50)
    log.info('| {0:46} |'.format('xmake plugin management'))
    log.info('-'*50)

    # list present builtin plugins
    builtinplugins.list(inst.get_build_plugin_dir())

    # download and install external plugins
    if build_cfg.build_script_file() != build_cfg.custom_build_script_file() and not isfile(build_cfg.build_script_file()):
        log.info('external plugins not downloaded. The directory was set manually with -b argument {}'.format(build_cfg.build_script_file()))
    else:
        specificPluginName = build_cfg._build_script_name if build_cfg._build_script_name != 'vmake' else None
        specificPluginVersion = build_cfg._build_script_version
        
        externalplugins.install(build_cfg.externalplugins_nexus_url(), build_cfg.externalplugins_dir(),
                                specificPluginName = specificPluginName,
                                specificPluginVersion = specificPluginVersion,
                                fromReleasesRepository = build_cfg.is_release() or build_cfg.is_milestone())

    build_script = determine_build_script(build_cfg)
    if not version_found:
        log.info('last try to determine project version...')
        if not _determine_version_from_config(build_cfg, args.version):
            raise XmakeException('VERSION file must exist at: '+ join(build_cfg.cfg_dir(), 'VERSION'))
        else:
            log.info('found version {}'.format(build_cfg._version))
    prepare_multi_component_dependencies(args,build_cfg)

    #persist effective build cfg for subsequent builds
    write_xmake_file(config, build_cfg, None)
    #load custom build script if such a script is present
    if build_cfg.build_script_settings() is not None:
        log.info( 'configuring build plugin: '+build_cfg.build_script_settings())
        build_script.set_option_string(build_cfg.build_script_settings())
    if build_cfg.build_script_options() is not None:
        log.info( 'configuring build plugin options: '+str(build_cfg.build_script_options()))
        for (o,v) in build_cfg.build_script_options().items():
            build_script.set_option(o,v)
    build_cfg._build_script = build_script

    #determine whether or not build plugin supports variant handling
    determine_whether_plugin_is_variant_aware(build_cfg)
    if not OS_Utils.is_UNIX():
        for key, value in os.environ.iteritems():
            visualStudioRE = re.search(r"^VS(\d{3})COMNTOOLS$", key)
            if not visualStudioRE or not is_existing_directory(value): continue
            setattr(build_cfg, "xmake_msvc%s_dir"%visualStudioRE.group(1), os.path.abspath(os.path.join(value, '..', '..')))
    print_effective_cfg(build_cfg)
    validate_project_root_dir(build_cfg)

def print_effective_cfg(build_cfg):
    log.info('-'*50)
    log.info('| {0:46} |'.format('effective build configuration'))
    log.info('-'*50)
    log.info('found repository types for import: '+str(build_cfg._import_repos.keys()))
    log.info('found repository types for export: '+str(build_cfg._export_repos.keys()))
    print_attribs = ['component_dir', 'src_dir', 'genroot_dir', 'do_import', 'do_export', 'productive', 'suppress_variant_handling',
                     'variant_info', 'variant_cosy_gav', 'variant_cosy', 'variant_coords',
                     'scm_snapshot_url', 'version', 'version_suffix', 'import_repos', 'export_repo']

    log.info('build is running on host: ' + platform.node())
    log.info('build runtime: ' + build_cfg.runtime())
    for attr in print_attribs:
        log.info('{0:25}: {1:30}'.format(attr, str(getattr(build_cfg,attr)())))

def validate_project_root_dir(build_cfg):
    #todo: enhance this check, e.g. also take build arguments into account
    if build_cfg.content_plugin() is None or build_cfg.content_plugin().validate_project():
        if not is_existing_file(join(build_cfg.component_dir(),".xmake.cfg")):
            if not is_existing_directory(build_cfg.cfg_dir()):
                log.error( "no 'cfg' directory found below project root: " + build_cfg.component_dir()+"\n"+
                       '     hint: did you specify an erroneous project root (-r option) or are the sources not synced properly?')
                raise XmakeException('invalid project root contents (missing cfg directory)')
            if not is_existing_directory(build_cfg.src_dir()):
                log.warning("no 'src' directory found below project root: " + build_cfg.component_dir())

    if build_cfg.do_import() and not reduce(lambda x,y:x and y, map(is_existing_file, build_cfg.import_scripts())):
        log.warning('importing is enabled, but not all of the following import scripts were found to be present: {}'.format(', '.join(build_cfg.import_scripts())))
    if build_cfg.do_export() and not is_existing_file(build_cfg.export_script()):
        log.warning("exporting is enabled, but no export script is present at: " + build_cfg.export_script())

#
# multi component build configuration
#

def parse_dependency_file(dependency_file, config_parser):
    if dependency_file is None or not is_existing_file(dependency_file): return dict()

    config_parser.read(dependency_file)

    results=dict();

    def transfer_sect(section):
        props=dict()
        results[section]=props

        def transfer_prop(prop):
            props[prop[0]] = prop[1]

        map(transfer_prop, config_parser.items(section))

    log.info( 'found multi component dependencies for '+str(config_parser.sections()))
    map(transfer_sect,config_parser.sections())
    return results

def determine_dependency_input_file(args, build_cfg):
    if args.dependency_file is None:
        dependency_file = build_cfg.dependency_file()
        if dependency_file is not None and is_existing_file(dependency_file):
            return dependency_file
        dependency_file = build_cfg.dependency_save_file()
        if dependency_file is not None and is_existing_file(dependency_file):
            return dependency_file
    else:
        if not is_existing_file(args.dependency_file):
            log.error('multi component dependency file '+args.dependency_file+' not found')
            raise XmakeException('dependency file '+args.dependency_file+' not found')

    return args.dependency_file

def save_dependencies(dependency_file, build_cfg):
    if dependency_file is None or not is_existing_file(dependency_file): return
    if dependency_file == build_cfg.dependency_save_file(): return
    log.info( 'saving multi component dependencies from '+dependency_file)
    copyfile(dependency_file,build_cfg.dependency_save_file())

def prepare_multi_component_dependencies(args,build_cfg):
    dependency_file = determine_dependency_input_file(args, build_cfg)
    if dependency_file is None: return

    config = IterableAwareCfgParser()
    build_cfg._dependency_config=parse_dependency_file(dependency_file, config)
    if args.dependency_file is not None:
        build_cfg._dependency_file=abspath(args.dependency_file)
    save_dependencies(dependency_file, build_cfg)

def tool_label(name,tid):
    if name==tid: return tid
    return tid+"["+name+"]"

def setup_tool_cfg(build_cfg):
    cfg=join(build_cfg.cfg_dir(),'tools.cfg')
    if is_existing_file(cfg):
        log.info('found tools.cfg...');
    else:
        cfg=join(build_cfg.component_dir(),'.tools.cfg')
        if is_existing_file(cfg):
            log.info('found .tools.cfg...');

    if is_existing_file(cfg):
        config = IterableAwareCfgParser()
        config.read(cfg)

        for s in config.sections():
            name=s
            tid=s
            tags=[]
            if config.has_option(name,'tags'):
                tags.extend(config.get(name,'tags'))
            if config.has_option(name,'toolid'):
                tid=config.get(name,'toolid')
            log.info("\trequested tool "+tool_label(name,tid))

            def gv(a,req=True):
                if config.has_option(name, a+'.'+build_cfg.runtime()):
                    return config.get(name,a+'.'+build_cfg.runtime())
                if config.has_option(name, a):
                    return config.get(name,a)
                if req==True:
                    raise XmakeException(a+' required for tool '+tool_label(name,tid))
                return None

            if config.has_option(name,'runtime'):
                o=config.get(name,'runtime')
                vmodes=[ x.strip() for x in o.split(',')]

                if len(vmodes)!=1 or vmodes[0]!='generic':
                    for o in vmodes:
                        if o!='group' and o!='classifier':
                            raise XmakeException('invalid mode "'+o+'" for runtime attribute of tool '+tool_label(name,tid))
            else:
                vmodes=['generic']

            path=gv('path',False)
            archive=gv('archive',False)
            if archive is None: archive=True
            else: archive= archive.lower() == "true"
            runtimes=None
            if config.has_option(name,'runtimes'):
                o=config.get(name,'runtimes')
                if not isinstance(o,list):
                    o=[ x.strip() for x in str(o).split(',') ]
                runtimes=o
            if runtimes is not None:
                log.info('\truntimes('+name+'): '+str(runtimes))
            if runtimes==None or contains(runtimes,build_cfg.runtime())>=0:
                vers=gv('version')
                if not build_cfg.tools().is_declared_tool(tid):
                    ga=build_cfg.runtime_gid(gv('groupId'),vmodes.count('group')>0)+':'+gv('artifactId')+':'
                    suffix=gv('type',False)
                    ga=ga+(suffix if suffix is not None else 'zip')
                    c=build_cfg.runtime_classifier(gv('classifier',False),vmodes.count('classifier')>0)
                    if c != None:
                        ga=ga+':'+c
                    log.info( 'declare custom tool '+tid+': '+ga)
                    build_cfg.tools().declare_tool(tid,ga,path,archive)
                build_cfg._configured_tools[name]=ConfiguredTool(name,vers,tags,tid)
                build_cfg.tools()[tid]._tags.extend(tags)
                if len(tags)>0:
                    log.info('\ttags for '+tool_label(name,tid)+" are "+str(tags))

def setup_build_cfg(build_cfg):
    script_file=None
    path=join(build_cfg.build_script_ext_dir(),'python')
    if is_existing_directory(path):
        log.info("appending python path: "+path)
        sys.path.append(path)

    config=build_cfg.xmake_cfg()
    if config is not None:
        s="dependencies"
        if (config.has_section(s)):
            for d in config.items(s):
                log.info("\tfound build plugin dependency "+d[0]+": "+d[1])
                if is_gav(d[1]):
                    gav=tool_gav(d[1],True)
                    if build_cfg.productive():
                        if gav[4].endswith("-SNAPSHOT"):
                            raise XmakeException('snapshot build plugin dependencies possible only for local developer builds: '+d[1])
                    build_cfg._configured_plugindeps[d[0]]=PythonDependency(d[0],gav)
                else:
                    if build_cfg.productive():
                        raise XmakeException('path like dependencies possible only for local developer builds: '+d[1])
                    build_cfg._configured_plugindeps[d[0]]=PythonDependency(d[0],d[1])

        s='buildplugin'
        if (config.has_section(s)):
            if config.has_option(s, "plugin") and config.has_option(s, "name"):
                raise XmakeException('both, plugin and name configured in build.cfg')

            for (o,v) in config.items(s):
                if o=="plugin":
                    script_file=validate_path(v)
                    t=join(build_cfg.cfg_dir(),script_file)
                    if not is_existing_file(t):
                        t=join(build_cfg.build_script_ext_dir(),'script',script_file)
                    if is_existing_file(t):
                        build_cfg._build_script_file=t
                        script_file=None
                    continue
                if o=="name":
                    build_cfg._build_script_name=v
                    continue
                if o=="plugin-version":
                    build_cfg._build_script_version=v
                    continue
                if o=="settings":
                    build_cfg._build_script_settings=v
                    continue
                if o=="alternate-path":
                    build_cfg._alternate_path=v
                    continue
                if o=="externalplugins-nexus-url":
                    build_cfg._externalplugins_nexus_url=v
                    continue
                build_cfg.add_build_script_option(o,v)

        env = dict();
        for platform in ['all','windows','unix'] + [s[4:] for s in config.sections() if s.startswith('env_') and s!='env_all' and s!='env_windows' and s!='env_unix']:
            env_platform = 'env_' + platform
            if not (env_platform in config.sections() and (platform == 'all' or platform==build_cfg.family() or platform==build_cfg.runtime())): continue
            for key in config.options(env_platform):
                env[key] = config.get(env_platform, key)
        if env:
            os.environ["XMAKE_ENV_FILE"] = filename = join(build_cfg.temp_dir(),'environment.cfg');
            with open(filename, 'w') as f:
                for key,value in env.items():
                    f.write("%s=%s\n" % (key,value))

    return script_file

def setup_plugin_dependencies(build_cfg, script_file=None):
    deps=build_cfg.configured_plugin_deps()
    if len(deps)>0:
        log.info('configuring python dependencies...')
        gavs=set()
        allgavs=set()
        for (n,d) in deps.items():
            if d.gav() is not None: allgavs.add(d.gavstr())
            if not d.has(build_cfg):
                if not is_existing_file(d.installation_archive(build_cfg)):
                    gavs.add(d.gavstr())
        append_import_file(build_cfg,allgavs)
        if len(gavs)>0:
            log.info('\tfound GAVs for import: '+str([x for x in gavs]))
            import_file=create_import_script(build_cfg, 'python-imports.ais', {'default':gavs})
            ai_args=prepare_ai_command(build_cfg, {'default':build_cfg.import_python_dir()},
                                       build_cfg.import_repos(), '.build')
            assert_import_file(build_cfg)
            execute_ai(build_cfg, ai_args, import_file, "python dependencies ")
            update_import_file(build_cfg,'.build')
        else:
            log.info("\tall dependencies already installed or imported -> no python dependency import required")

        for (n,d) in deps.items():
            p=d.get(build_cfg)
            log.info('\tadding '+p+' to python path')
            if script_file is not None:
                t=join(p,script_file)
                if is_existing_file(t):
                    build_cfg._build_script_file=t
                    script_file=None
            sys.path.append(p)
        if script_file is not None:
            raise XmakeException('build script '+script_file+' not found')
    else:
        log.info('no python dependencies found')
