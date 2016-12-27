from os.path import join, basename
from glob import glob
import inst, spi, log
import imp
from utils import is_existing_file, has_method
from xmake_exceptions import XmakeException

def list(destDirectory):
    log.info('list of available builtin plugins')
    files = glob(join(destDirectory, '*.py'))
    files.remove(join(destDirectory,'__init__.py'))

    for pluginName in [basename(f)[:-3] for f in files]:
        log.info('\t{}'.format(pluginName))

def discover(build_cfg, wantedPluginName=None):
    log.info('looking for a built-in plugin compatible with source ...')
    contentPlugins={}
    files=glob(join(inst.get_content_plugin_dir(), '*.py'))
    files.remove(join(inst.get_content_plugin_dir(),'__init__.py'))
    files.remove(join(inst.get_content_plugin_dir(),'zzdefaults.py')) #Don't want to use generic plugin by default
    def load_plugin(f):
        plugin_name=basename(f)[:-3]
        module=imp.load_source('plugin',f)
        if not hasattr(module, 'content'):raise XmakeException('ERR: content plugin %s does not define a class "content"' % (plugin_name))

        if not issubclass(module.content, spi.ContentPlugin):
            log.warning("content plugin class is not a subclass of spi.ContentPlugin: "+plugin_name)
        if not has_method(module.content,'__init__', 2):
            log.error( "content plugin class for %s must implement a c'tor w/ exactly two formal parameters" % (plugin_name))
            raise XmakeException("failed to instantiate content plugin "+plugin_name+" (no c'tor def w/ correct amount of formal parameters (which is one) found)")
        impl=module.content(build_cfg,plugin_name)
        contentPlugins[plugin_name] = impl
    map(load_plugin, files)
    list=sorted(contentPlugins.keys())

    compatiblePlugins = []

    if wantedPluginName:
        log.info('\tplugin set in configuration file: '+wantedPluginName)
        if wantedPluginName in contentPlugins:
            p=contentPlugins[wantedPluginName]
            log.info('\t{} is compatible'.format(wantedPluginName))
            compatiblePlugins.append({'name': wantedPluginName,'content_plugin': p})
            return compatiblePlugins
        else:
            plugin=join(inst.get_build_plugin_dir(), wantedPluginName+".py")
            if not is_existing_file(plugin):
                log.warning('\tgiven plugin is not standard: {}'.format(wantedPluginName))
            else:
                log.info('\t{} is compatible'.format(wantedPluginName))
                compatiblePlugins.append({'name': wantedPluginName})
            return compatiblePlugins

    for pn in list:
        p=contentPlugins[pn]
        if p.matches():
            log.info('\t{} is compatible'.format(pn))
            compatiblePlugins.append({'name': pn, 'content_plugin': p})

    if len(compatiblePlugins) > 0:
        return compatiblePlugins

    log.info('\tno compatible built-in plugin found')
    return []
