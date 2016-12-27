'''
Created on 18.12.2013

@author: Christian Cwienk (d051236)
'''

from ExternalTools import OS_Utils
import os
import imp
import inspect
import shutil
import stat
import log
from distutils import dir_util
from xmake_exceptions import XmakeException
from utils import is_existing_directory, is_existing_file
from os.path import join

from spi import BuildPlugin

from phases.prelude import XMAKE_BUILD_MODE

BUILDTOOLS_DIR_NAME = 'buildtools'


class build(BuildPlugin):
    """an xmake build script implementation. will be instantiated during the xmake PRELUDE phase and
    executed (using the run() method) during the xmake BUILD phase"""
    def __init__(self, build_cfg):
        BuildPlugin.__init__(self, build_cfg)
        self.is_UNIX = OS_Utils.is_UNIX()
        self._cosy_version = '1.1.2'

    def _validate_vmake_installation(self):
        if OS_Utils.find_in_PATH("vmake") is not None:
            return
        if is_existing_file(join(self.build_cfg.vmake_instdir(), "pgm", "vmake" if OS_Utils.is_UNIX() else "vmake.exe")):
            return
        raise XmakeException('Vmake was not found neither in PATH nor in %s.' % (self.build_cfg.vmake_instdir()))

    def _symlink(self, source, link_name):
        source = os.path.abspath(source)
        if self.is_UNIX:
            getattr(os, 'symlink')(source, link_name)
        # unfortunatly, python 2.7 does not support symlinks on windows
        else:
            if os.system("mklink /d " + link_name + " " + source) != 0:
                raise XmakeException('failed to create symbolic link (hint: you may need to run this build w/ administrative privileges)')

    def _build_tools_dir(self):
        # e.g.: project-root/bse/buildtools
        return os.path.join(self.build_cfg.build_script_ext_dir(), BUILDTOOLS_DIR_NAME)

    def _build_tools_source_dir(self):
        # e.g.: project-root/src/buildtools
        return os.path.join(self.build_cfg.src_dir(), BUILDTOOLS_DIR_NAME)

    def _build_tools_import_dir(self):
        # e.g.: project-root/import/buildtools
        return os.path.join(self.build_cfg.import_dir(), BUILDTOOLS_DIR_NAME)

    def _effective_buildtools_dir(self):
        # e.g.: project-root/gen/out/buildtools
        return os.path.join(self.build_cfg.gen_dir(), BUILDTOOLS_DIR_NAME)

    def run(self):
        """the vmake build execution implementation. Invoked during the xmake BUILD phase"""
        self._initialise()
        log.info("invoking vmake build...")
        self._before_build_callback()
        vmake_args = self.build_cfg.build_args()
        vmake_args = ['all.vprj'] if vmake_args is None or len(vmake_args) == 0 else vmake_args
        self._handle_build_mode(self.build_cfg.variant_info()[XMAKE_BUILD_MODE])
        vmake_args = ' '.join(vmake_args)
        if self.is_UNIX:
            rc = os.system("bash -c \"source " + self._iprofile() + " && vmake " + vmake_args + "\"")  # assume there must be a 'all.vprj' vmake target
        else:
            rc = os.system(self._iprofile() + " && vmake " + vmake_args)  # assume there must be a 'all.vprj' vmake target
        # dirty-hacks: 1. RC == 1 seems to mean build was OK,
        #              2. left-shift RC if on unix
        if self.is_UNIX and rc > 254:
            rc = rc >> 8

        if rc > 1:
            raise XmakeException('ERR: vmake returned RC >1: %s' % str(rc))

    def _handle_build_mode(self, build_mode):
        build_modes = ['opt', 'dbg', 'rel']
        if build_mode is None:
            log.warning('no build_mode was specified - defaulting to opt')
            return
        if build_mode not in build_modes:
            raise XmakeException('unsupported build mode: %s' % (build_mode))
        # todo: do not modify own process' environment, but only to this for vmake subproc
        os.environ['VMAKE_VERSION'] = build_mode
        os.environ['VMAKE_DEFAULT'] = build_mode

    def _before_build_callback(self):
        before_build_script = join(self.build_cfg.cfg_dir(), 'vmake_before_build.py')
        if not is_existing_file(before_build_script):
            return
        module = imp.load_source('before_build', before_build_script)
        if not hasattr(module, 'run'):
            raise XmakeException('ERR: tool f %s does not define a method "run"' % (before_build_script))
        run_method = module.run
        if not callable(run_method):
            raise XmakeException('ERR: tool f %s does not define a method "run"' % (before_build_script))
        argcount = len(inspect.getargspec(run_method)[0])
        if not argcount < 2:
            raise XmakeException('ERR: tool file %s does not define a function "run" with one or no formal parameters' % (before_build_script))
        run_method(self.build_cfg) if argcount == 1 else run_method()

    def variant_cosy_gav(self):
        return 'vmake:'+self._cosy_version

    def set_option_string(self, v):
        c = v.split(':')
        if len(c) > 1:
            raise XmakeException('ERR: only version of vmake variant coordinate system can be set: %s' % (v))
        self._cosy_version = v
        log.info('  using coordinate system '+self.variant_cosy_gav())


#    def variant_cosy(self):
#        """returns the (optional) variant coordinate system to be used for handling variants"""
#        return os.path.join(self.build_cfg.tools().commonrepo_root(),
#                            'coordinatesystems', 'com.sap.commonrepo.coordinatesystems',
#                            'vmake', '1', 'vmake.variant-coordinate-system')

    def deploy_variables(self):
        """returns deploy variables that ought to be made available to export scripts
        (this method will be invoked by xmake during the EXPORT phase)"""
        return {'vmakeGenDir': os.path.join(self._own_dir(), 'gen'),
                'vmakeWrkDir': self._wrk_dir(),
                'buildtools': self._effective_buildtools_dir()}

    def import_roots(self):
        """returns import root bindings that will be passed to the 'Artifact Importer' during the
        IMPORT phase"""
        return {'buildtools': self._build_tools_import_dir()}

    def import_variables(self):
        """returns import variable binding that will be passed to the 'Artifact Importer' during the
        IMPORT phase"""
        return {}

    def _clean_if_requested(self):
        if not self.build_cfg.do_clean() or not os.path.isdir(self._own_dir()):
            return
        log.info("purging build directory")
        wrkDir = os.path.join(self._own_dir(), 'sys', 'wrk')
        if os.path.exists(wrkDir):
            shutil.rmtree(wrkDir)

    def _init_buildtools(self):
        # use symbolic links if only one buildtools directory exists
        buildtools_target_dir = self._effective_buildtools_dir()

        def rm_if_target_exists():
            if os.path.exists(buildtools_target_dir):
                OS_Utils.rm_dir(buildtools_target_dir)
        if os.path.exists(self._build_tools_dir()) and not os.path.exists(self._build_tools_import_dir()) and not os.path.exists(self._build_tools_source_dir()):
            rm_if_target_exists()
            buildtools_source = self._build_tools_dir()
            self._symlink(buildtools_source, buildtools_target_dir)
            return
        if not os.path.exists(self._build_tools_dir()) and os.path.exists(self._build_tools_import_dir()) and not os.path.exists(self._build_tools_source_dir()):
            rm_if_target_exists()
            buildtools_source = self._build_tools_import_dir()
            self._symlink(buildtools_source, buildtools_target_dir)
            return
        if not os.path.exists(self._build_tools_dir()) and not os.path.exists(self._build_tools_import_dir()) and os.path.exists(self._build_tools_source_dir()):
            rm_if_target_exists()
            buildtools_source = self._build_tools_source_dir()
            self._symlink(buildtools_source, buildtools_target_dir)
            return
        rm_if_target_exists()
        # we need to cp buildtools (local buildtool contents win over imported ones)

        if is_existing_directory(self._build_tools_import_dir()):
            dir_util.copy_tree(self._build_tools_import_dir(), buildtools_target_dir)
        if is_existing_directory(self._build_tools_source_dir()):
            dir_util.copy_tree(self._build_tools_source_dir(), buildtools_target_dir)
        if is_existing_directory(self._build_tools_dir()):
            dir_util.copy_tree(self._build_tools_dir(), buildtools_target_dir)

    def _initialise(self):
        self._validate_vmake_installation()
        self._clean_if_requested()
        # link sources to gen-dir
        sys_dir = os.path.join(self.build_cfg.gen_dir(), 'sys')
        if not os.path.exists(sys_dir):
            os.makedirs(sys_dir)
        src_symlink = os.path.join(self.build_cfg.gen_dir(), 'sys', 'src')
        if not os.path.exists(src_symlink):
            self._symlink(self.build_cfg.src_dir(), src_symlink)
        self._init_buildtools()

        self._initialise_UNIX() if self.is_UNIX else self._initialise_NT()

    def _vmake_path(self):
        path_dirs = [self._own_dir(),
                     os.path.join(self.build_cfg.component_dir(), 'buildtools'),
                     os.path.join(self.build_cfg.import_dir())]
        return ','.join(path_dirs)

    def _perl_instdir(self):
        '''determines a perl installation directory on the local host.
        if the PERL env var is set, this value is used. Otherwise, "perl" is being looked up in the PATH
        the first found entry from the PATH will be used / returned'''
        if 'PERL' in os.environ:
            return os.environ['PERL']
        perl_paths = OS_Utils.find_in_PATH('perl')
        if perl_paths is None:
            log.error("could not determine perl installation directory (must either be set in env var 'PERL' or reside in PATH)", log.INFRA)
            raise XmakeException("perl instalation directory could not be determined")
        # we arbitrarily choose the first found perl entry (instdir is two levels above perl binary)
        perl_instdir = os.path.abspath(os.path.join(perl_paths[0], os.path.pardir, os.path.pardir))
        log.info("using perl installation from " + perl_instdir)
        return perl_instdir

    def _own_dir(self):
        return os.path.abspath(self.build_cfg.gen_dir())

    def _wrk_dir(self):
        return os.path.join(self._own_dir(), 'sys', 'wrk')

    def _is_initialised(self):
        # heuristically determine this depending on whether iprofile is present
        return os.path.exists(self._iprofile())

    def _iprofile(self):
        basedir = self.build_cfg.gen_dir()
        return os.path.join(basedir, '.iprofile') if self.is_UNIX else os.path.join(basedir, 'iprofile.bat')

    def _tool_property(self, key):
        return 'BUILD_TOOL_'+key+'_DIR'

    def _tool_tag_property(self, key, tag):
        return 'BUILD_TOOL_'+key+'_TAG_'+tag

    def _import_property(self, key):
        return 'BUILD_IMPORTS_'+key+'_DIR'

    def _set_properties(self, verb, contents=""):
        contents += verb+" OWN=" + self._own_dir() + "\n"
        contents += verb+" GENROOTDIR=" + self.build_cfg.genroot_dir() + "\n"
        contents += verb+" IMPORTDIR=" + self.build_cfg.import_dir() + "\n"
        contents += verb+" BUILD_GENROOT_DIR=" + self.build_cfg.genroot_dir() + "\n"
        contents += verb+" BUILD_IMPORT_DIR=" + self.build_cfg.import_dir() + "\n"
        contents += verb+" BUILD_RESULT_DIR=" + self.build_cfg.result_base_dir() + "\n"
        contents += verb+" BUILD_RUNTIME=" + self.build_cfg.runtime() + "\n"
        contents += verb+" BUILD_VERSION=" + self.build_cfg.version() + "\n"
        contents += verb+" BUILD_BASE_VERSION=" + self.build_cfg.base_version() + "\n"

        def add_tool(tid, d):
            contents += verb+" "+self._tool_property(tid)+"="+d
            for t in self.build_cfg.configured_tools()[tid].tags():
                contents += "export "+self._tool_tag_property(tid, t)+"=true"

        self._handle_configured_tools(add_tool)

        def add_dep(key, d):
            contents += verb+self._import_property(key)+'='+d

        self._handle_dependencies(add_dep)
        return contents

    def _initialise_UNIX(self):
        with open(self._iprofile(), 'w') as f:
            contents = """
#!/bin/bash

###############
## this is a generated configuration file for vmake
## manual modifications will be lost when this file is re-generated
###############

export VMAKE_REPORT_FORMAT_TITLEBAR=" - <PROGRESS(1)> % ( <TARGETS_LEFT> of <ALL_TARGET_COUNT>; <CURRENT_DESCRIPTION>; <ERROR_COUNT> error(s) )"
# 'L' is required for proper linking of static libraries on UN*X
export VMAKE_OPTION=L
export TOOLEXT=.pl
export TOOLSHELL=/usr/bin/perl

export LIB_TYPE=a
export DLL_TYPE=so

"""
            # add non-static parts
            if self.build_cfg.bit_count() == 64:
                contents += 'export BIT64=1\n'
            contents += "export SRC=" + self.build_cfg.src_dir() + "\n"
            contents += "export WRK=" + self._wrk_dir() + "\n"

            contents += self._set_properties('export')

            contents += "export TOOLVARS=$OWN/buildtools/config/toolvars.pl\n"
            contents += "export VMAKETOOL=" + self.build_cfg.vmake_instdir() + "\n"
            contents += "export TOOL=$VMAKETOOL\n"
            contents += "export PERL5LIB=$OWN/buildtools/bin:$TOOL/lib/perl5\n"
            contents += 'export VMAKE_PATH=' + self._vmake_path()
            contents += """
export INITIAL_PATH=${INITIAL_PATH:=$PATH}
export PATH=$INITIAL_PATH
export PATH=$TOOL/bin:$TOOL/pgm:$PATH

# configure output directories (specific for buildmode (dbg/opt)
export INSTROOT=$OWN/gen/indep
export INSTROOT_OPT=$OWN/gen/opt
export INSTROOT_DBG=$OWN/gen/dbg

cd $OWN
echo "current dir     : `pwd`"
echo
echo "\$VMAKEBUILD_BASE: $VMAKEBUILD_BASE"
echo "\$VMAKESRC_BASE  : $VMAKESRC_BASE"
echo "\$VMAKETOOL_BASE : $VMAKETOOL_BASE"
echo
echo "\$TOOL           : $TOOL"
echo "\$VMAKE_PATH     : $VMAKE_PATH"
echo
echo ==================================================================
"""
            f.write(contents)
            f.flush()
        st = os.stat(self._iprofile())
        os.chmod(self._iprofile(), stat.S_IEXEC | st.st_mode)

    def _initialise_NT(self):
        with open(self._iprofile(), 'w') as f:
            contents = """@echo off
:: this is a generated configuration file for vmake
:: it may be freely modified. In order to have it generated anew, rm the file

set VMAKE_NG_FEATURES=yes
set VMAKE_REPORT_FORMAT_TITLEBAR=" - <PROGRESS(1)> %% ( <TARGETS_LEFT> of <ALL_TARGET_COUNT>; <CURRENT_DESCRIPTION>; <ERROR_COUNT> error(s) )"

"""
            contents += "set VMAKETOOL=" + self.build_cfg.vmake_instdir() + "\n"
            contents += "set TOOL=%VMAKETOOL%\n"

            contents += self._set_properties('set')

            contents += "set VMAKE_PATH=" + self._vmake_path() + '\n'
            contents += 'set PERL=' + self._perl_instdir() + '\n'

            contents += r"""
if not defined INITIAL_PATH set INITIAL_PATH=%PATH%
set PATH=%INITIAL_PATH%
set PATH=%TOOL%\bin;%TOOL%\pgm;%PATH%

set SRC=%OWN%\sys\src
set TMP=%OWN%\tmp
set TOOLVARS=%OWN%\buildtools\config\toolvars.pl
set WRK=%OWN%\sys\wrk

set INSTROOT=%OWN%\gen\indep
set INSTROOT_OPT=%OWN%\gen\opt
set INSTROOT_DBG=%OWN%\gen\dbg

set LIB_TYPE=lib
set DLL_TYPE=dll

if not defined TOOLSHELL set TOOLSHELL=%PERL%\bin\perl.exe
if not defined TOOLEXT set TOOLEXT=.pl
if not defined INITIAL_PATHEXT set INITIAL_PATHEXT=%PATHEXT%
set PATHEXT=%INITIAL_PATHEXT%
set PATHEXT=%PATHEXT%;%TOOLEXT%

:: configure vmake build tool libraries
set PERL5LIB=%OWN%\buildtools\bin;%TOOL%\lib\perl5

"""
            if self.build_cfg.bit_count() == 64:
                contents += 'set BIT64=1\n'
            contents += ":: Visual Studio installation directory (assume it is properly installed in default location)\n"

            vs_inst_path = self.build_cfg.tools()['msvc']['100']
            vc_vars_all = os.path.normpath(os.path.join(vs_inst_path, "VC", "vcvarsall.bat"))
            contents += 'set VCVARS_PATH="' + vc_vars_all + '"\n'
            if self.build_cfg.bit_count() == 64:
                contents += 'set VCVARS_PLATFORM_TAG=amd64'
            else:
                contents += 'set VCVARS_PLATFORM_TAG=x86'

            contents += r"""

echo Microsoft Compiler:
if exist %VCVARS_PATH% (
    call %VCVARS_PATH% %VCVARS_PLATFORM_TAG%
) else (
    echo no installed compiler detected !
)

echo.
echo %%VMAKEBUILD_BASE%%: %VMAKEBUILD_BASE%
echo %%VMAKESRC_BASE%%  : %VMAKESRC_BASE%
echo %%VMAKETOOL_BASE%% : %VMAKETOOL_BASE%
echo %%BRANCH%%         : %BRANCH%
echo.
echo %%VMAKETOOL%%      : %VMAKETOOL%
echo %%OWN%%            : %OWN%
echo %%VMAKE_PATH%%     : %VMAKE_PATH%
echo.
echo ==================================================================
"""

            f.write(contents)
            f.flush()
