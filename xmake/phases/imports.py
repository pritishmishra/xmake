'''
implementation of the xmake 'PRELUDE' phase. This phase is by definitionem the
first phase to be executed. It deals w/ command-line parsing and preprocessing

Created on 23.07.2014

@author: Christian Cwienk (d051236)
'''

import log

from utils import is_existing_file, mkdirs
from xmake_exceptions import XmakeException
from os.path import join
from string import Template

import inst
import spi
import externalplugins
import xml.etree.ElementTree as ET

from commonrepo import create_import_script, prepare_ai_command, execute_ai, assert_import_file, update_import_file
from commonrepo import append_import_file
from config import PythonDependency

def execute_imports(build_cfg):
    '''performs the xmake IMPORT phase (imports are defined in <cfgdir>/import.ais and resolved using the Artifact Importer)'''
    mkdirs(build_cfg.import_dir())

    if not build_cfg.do_import():
        log.info( "importing was skipped, because the according option '-i' was not set\n")
        return
    absent_import_scripts = filter(lambda(x): not is_existing_file(x), build_cfg.import_scripts())
    import_scripts = filter(lambda(x): is_existing_file(x), build_cfg.import_scripts())
    if len(import_scripts) == 0:
        log.info( 'no standard import')
    else:
        log.info( 'standard import scripts: '+str(import_scripts))
    #add explicit import targets from build plugin
    tool_import_script=_create_tool_import_script(build_cfg)
    if tool_import_script is not None:
        log.info( 'adding tool import script '+tool_import_script)
        import_scripts.insert(0, tool_import_script)
    if not len(absent_import_scripts) == 0:
        log.warning('importing was switched on, but the following import mapping scripts were not found:')
        log.warning(', '.join(build_cfg.import_scripts()))
        if len(import_scripts) == 0: return
    #run artifact importer
    log.info( "performing import...")
    log.info( 'import scripts: '+str(import_scripts))

    ai_args=prepare_ai_command(build_cfg, {'default':build_cfg.import_dir(),
                                           'tools':build_cfg.import_tools_dir()},
                               build_cfg.import_repos(), '.tmp')

    if not build_cfg.suppress_variant_handling():
        def add_variant_coord(k):
            ai_args.extend(['-Dbuild'+k.capitalize()+'=' + vcoords[k]]) # why different from export script variables???
            ai_args.extend(['-Dbuild'+k+'=' + vcoords[k]])

        vcoords=build_cfg.variant_coords()
        if vcoords!=None and len(vcoords)!=0:
            map(add_variant_coord,vcoords.keys())
        else:
            log.error("using variant coordinate system ("+build_cfg.variant_cosy_gav()+") requires coordinates/variant options")
            raise XmakeException("using variant coordinate system ("+build_cfg.variant_cosy_gav()+") requires coordinates/variant options")

    #add custom import config if present
    bs = build_cfg.build_script()
    for (name, value) in bs.import_roots().items():
        ai_args.extend(['-C', 'root.' + name + '=' + value])
    for (name, value) in bs.import_variables().items():
        ai_args.extend(['-D', name + '=' + value ])

    assert_import_file(build_cfg)
    for script in import_scripts:
        execute_ai(build_cfg, ai_args, script, "")
        update_import_file(build_cfg,'.tmp')

    _setup_global_settings_xml(build_cfg)

def _tool_installation_info(m,s):
    if not m:
        if s is None or len(s)==0:
            return "no on-the-fly tool download required"
        else:
            return "already installed"
    return str(s)

def _handleToolImports(build_cfg, tid, v, gavs, allgavs):
    tools=build_cfg.tools();
    s=tools[tid].imports(v)
    m=False
    if s is not None:
        allgavs.update(s)
        for gav in s:
            if not tools.hasToolGAV(gav):
                gavs.add(gav)
                build_cfg.add_tool_to_be_installed(tid,gav)
                m=True
    log.info( '\ttool '+tid+'('+v+'): '+_tool_installation_info(m,s))

def _gather_tool_imports(build_cfg, build_script):
    gavs=set()
    allgavs=set()
    v = None
    if build_cfg.externalplugin_setup():
        if hasattr(build_script, 'need_tools'):
            declared_tools = build_script.need_tools()
            if declared_tools:
                v = {}
                for tool in declared_tools:
                    v[tool['toolid']]=tool['version']
    else:
        v = build_script.required_tool_versions()
    if v != None:
        for k in v.keys():
            if isinstance(k,spi.Tool):
                v[k.toolid()]=v[k]
                del v[k]
        log.info( 'required tool versions for build plugin: '+str(v))
        def gather_gavs(tid):
            _handleToolImports(build_cfg,tid,v[tid],gavs,allgavs)
        map(gather_gavs,v.keys())
    else:
        log.info( 'build plugin does not request tools')
    return (gavs,allgavs)

def _create_tool_import_script(build_cfg):
    build_script = build_cfg.build_script()
    (tool_imports,allgavs)=_gather_tool_imports(build_cfg, build_script)
    if (not build_cfg.suppress_variant_handling() and build_cfg.variant_cosy_gav()!=None):
        tool_imports.add(build_cfg.variant_cosy_gav())
    if len(tool_imports) > 0:
        imports={'tools': tool_imports}
    else:
        imports={}

    imps=build_script.plugin_imports()
    if imps is not None:
        if not isinstance(imps, dict):
            raise XmakeException('plugin_imports must return a dict')
        log.info( 'build plugin requests imports: '+str(imps))
        if imps.has_key('tools') and len(imports) > 0:
            imports['tools'].update(imps['tools']);
            del imps['tools']
        if len(imps)>0: imports.update(imps)

    ct=build_cfg.configured_tools()
    if len(ct)!=0:
        log.info( 'found configured tools...')
        gavs=set()
        for n in ct.keys():
            tid=ct[n].toolid()
            _handleToolImports(build_cfg,tid,ct[n].version(),gavs,allgavs)
        if len(gavs) > 0:
            if imports.has_key('tools'):
                imports['tools'].update(gavs);
            else:
                imports['tools']=gavs

    log.info('all tool imports: '+str(allgavs))
    append_import_file(build_cfg,allgavs)
    if len(imports)==0:
        log.info( 'no tool import script required')
        return None

    #dict keys must denote existing (defined) import roots
    import_keys = ['default', 'tools'] # default and tools is provided by IMPORT phase (xmake)
    import_keys.extend(build_script.import_roots().keys())
    undefined_import_roots=filter(lambda(key):key not in import_keys, imports.keys())
    if len(undefined_import_roots)>0: raise XmakeException('the following import roots were not defined by build plugin: %s' % ', '.join(undefined_import_roots))
    import_file=create_import_script(build_cfg, 'plugin-imports.ais', imports)

    return import_file


def _setup_global_settings_xml(build_cfg):
    '''
        Build a custom settings.xml file from a template located in [install_dir]/xmake/template/maven/global_settings.xml
        Override the the default mirroring for global maven settings (use case: run maven outside xmake )
        This new file is saved into M2_HOME/conf/settings.xml
    '''

    # Add xml namespaces
    ET.register_namespace('', 'http://maven.apache.org/SETTINGS/1.0.0')
    ET.register_namespace('xsi', "http://www.w3.org/2001/XMLSchema-instance")
    ET.register_namespace('xsi:schemaLocation', 'http://maven.apache.org/SETTINGS/1.0.0 http://maven.apache.org/xsd/settings-1.0.0.xsd')

    # Parse template/settings.xml
    templateSettingsXmlFile = join(inst.get_installation_dir(), 'xmake', 'template', 'maven', 'global_settings.xml')
    xmlSettingsContent = ''
    with open(templateSettingsXmlFile, 'r') as f:
        xmlSettingsContent = f.read()

    tree = ET.fromstring(xmlSettingsContent)
    if tree is None:
        raise XmakeException( 'cannot generate specific settings.xml for maven')

    #Search fileds to update
    namespace = "{http://maven.apache.org/SETTINGS/1.0.0}"
    mirrorsUrl = tree.find('./{0}mirrors'.format(namespace))
    repos = tree.find('./{0}profiles/{0}profile[{0}id="customized.repo"]/{0}repositories'.format(namespace))
    pluginrepositoryListUrl = tree.find('./{0}profiles/{0}profile[{0}id="customized.repo"]/{0}pluginRepositories'.format(namespace))

    if mirrorsUrl is None or repos is None or pluginrepositoryListUrl is None:
        raise XmakeException('cannot generate specific settings.xml for maven')

    # Add specific fields
    if build_cfg.is_release() is None:
        i = 1
        for repo in build_cfg.import_repos():
            pluginrepository = ET.SubElement(pluginrepositoryListUrl, 'pluginRepository')
            ET.SubElement(pluginrepository, 'id').text = 'repo%d' % i \
                if i < len(build_cfg.import_repos()) else "central"
            ET.SubElement(pluginrepository, 'url').text = repo
            snapshots = ET.SubElement(pluginrepository, 'snapshots')
            ET.SubElement(snapshots, 'enabled').text = 'true'
            i += 1

    i = 1
    for import_repo in build_cfg.import_repos():
        additional_mirror = ET.SubElement(mirrorsUrl, 'mirror')
        ET.SubElement(additional_mirror, 'id').text = 'mirror%d' % i
        ET.SubElement(additional_mirror, 'url').text = import_repo
        ET.SubElement(additional_mirror, 'mirrorOf').text = 'repo%d' % i \
            if i < len(build_cfg.import_repos()) else "central"
        i += 1

    i = 1
    for repo in build_cfg.import_repos():
        additional_repo = ET.SubElement(repos, 'repository')
        ET.SubElement(additional_repo, 'id').text = 'repo%d' % i \
            if i < len(build_cfg.import_repos()) else "central"
        ET.SubElement(additional_repo, 'url').text = repo
        i += 1

    for tid in build_cfg.tools_to_be_installed():
        for gav_str in build_cfg.tools_to_be_installed()[tid]:
            gav=build_cfg.tools().mapToolGAVStr(gav_str)
            if 'org.apache.maven'==gav[0] and 'apache-maven'==gav[1] and build_cfg.tools()[tid] and build_cfg.tools()[tid][gav[-1]]:
                _maven_global_settings_xml_file = join(build_cfg.tools()[tid][gav[-1]], 'conf', 'settings.xml')
                log.info('write maven global settings in {} for "{}" {}'.format(_maven_global_settings_xml_file, tid, gav_str))
                with open(_maven_global_settings_xml_file,'w') as f:
                    f.write(ET.tostring(tree))
