import new
import sys
import imp
import os
import urllib
import shutil
import contextlib
import tempfile
import re
import tarfile
import log
import xml.etree.ElementTree as ET
from xmake_exceptions import XmakeException

NEXUS_RELEASES_REPOSITORY  = 'build.milestones'
NEXUS_SNAPSHOTS_REPOSITORY = 'build.snapshots.xmake'

def install(nexusUrl, destDirectory, specificPluginName = None, specificPluginVersion = None, fromReleasesRepository = False):
    nexusRepo = NEXUS_RELEASES_REPOSITORY if fromReleasesRepository else NEXUS_SNAPSHOTS_REPOSITORY
    log.info('install external plugins from nexus repository {} on server {}'.format(nexusRepo, nexusUrl))
    if os.path.isdir(destDirectory):
        log.debug('\tremove existing external plugins in {}'.format(destDirectory))
        shutil.rmtree(destDirectory)
    countInstalledPlugin = 0
    externalPlugins = _list_plugins_from_nexus(nexusUrl, nexusRepo)
    if specificPluginName:
        log.info('\t{} version: {} is required from configuration file'.format(specificPluginName, specificPluginVersion if specificPluginVersion is not None else 'LATEST'))
    for externalPlugin in externalPlugins:
        if specificPluginName:
            if specificPluginName == externalPlugin:
                countInstalledPlugin += 1
                _download_plugin_from_nexus(nexusUrl, externalPlugin, pluginVersion=specificPluginVersion, nexusRepo=nexusRepo, destDirectory=destDirectory)
                break
        else:
            countInstalledPlugin += 1
            _download_plugin_from_nexus(nexusUrl, externalPlugin, pluginVersion=None, nexusRepo=nexusRepo, destDirectory=destDirectory)
    if len(externalPlugins)==0:
        log.warning('\tno external plugins available in nexus repository')
    else:
        log.info('\t{} plugin{} installed in directory {}'.format(countInstalledPlugin, 's' if countInstalledPlugin > 1 else '', destDirectory))

def discover(build_cfg, destDirectory, wantedPluginName=None):
    def returnDiscoveryPlugin(setupxmake):
        pluginName = setupxmake.get_name()
        DicoveryPluginClass = setupxmake.get_discovery_plugin()
        discoveryPlugin = DicoveryPluginClass(build_cfg)
        opponentPlugins = None
        try:
            opponentPlugins = discoveryPlugin.has_priority_over_plugins()
        except AttributeError:
            pass
        if opponentPlugins and len(opponentPlugins)>0:
            log.info('\t{} is compatible and declares that it has priority over plugin{}: {}'.format(pluginName, ('s' if len(opponentPlugins)>1 else ''), ', '.join(opponentPlugins)))
        else:
            log.info('\t{} is compatible'.format(pluginName))
        return discoveryPlugin

    def checkPlugin(setupxmake, root):
        try:
            if wantedPluginName:
                if setupxmake.get_name().lower() == wantedPluginName.lower():
                    return returnDiscoveryPlugin(setupxmake)
                return None

            DicoveryPluginClass = setupxmake.get_discovery_plugin()
            discoveryPlugin = DicoveryPluginClass(build_cfg)
            if discoveryPlugin.matches():
                return returnDiscoveryPlugin(setupxmake)
        except AttributeError as e:
            log.exception(e)
            log.error('\texternal plugin is incorrect. Module setupxmake should have these methods get_name() and get_discovery_plugin()')
        except:
            log.exception(sys.exc_info())
            log.error('\texternal plugin is incorrect. Please check the external plugin implementation.')

        return None

    log.info('looking for an external plugin compatible with source ...')
    if wantedPluginName:
        log.info('\tplugin set in configuration file: {}'.format(wantedPluginName))
    pluginsFound = _walk_plugin(destDirectory, checkPlugin)

    if len(pluginsFound) == 0:
        log.info('\tno compatible external plugin found')

    return pluginsFound

def declare_tools(build_cfg, declared_tools):
    log.info('tools needed by the external plugin:')
    if not declared_tools or len(declared_tools)==0:
        log.info('\texternal plugin do not need tools')
        return

    tool_names = []
    for tool in declared_tools:
        name = tool['toolid']
        tid = None
        path = tool['custom_installation'] if tool.has_key('custom_installation') else None
        if tool.has_key('classifier'):
            tid = '{}:{}:{}'.format(name, tool['type'], tool['classifier'])
        else:
            tid = '{}:{}'.format(name, tool['type'])
        log.info('\t{}'.format(name+':'+tool['version']))
        tool_names.append(name+':'+tool['version'])
        
        archive=True
        if tool.has_key('archive'):
            archive=tool['archive']
        build_cfg.tools().declare_tool(name, tid, path=path, archive=archive)

def load_plugin(root_path):
    log.debug('\tadd to sys path {}'.format(root_path))
    sys.path.append(root_path)
    return imp.load_source('setupxmake', os.path.join(root_path, 'setupxmake.py'))

def _unload_plugin(root_path):
    module_names_to_remove = []
    for module_name in sys.modules:
        if module_name == 'externalplugin' or module_name.count('externalplugin.') > 0:
            module_names_to_remove.append(module_name)
    for module_name in module_names_to_remove:
        log.debug('\t\t{}'.format(module_name))
        del sys.modules[module_name]
    log.debug('\tremove from sys path {}'.format(root_path))
    sys.path.remove(root_path)

def _walk_plugin(destDirectory, callback):
    pluginsFound = []
    for root, dirs, files in os.walk(destDirectory):
        currentPluginPath = None
        for file in files:
            currentPluginPath = root
            if file == 'setupxmake.py':
                try:
                    log.debug('\tloading setupxmake from directory {}'.format(root))
                    setupxmake = load_plugin(root)
                    log.debug('\tcheck if {} match...'.format(setupxmake.get_name()))
                    discoveryPlugin = callback(setupxmake, root)
                    log.debug('\tcheck returned {}'.format(discoveryPlugin))
                    if discoveryPlugin:
                        readPluginVersion = None
                        try:
                            with open(os.path.join(root, 'version.txt'),'r') as versionFile:
                                readPluginVersion = versionFile.readline()
                                if readPluginVersion.endswith('\n'):
                                    readPluginVersion = readPluginVersion[:-1]
                        except IOError as e:
                            log.exception(e)
                            log.warning('\tcannot retrieve version of plugin in file {}'.format(os.path.join(root, 'version.txt')))
                        pluginInfo = {'name': setupxmake.get_name(), 'externalplugin_path': root, 'build_script_version': readPluginVersion}
                        if hasattr(discoveryPlugin, 'has_priority_over_plugins'):
                            pluginInfo['has_priority_over_plugins'] = discoveryPlugin.has_priority_over_plugins()
                        pluginsFound.append(pluginInfo)
                except AttributeError as e:
                    log.exception(e)
                    log.error('\texternal plugin in {} is incorrect. Module setupxmake should have method get_name()'.format(currentPluginPath))
                finally:
                    # clean python runtime of not useful plugin
                    log.debug('\tremove from sys modules')
                    _unload_plugin(root)
    return pluginsFound

def _download_plugin_from_nexus(nexusUrl, pluginName, pluginVersion=None, nexusRepo=None, destDirectory=None):
    if nexusRepo is None or nexusRepo=='':
        raise XmakeException('cannot load external plugins nexus repository is not set')
    if destDirectory is None or destDirectory=='':
        raise XmakeException('cannot load external plugins destination directory is not set')

    #http://nexus.wdf.sap.corp:8081/nexus/service/local/artifact/maven/content?g=com.sap.prd.xmake.buildplugins&a=sampleplugin&v=LATEST&r=build.snapshots.xmake&e=tar.gz
    url = '{}/nexus/service/local/artifact/maven/content?g=com.sap.prd.xmake.buildplugins&a={}&v={}&r={}&e=tar.gz'.format(
        nexusUrl,
        pluginName,
        'LATEST' if pluginVersion is None else pluginVersion,
        nexusRepo
    )

    try:
        # Download file in temporary directory
        log.debug('\tdownloading external plugin {} from nexus...'.format(pluginName))
        subDirectory = None
        tmpFileName = None
        with contextlib.closing(urllib.urlopen(url, proxies={})) as downloadedFile:
            m = re.search(r'filename="(?P<filename>.*).tar.gz"', downloadedFile.headers['Content-disposition'])
            subDirectory = m.group('filename')
            with tempfile.NamedTemporaryFile(delete=False) as tmpFile:
                tmpFileName = tmpFile.name
                shutil.copyfileobj(downloadedFile, tmpFile)
        log.debug('\texternal plugin {} downloaded'.format(pluginName))

        # Untar temporary file in destDirectory/filename
        log.debug('\tinstalling external plugin {}...'.format(pluginName))
        targetDirectory = os.path.join(destDirectory, subDirectory)
        os.makedirs(targetDirectory)
        with tarfile.open(tmpFileName) as tar:
            tar.extractall(path=targetDirectory)

        readPluginVersion = None
        readCommit = None
        try:
            with open(os.path.join(targetDirectory, 'version.txt'),'r') as versionFile:
                readPluginVersion = versionFile.readline()
                if readPluginVersion.endswith('\n'):
                    readPluginVersion = readPluginVersion[:-1]
                if readPluginVersion.endswith('\r'):
                    readPluginVersion = readPluginVersion[:-1]
        except IOError:
            log.warning('\tthere is no version information for external plugin {}'.format(pluginName))

        try:
            with open(os.path.join(targetDirectory, 'sourceversion.txt'),'r') as commitFile:
                readCommit = commitFile.readline()
                if readCommit.endswith('\n'):
                    readCommit = readCommit[:-1]
                if readCommit.endswith('\r'):
                    readCommit = readCommit[:-1]
        except IOError:
            log.warning('\tthere is no commit information for external plugin {}'.format(pluginName))

        log.info('\t{0:25} version {1:25} commit {2} installed'.format(pluginName, readPluginVersion if readPluginVersion is not None else '?', readCommit if readCommit is not None else '?'))
    except Exception, e:
        log.exception(e)
        log.warning('\tcannot download external plugin {} {}'.format(pluginName, 'LATEST' if pluginVersion is None else pluginVersion))
        log.warning('\tplease check if plugin name and version exist on nexus {}'.format(url))


def _list_plugins_from_nexus(nexusUrl, nexusRepo):
    if nexusRepo is None or nexusRepo=='':
        raise XmakeException('cannot list external plugins from nexus. Repository is not set')

    plugins = set()

    #http://nexus.wdf.sap.corp:8081/nexus/service/local/repositories/build.snapshots/content/com/sap/prd/xmake/buildplugins/
    url = '{}/nexus/service/local/repositories/{}/content/com/sap/prd/xmake/buildplugins'.format(
        nexusUrl,
        nexusRepo
    )

    try:
        # Download xml file in temporary directory
        with contextlib.closing(urllib.urlopen(url, proxies={})) as downloadedFile:
            xmlPluginContent = downloadedFile.read()
            log.debug('\texternal plugin list downloaded')

            # Parse xml file to get the list of external plugins
            root = ET.fromstring(xmlPluginContent)
            if root is None:
                raise Exception('cannot extract the plugin list from nexus xml file downloaded')
            data = root.find('data')
            for item in data.findall('content-item'):
                plugins.add(item.find('text').text)

            log.debug('\tplugins found: {}'.format(', '.join(plugins).upper()))

        return plugins

    except Exception as e:
        log.exception(e)
        log.warning('\tcannot list plugins from {}'.format(url))
        return set()
