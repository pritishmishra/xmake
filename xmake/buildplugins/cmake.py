import ExternalTools
import xmake_exceptions
import log
import os
import re


class build:
    def __init__(self, build_cfg):
        self.build_cfg = build_cfg
        self._options = {}
        self._options['cmake'] = '3.0.1-sap1'
        self._options['msvc'] = '2010'

    def required_tool_versions(self):
        return {'cmake': self._options['cmake']}

    def set_options(self, opts):
        for option in opts:
            if option.find(':') >= 0:
                (key, value) = option.split(':')
                self._options[key] = value
            else:
                self._options['cmake'] = option

    def run(self):
        log.info('invoking cmake build...')
        self._clean_if_requested()

        global cmake_opts
        global make_opts

        cmake = make = '. ' + os.path.join(self.build_cfg.component_dir(), self._options['config']) + ';' if 'config' in self._options else ''
        cmake += os.path.join(self.build_cfg.tools()['cmake'][self._options['cmake']], 'bin', 'cmake')
        cmake_opts = ' -Dbuild.srcdir:STRING=%s -Dbuild.gendir:STRING=%s -Dbuild.genroot:STRING=%s -Dbuild.cfgdir:STRING=%s -Dbuild.componentroot:STRING=%s -Dbuild.importdir:STRING=%s -Dbuild.bsedir:STRING=%s -Dbuild.resultdir:STRING=%s -Dbuild.runtime:STRING=%s' % (self.build_cfg.src_dir(), self.build_cfg.gen_dir(), self.build_cfg.genroot_dir(), self.build_cfg.cfg_dir(), self.build_cfg.component_dir(), self.build_cfg.import_dir(), self.build_cfg.build_script_ext_dir(), self.build_cfg.result_base_dir(), self.build_cfg.runtime())
        make += 'make'
        make_opts = ' $MAKE_OPTIONS'
        (os.environ['build_srcdir'], os.environ['build_gendir'], os.environ['build_genroot'], os.environ['build_cfgdir'], os.environ['build_componentroot'], os.environ['build_importdir'], os.environ['build_bsedir'], os.environ['build_resultdir'], os.environ['build_runtime']) = (self.build_cfg.src_dir(), self.build_cfg.gen_dir(), self.build_cfg.genroot_dir(), self.build_cfg.cfg_dir(), self.build_cfg.component_dir(), self.build_cfg.import_dir(), self.build_cfg.build_script_ext_dir(), self.build_cfg.result_base_dir(), self.build_cfg.runtime())

        def add_tool(tid, d):
            global cmake_opts
            cmake_opts += ' -D tool.%s.dir:STRING=%s' % (tid, d)
            os.environ['tool_%s_dir' % tid] = d
        self._handle_configured_tools(add_tool)

        os.chdir(self.build_cfg.gen_dir())
        if ExternalTools.OS_Utils.is_UNIX():
            log.info(cmake + cmake_opts + ' $CMAKE_OPTIONS -G "Unix Makefiles" ' + os.path.join(self.build_cfg.component_dir(), 'src'))
            rc = log.log_execute_shell(cmake + cmake_opts + ' -G "Unix Makefiles" ' + os.path.join(self.build_cfg.component_dir(), 'src'))
            if rc > 0:
                raise xmake_exceptions.XmakeException('ERR: cmake returned %s' % str(rc))
            log.info(make + make_opts + ' -f Makefile')
            rc = log.log_execute_shell(make + make_opts + ' -f Makefile')
            if rc > 0:
                raise xmake_exceptions.XmakeException('ERR: cmake returned %s' % str(rc))
        else:
            msvc_home = self.build_cfg.tools()['msvc'][self._options['msvc']]
            log.info(cmake + cmake_opts + ' %CMAKE_OPTIONS% -G "Visual Studio 10 Win64" ' + os.path.join(self.build_cfg.component_dir(), 'src'))
            rc = log.log_execute(cmake + cmake_opts + ' %CMAKE_OPTIONS% -G "Visual Studio 10 Win64" ' + os.path.join(self.build_cfg.component_dir(), 'src'))
            if rc > 0:
                raise xmake_exceptions.XmakeException('ERR: cmake returned %s' % str(rc))
            with open(os.path.join(self.build_cfg.component_dir(), 'src', 'CMakeLists.txt'), 'r') as f:
                for line in f:
                    searchProject = re.search(r'project\s*\((.*?)\)', line)
                    if searchProject:
                        cmake_project = searchProject.group(1) + '.vcxproj'
                        break
            with open('win_compile.bat', 'w') as f:
                f.write('CALL "%s\\VC\\vcvarsall.bat" x86_amd64\n' % msvc_home)
                f.write('msbuild ' + cmake_project + ' /p:Configuration=Release /maxcpucount /p:Platform=X64\n')
            rc = log.log_execute(['win_compile.bat'])
            if rc > 0:
                raise xmake_exceptions.XmakeException('ERR: cmake returned %s' % str(rc))
        return 0
