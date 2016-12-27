'''
Created on 23.07.2014

@author: D051236
'''

from cosy import CoSy
import utils
import log

def execute_build(build_cfg):
    # set configured tool resolutions

    if not build_cfg.suppress_variant_handling():
        p=build_cfg.variant_cosy()
        cosy=CoSy(p)
        log.info( 'using variant coordinate system '+p)
        log.info( '  coordinate dimensions: '+str(cosy.get_dimensions()))
        for d in cosy.get_dimensions():
            log.info('   dimension '+d+': '+str(cosy.get_dimension(d)))
        coords=build_cfg.variant_coords()
        # projection of variant coordinates according to actual coordinate system
        for c in coords.keys():
            if not c in cosy.get_dimensions():
                log.warning( "invalid dimension '"+c+"' -> adjusted")
                del coords[c]
        cosy.check_coords(coords)
        build_cfg._variant_vector=cosy.variant_coord_vector(coords)

    ct=build_cfg.configured_tools()
    if len(ct)!=0:
        tools=build_cfg.tools();
        for n in ct.keys():
            tid=ct[n].toolid()
            ct[n]._inst_dir=tools[tid][ct[n].version()]

    #as a fallback, use built-in vmake build plugin
    if not build_cfg.skip_build():
        if build_cfg._externalplugin_setup:
            log.info('-'*100)
            log.info('| {0:15} {1:80} |'.format('Build plugin:', build_cfg._build_script_name))
            log.info('| {0:96} |'.format('-'*96))
            log.info('| {0:15} {1:80} |'.format('version:', build_cfg._build_script_version))
            try:
                log.info('| {0:15} {1:80} |'.format('description:', build_cfg._externalplugin_setup.get_description()))
            except AttributeError:
                log.info('| {0:15} {1:80} |'.format('description:', ''))
            log.info('|{0:98}|'.format(''))
            try:
                log.info('| {0:15} {1:80} |'.format('author:', build_cfg._externalplugin_setup.get_author()))
            except AttributeError:
                log.info('| {0:15} {1:80} |'.format('author:', ''))
            try:
                log.info('| {0:15} {1:80} |'.format('contact:', build_cfg._externalplugin_setup.get_contact_email()))
            except AttributeError:
                log.info('| {0:15} {1:80} |'.format('contact:', ''))
            log.info('|{0:98}|'.format(''))
            log.info('-'*100)
        build_script = build_cfg.build_script()
        utils.flush()
        build_script.run()
        utils.flush()
        log.info( "build succeeded")
    else:
        log.info( "build step skipped because of explicitly given option -B")
