'''
Created on 23.07.2014

@author: D051236
'''
import os
import re
import utils
import subprocess
import log

from utils import is_existing_file, stripToBlank
from pyjavaproperties import Properties
from xmake_exceptions import XmakeException


def execute_exports(build_cfg):
    '''performs the xmake EXPORT phase (exports are defined in <cfgdir>/export.ads)
the export phase results in a Artifact Deployer 'deploy file'. Its contents may be deployed to a maven repository during the DEPLOY phase'''
    if build_cfg.do_export() is False:
        if build_cfg.do_deploy() is True:
            if os.path.exists(build_cfg.export_file()):
                    log.info('exporting was skipped,because the according option \'-e\' was not set but option \'-d\' is set and export.df exists')
                    return
        else:
            log.info('exporting was skipped, because the according option \'-e\' was not set')
            return
    if not os.path.exists(build_cfg.export_dir()):
        os.mkdir(build_cfg.export_dir())
    if not os.path.exists(build_cfg.export_script()):
        write_version_properties(build_cfg)
        log.warning('exporting was switched on, but there was no export description file at: ' + build_cfg.export_script())
        return
    adargs = [build_cfg.tools().artifact_deployer(),
              'pack', '-f', build_cfg.export_script(), '-p', build_cfg.export_file(),
              '-Dcfgdir='+build_cfg.cfg_dir(), '-Dbsedir='+build_cfg.build_script_ext_dir(),
              '-Dgendir=' + build_cfg.gen_dir(), '-Dsrcdir=' + build_cfg.src_dir(),
              '-Dgenroot=' + build_cfg.genroot_dir(), '-Dcomponentroot=' + build_cfg.component_dir(),
              '-Druntime=' + build_cfg.runtime(),
              '-Dbaseversion=' + build_cfg.base_version(),
              '-DbuildRuntime=' + build_cfg.runtime(),
              '-DbuildVersion=' + build_cfg.version(),
              '-DbuildBaseVersion=' + build_cfg.base_version(),
              '-DbuildVersionSuffix=' + stripToBlank(build_cfg.version_suffix()),
              '-Dimportdir=' + build_cfg.import_dir()]
    # add variant coordinates only if corresponding args are present
    if not build_cfg.suppress_variant_handling():
        def add_coord(k):
            adargs.extend(['-Dbuild'+k+'='+vcoords[k]])

        vcoords = build_cfg.variant_coords()
        map(add_coord, vcoords.keys())
        log.info('variant vector of actual build is '+str(build_cfg.variant_vector()))
        adargs += ['--variant-coordinate-system', build_cfg.variant_cosy(),
                   '--variant-projection-method', 'groupId',
                   '--variant-coordinates', ','.join(build_cfg.variant_vector())]
    else:
        log.warning('no variant coordinates are available for export (i.e. export will fail for platform-dependent contents')
    if build_cfg.suppress_variant_handling():
        log.info('build plugin suppressed variant handling by returning \'None\' as a variant coordinate system')

    # add custom deploy variables if any
    build_script = build_cfg.build_script()
    adargs.extend(['-D' + name + '=' + value for (name, value) in build_script.deploy_variables().items()])
    adargs.extend(['-Dimport' + name + '=' + value for (name, value) in build_script.import_roots().items()])

    # write metatdata
    if build_cfg.scm_snapshot_url() is not None:
        print_attribs = ['scm_snapshot_url', 'build_args', 'productive', 'version', 'xmake_version']
        if not build_cfg.suppress_variant_handling():
            print_attribs.append('variant_coords')
        metadata_str = '''xmake release metadata
~~~~~~~~~~~~~~~~~~~~~~
'''
        metadata_str += '\n'.join([' {0:25}: {1}'.format(attr, str(getattr(build_cfg, attr)())) for attr in print_attribs])
        if build_cfg._externalplugin_setup:
            metadata_str += '\n {0:25}: {1}'.format('xmake_plugin', build_cfg._build_script_name)
            metadata_str += '\n {0:25}: {1}'.format('xmake_plugin_version', build_cfg._build_script_version)
        with open(build_cfg.release_metadata_file(), 'w') as rmf:
            rmf.write(metadata_str)

        # add release metadata if present
        meta = [build_cfg.release_metadata_file(), build_cfg.import_file(), build_cfg.xmake_file(), build_cfg.dependency_file()]
        meta.extend(build_cfg.addtional_metadata())
        for f in meta:
            if is_existing_file(f):
                adargs.extend(['--metadata-file', f])
        adargs.extend(['--metadata-type-id', 'xmake', '--metadata-type-name', 'xmake'])
    elif build_cfg.productive():
        log.error('no release metadata available. Resulting export file must not be released.', log.INFRA)
        raise XmakeException('missing release metadata file for productive build')
    else:
        log.warning('no release metadata available. Resulting export file must not be released.')

    log.info('calling ' + ' '.join(adargs))
    utils.flush()
    rc = log.log_execute(adargs)
    utils.flush()
    log.info('done')
    if rc == 0:
        log.info('export file creation succeeded')
    else:
        log.info('export file creation returned w/ RC==' + str(rc))
        log.error('export file creation resulted in an error. See log output for further hints)', log.INFRA)
        raise XmakeException('export failed')

    write_version_properties(build_cfg)

    p = subprocess.Popen([build_cfg.tools().artifact_deployer(), 'showpackage', '-p', build_cfg.export_file()], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for line in p.stdout:
        searchGroup = re.search(r"group\s+\'(.+)\'", line)
        if searchGroup:
            group = searchGroup.group(1)
            if group.startswith('com.sap.'):
                if not re.search(r'^[1-9]\d*\.\d+\.\d+$', build_cfg.base_version()):
                    if build_cfg.is_release() == 'direct-shipment':
                        log.error('ERR: project version %s does not respect the format for the direct shipment release.' % build_cfg.base_version())
                        raise XmakeException('ERR: project version %s does not respect the format for the direct shipment release.' % build_cfg.base_version())
                    log.warning('project version %s does not respect the format for the direct shipment release.' % build_cfg.base_version())
                if not re.search(r'^[1-9]+', build_cfg.base_version()):
                    if build_cfg.is_release() == 'indirect-shipment':
                        log.error('ERR: project version %s does not respect the format for the indirect shipment release.' % build_cfg.base_version())
                        raise XmakeException('ERR: project version %s does not respect the format for the indirect shipment release.' % build_cfg.base_version())
                    log.warning('project version %s does not respect the format for the indirect shipment release.' % build_cfg.base_version())
                if not re.search(r'^\d+', build_cfg.base_version()):
                    if build_cfg.is_release() == 'milestone' or build_cfg.is_milestone():
                        log.error('ERR: project version %s does not respect the format for the milestone release.' % build_cfg.base_version())
                        raise XmakeException('ERR: project version %s does not respect the format for the milestone release.' % build_cfg.base_version())
                    log.warning('project version %s does not respect the format for the milestone release.' % build_cfg.base_version())
            else:
                if build_cfg.is_release() == 'direct-shipment':
                    log.error('ERR: the group %s does not respect the format for the direct shipment release.' % group)
                    raise XmakeException('ERR: the group %s does not respect the format for the direct shipment release.' % group)
                log.warning('the group %s does not respect the format for the direct shipment release.' % group)
                if not (re.search(r'^\d+[\d\.]*[-\.]sap-\d+', build_cfg.base_version()) or re.search(r'^(\d+\.\d+\.\d+\.[a-zA-Z0-9_-]+)-sap-\d+', build_cfg.base_version())):
                    if build_cfg.is_release() == 'indirect-shipment' or build_cfg.is_release() == 'milestone' or build_cfg.is_milestone():
                        log.error('ERR: project version %s does not respect the format for the indirect shipment or milestone release.' % build_cfg.base_version())
                        raise XmakeException('ERR: project version %s does not respect the format for the indirect shipment or milestone release.' % build_cfg.base_version())
                    log.warning('project version %s does not respect the format for the indirect shipment or milestone release.' % build_cfg.base_version())
    rc = p.wait()
    if rc != 0:
        log.info('showpackage returned w/ RC==' + str(rc))
        log.error('showpackage resulted in an error.', log.INFRA)
        raise XmakeException('export failed')


def write_version_properties(build_cfg):
    p = Properties()
    log.info('version is '+build_cfg.version())
    log.info('scm_url is '+str(build_cfg.scm_snapshot_url()))
    p.setProperty('release_version', build_cfg.version())
    p.setProperty('scm_url', str(build_cfg.scm_snapshot_url()))

#     pairs = [('release_version', build_cfg.version()),
#              ('scm_url', build_cfg.scm_snapshot_url())]
#     contents = '\n'.join([key + '=' + str(value) for (key, value) in pairs])
    with open(build_cfg.version_properties_file(), 'w') as f:
        p.store(f)
