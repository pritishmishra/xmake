'''
Created on 07.02.2014

@author: D051236
'''
import log
from os.path import join
from xmake_exceptions import XmakeException
from ExternalTools import OS_Utils
from utils import stripToBlank, mkdirs
from spi import JavaBuildPlugin
import inst


class build(JavaBuildPlugin):
    def __init__(self, build_cfg):
        JavaBuildPlugin.__init__(self, build_cfg)
        self._variant_cosy_gav = None
        self._ant_version = '1.9.4'
        self._imports = None

    def java_required_tool_versions(self):
        return {'ant': self._ant_version}

    def variant_cosy_gav(self):
        return self._variant_cosy_gav

    def java_set_option(self, o, v):
        if o is None or o == 'cosy':
            if len(v.split(':')) == 2:
                log.info('  using coordinate system ' + v)
                self._variant_cosy_gav = v
            else:
                raise XmakeException('ERR: invalid coordinate system specification '+str(v)+': expected <name>:<version>')
        else:
            if o == 'version':
                log.info('  using ant version ' + v)
                self._ant_version = v
            else:
                if o == 'importlabels':
                    self._imports = [i.strip() for i in v.split(',')]
                else:
                    log.warning('unknown build plugin option; '+o)

    def import_roots(self):
        '''returns import root bindings that will be passed to the 'Artifact Importer' during the
        IMPORT phase'''
        imps = {}
        if self._imports is not None:
            for i in self._imports:
                imps[i] = join(self.build_cfg.import_dir(), i)
                mkdirs(imps[i])
        return imps

    def java_run(self):
        self._clean_if_requested()

        self._anthome = self.build_cfg.tools()['ant'][self._ant_version]
        log.info('found ant: ' + self._anthome)
        ant_executable = self._ant_executable()
        ant_args = []
        build_cfg = self.build_cfg
        if not OS_Utils.is_UNIX():
            ant_args.extend([join(inst.get_build_plugin_dir(), 'ant_wrapper.bat')])
        ant_args.extend([ant_executable,
                         '-Dbuild.srcdir=' + build_cfg.src_dir(), '-Dbuild.wrkdir=' + self._wrk_dir(),
                         '-Dbuild.gendir=' + build_cfg.gen_dir(), '-Dbuild.genroot=' + build_cfg.genroot_dir(),
                         '-Dbuild.cfgdir=' + build_cfg.cfg_dir(), '-Dbuild.componentroot=' + build_cfg.component_dir(),
                         '-Dbuild.importdir=' + build_cfg.import_dir(), '-Dbuild.bsedir=' + build_cfg.build_script_ext_dir(),
                         '-Dbuild.module_genroot=' + build_cfg.module_genroot_dir(),
                         '-Dbuild.resultdir=' + build_cfg.result_base_dir(),
                         '-Dbuild.runtime=' + build_cfg.runtime(),
                         '-f', self._build_xml_file()])

        props = dict()
        # not possible under NT to pass empty argument, all variants result in strange behavior or just do not work
        props['build.versionsuffix'] = stripToBlank(build_cfg.version_suffix())
        props['build.baseversion'] = stripToBlank(build_cfg.base_version())
        props['build.version'] = stripToBlank(build_cfg.version())

        for (i, d) in self.import_roots().items():
            props['build.importlabel.'+i+'.dir'] = d

        def add_tool(n, d):
            props[self._tool_property(n)] = d
            props[self._tool_id_property(n)] = build_cfg.configured_tools()[n].toolid()
            for t in build_cfg.configured_tools()[n].tags():
                props[self._tool_tag_property(n, t)] = 'true'
                props['build.'+self._tool_tag_property(n, t)] = 'true'

        self._handle_configured_tools(add_tool)

        def add_dep(key, d):
            props[self._import_property(key)] = d
            props['build.'+self._import_property(key)] = d
        self._handle_dependencies(add_dep)

        def add_opts(d, prefix):
            for k in d.keys():
                props[prefix+'.'+k] = d[k]

        if not build_cfg.suppress_variant_handling():
            add_opts(build_cfg.variant_info(), 'build.variant.info')
            add_opts(build_cfg.variant_coords(), 'build.variant.coord')

        if len(props) > 0:
            filename = join(build_cfg.temp_dir(), 'ant.properties')
            with open(filename, 'w') as f:
                def add_arg(key):
                    f.write(key+'='+props[key].replace('\\', '\\\\') + '\n')
                map(add_arg, props.keys())
                ant_args.extend(['-propertyfile', filename])

        if build_cfg.build_platform() is not None:
            ant_args.extend(['-Dbuild.platform', build_cfg.build_platform()])
        if build_cfg.build_mode() is not None:
            ant_args.extend(['-Dbuild.mode', build_cfg.build_mode()])

        if build_cfg.skip_test():
            ant_args.extend(['-Dbuild.skip.test', 'true'])
        else:
            ant_args.extend(['-Dbuild.do.test', 'true'])
        if build_cfg.build_args() is not None:
            ant_args.extend(build_cfg.build_args()[1:])
        log.info('invoking ant: ' + ' '.join(ant_args))
        # logfile=join(self.build_cfg.temp_dir(),'ant.log')
        # ant_args.extend(['-l', logfile])
        self.call_ant(ant_args)

#    def required_tool_versions(self):
#        return {'ant': '1.9.4'}

    def call_ant(self, args):
        rc = self.java_exec_env.log_execute(args)
        if rc > 0:
            raise XmakeException('ERR: ant returned %s' % str(rc))

    def _import_property(self, key):
        return 'imports.'+key+'.dir'

    def _tool_property(self, key):
        return 'tool.'+key+'.dir'

    def _tool_tag_property(self, key, tag):
        return 'tool.'+key+'.tag.'+tag

    def _tool_id_property(self, key):
        return 'tool.'+key+'.id'

    def _ant_executable(self):
        cmd = 'ant'  # +self.build_cfg.tools().tool_suffix('bat')
        if self._anthome is not None:
            self.java_exec_env.env['ANT_HOME'] = self._anthome
        if 'ANT_HOME' in self.java_exec_env.env:
            return join(self.java_exec_env.env['ANT_HOME'], 'bin', cmd)
        log.warning('ANT_HOME was not set - falling back to using ant from PATH', log.INFRA)
        ant_executable = OS_Utils.find_in_PATH('ant')
        if ant_executable is not None:
            return ant_executable
        log.error('ant was not found in PATH and ANT_HOME was not set - aborting build', log.INFRA)
        raise XmakeException('ant was neither configured via ANT_HOME env var nor present in PATH')

    def _build_xml_file(self):
        # if any build args are present, first arg is build.xml
        if self.build_cfg.build_args() is not None and len(self.build_cfg.build_args()) > 0:
            return join(self.build_cfg.src_dir(), self.build_cfg.build_args()[0])
        return join(self.build_cfg.src_dir(), 'build.xml')
