#!/usr/local/bin/python2.7
# encoding: utf-8
'''
xmake.xmake -- a multiplatform build tool framework

It features  well-defined build result exchange interfaces and a
pluggable build system (defaulting to vmake)

@author:     Christian Cwienk (d051236)

@copyright:  2013 SAP AG. All rights reserved.

@license:    SAP-proprietary

@contact:    christian.cwienk@sap.com    uwe.krueger@sap.com
'''

import sys
import utils
import log
import inst
import os
from xmake_exceptions import XmakeException

from config import BuildConfig
from phases.build import execute_build
from phases.deploy import execute_deployment, execute_create_staging, execute_close_staging
from phases.forward import execute_forward
from phases.exports import execute_exports
from phases.imports import execute_imports
from phases.prelude import execute_prelude
from phases.promote import execute_promote

# Allows to access to external python modules
# This directory was initialy filled by calling pip cmd
#  Example of pip command call:
#  (pip install --target=[path_to_project]/src/xmake/externals mock)
dirname = os.path.dirname(os.path.realpath(__file__))
if os.path.isfile(dirname+'/../externals'):
    sys.path.append(dirname+'/../externals')


def execute(build_cfg, module, args):
    l = inst.get_installation_dir()
    gen = os.path.join(build_cfg.module_genroot_dir(), module)
    cwd = os.path.join(build_cfg.src_dir(), module)

    cmd = [sys.executable, os.path.join(l, 'xmake', 'xmake.py'), '--gendir', gen, '-r', cwd, '--base-version', build_cfg.base_version()]
    log.info('------------------------------------------------------')
    log.info('- building module '+module+'...')
    log.info('------------------------------------------------------')

    cmd.extend(args)
    log.info('cmd is '+str(cmd))
    rc = log.log_execute(cmd, cwd=cwd)
    if rc != 0:
        raise XmakeException('module build failed for '+module+': RC='+str(rc))


def execute_modules(build_cfg):
    cfg = build_cfg.xmake_cfg()
    if cfg is not None and cfg.has_option('xmake', 'modules'):
        modules = cfg.get('xmake', 'modules')
        args = build_cfg._args
        args = utils.remove_arg('--gendir', 1, args)
        args = utils.remove_arg('-g', 1, args)
        args = utils.remove_arg('--project-root-dir', 1, args)
        args = utils.remove_arg('-r', 1, args)
        args = utils.remove_arg('--base-version', 1, args)

        log.info('found modules '+modules)
        for module in [m.strip() for m in modules.split(',')]:
            execute(build_cfg, module, args)
        log.info('------------------------------------------------------')
        log.info('- continue building of '+build_cfg.component_dir()+'...')
        log.info('------------------------------------------------------')


def notify_phase_ended(name, build_cfg):
    build_script = build_cfg.build_script()
    notify_callback = getattr(build_script, 'after_' + name)
    notify_callback(build_cfg)


def main(argv=sys.argv):
    try:
        build_cfg = BuildConfig()
        build_cfg._args = argv[1:]
        log.logging_monitoring_enable(build_cfg)
        
        v = inst.get_technical_xmake_version()
        if v is not None:
            log.info('technical xmake version is '+v)

        phases = [('PRELUDE',        execute_prelude),
                  ('MODULES',        execute_modules),
                  ('IMPORT',         execute_imports),
                  ('BUILD',          execute_build),
                  ('EXPORT',         execute_exports),
                  ('FORWARD',        execute_forward),
                  ('CREATE_STAGING', execute_create_staging),
                  ('DEPLOY',         execute_deployment),
                  ('CLOSE_STAGING',  execute_close_staging),
                  ('PROMOTE',        execute_promote)]

        def exec_phase(name, method):
            if name == 'PRELUDE':
                log.info('='*100)
            log.info('= {0:96} ='.format('entering xmake ' + name + ' phase'))
            log.info('='*100)

            try:
                method(build_cfg)
                notify_phase_ended(name, build_cfg)
                utils.flush()
            except SystemExit:
                raise
            except BaseException:
                raise
            log.info('end of xmake ' + name + ' phase')
            log.info('='*100)

        [exec_phase(name, method) for (name, method) in phases]
        log.info('')
        log.info('*'*100)
        log.info('*{0:98}*'.format(''))
        log.info('* {0:96} *'.format('XMake Build Successfully Done (^_^)'))
        log.info('*{0:98}*'.format(''))
        log.info('*'*100)
        return 0
    except SystemExit as se:
        log.exception(se)
        log.info('')
        log.error('*'*100)
        log.error('*{0:98}*'.format(''))
        log.error('* {0:96} *'.format('XMake Build failed (-_-\')'))
        log.error('*{0:98}*'.format(''))
        log.error('* {0:96} *'.format('Exit code '+str(se)))
        if build_cfg.genroot_dir():
            log.error('* {0:96} *'.format(os.path.join(build_cfg.genroot_dir(), 'boot.log')))
            log.error('* {0:96} *'.format(os.path.join(build_cfg.genroot_dir(), 'build.log')))
        log.error('*{0:98}*'.format(''))
        log.error('*'*100)
        raise
    except BaseException as ex:
        log.exception(ex)
        log.info('')
        log.error('*'*100)
        log.error('*{0:98}*'.format(''))
        log.error('* {0:96} *'.format('XMake Build failed (-_-\')'))
        log.error('*{0:98}*'.format(''))
        log.error('* {0:96} *'.format('aborting build because of error in last phase'))
        if build_cfg.genroot_dir():
            log.error('* {0:96} *'.format(os.path.join(build_cfg.genroot_dir(), 'boot.log')))
            log.error('* {0:96} *'.format(os.path.join(build_cfg.genroot_dir(), 'build.log')))
        log.error('*{0:98}*'.format(''))
        log.error('*'*100)
        sys.exit(1)

if __name__ == '__main__':
    main(sys.argv)
