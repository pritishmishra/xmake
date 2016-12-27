'''
Created on 25.09.2014

@author: d021770
'''

import appcache
import time
import sys,os
import xmake
import urllib
import subprocess
import imp
import re
import traceback
import log
import options
import inst
import utils
from tarfile import TarFile
from optparse import OptionParser
from os.path import join, getctime, getmtime, isdir, isfile, basename
from os import listdir, environ
from utils import read_first_line, get_first_line, touch_file, is_existing_file
from utils import rmtree, is_existing_directory, flush, contains, Bunch
from utils import remove_arg, remove_dedicated_arg
from config import BuildConfig
from phases.prelude import setup_config, create_gendir, determine_version_suffix
from xmake_exceptions import XmakeException
from ExternalTools import tool_package_url,tool_retrieve_url

import xml.etree.ElementTree as ET

from const import XMAKE_NEXUS

XMAKE_VERSION   = 'XMAKE_VERSION'
XMAKE_CHECK_TIME            = 12*60*60
XMAKE_EXPIRE_TIME           = 24*60*60
XMAKE_PKG_NEXUS = XMAKE_NEXUS
XMAKE_PKG_REPO  = 'build.snapshots.xmake'
XMAKE_PKG_GID  = 'com.sap.prd.xmake'
XMAKE_PKG_AID  = 'xmake'
XMAKE_PKG_SUF  = 'tar.gz'

test_mode=False

def versionlist_url():
    url='/'.join([XMAKE_PKG_NEXUS,'nexus/content/groups',XMAKE_PKG_REPO,XMAKE_PKG_GID.replace('.', '/'),XMAKE_PKG_AID,'maven-metadata.xml'])
    return url

def package_url(v):
    return tool_package_url((XMAKE_PKG_GID,XMAKE_PKG_AID,XMAKE_PKG_SUF,'',v),XMAKE_PKG_REPO,XMAKE_PKG_NEXUS)

def get_version_list():
    f=urllib.urlopen(versionlist_url())
    root=ET.parse(f)
    return [ x.text for x in root.findall("./versioning/versions/version")]

def find_latest(p):
    found=p
    try:
        p.index('*')
        p=p.replace('*','(.*)')
        m=-1
        for v in get_version_list():
            mo=re.compile(p).match(v)
            if mo!=None:
                try:
                    c=int(mo.group(1))
                    if (c>m):
                        found=v
                        m=c
                except ValueError:
                    pass
    except ValueError:
        pass
    return found

def load_latest(v):
    l=None
    v=find_latest(v)
    if v!=None:
        bc=BuildConfig()
        bc._do_import=True
        log.info( 'required bootstrapper version is '+v)
        l=get_xmake_version(v, bc)
        if l is None:
            log.error( 'required bootstrapper version not found: '+v)
            sys.exit(2)
        else:
            log.info( 'required bootstrapper version found at '+l)

    return (v,l)

def update_snapshot(versions,v):
    a=versions._retriever(v)
    x=TarFile.open(a,'r').extractfile("sourceversion.txt")
    sv=read_first_line(x,'cannot read sourcerversion.txt from '+a)
    log.info( "latest version of "+v+' is '+sv)

    def retrieve(aid):
        return a

    x=versions.get((v,sv),retrieve)
    d=versions.path(v)
    if isdir(d): touch_file(d)
    return x

xmake_loaded=None

def get_xmake_version(v, build_cfg):
    def finalize(aoid,d):
        touch_file(join(d,'.loaded'))

    def retrieve(aid):
        url=package_url(aid)
        if test_mode:
            return join(build_cfg.gen_dir(),"xmake.tar.gz")
        return tool_retrieve_url(url,aid,XMAKE_PKG_REPO)

    if environ.has_key('XMAKE_VERSION_INSTALLATION_ROOT'):
        version_root=environ['XMAKE_VERSION_INSTALLATION_ROOT']
        if not is_existing_directory(version_root):
            log.error("env var 'XMAKE_VERSION_INSTALLATION_ROOT' was set, but does not point to an existing directory. Either unset or change it")
            raise XmakeException("encountered invalid value of env var 'XMAKE_TOOL_INSTALLATION_ROOT'")
    else:
        version_root=join(inst.get_xmake_user_home(),'versions')

    #xmake_inst_dir = get_installation_dir()
    #version_root=join(xmake_inst_dir,"versions")

    versions=appcache.AppCache("xmake",join(version_root),retrieve,finalize)

    if (v.endswith("-SNAPSHOT")):
        p=versions.path(v)
        latest=get_latest(p)
        if latest==None:
            log.info('no snapshot found for '+v+' -> load new version')
            return update_snapshot(versions,v)
        else:
            cleanup(p)
            try:
                if build_cfg.do_import():
                    log.info('check for newer snapshot for xmake version '+v)
                    return update_snapshot(versions,v)
                else:
                    c=time.time()
                    t=getmtime(p)
                    if t+XMAKE_CHECK_TIME<c:
                        log.info('check time exceeded for '+v+' -> check for newer snapshot')
                        return update_snapshot(versions,v)
            except XmakeException as xme:
                log.warning('update of xmake version failed: '+ xme.msg)
                log.warning('reusing actually available snapshot')
        return latest
    else:
        return versions.get(v)

def cleanup(d):
    expired=[]
    c=time.time()-XMAKE_EXPIRE_TIME

    def clean(skip,cand):
        if skip[0]<c and skip[1]!=None:
            expired.append(skip[1])

    get_latest(d,clean)

    if len(expired)>0:
        log.info('cleanup expired snapshot versions '+str([ basename(x) for x in expired]))
        for d in expired:
            try:
                rmtree(d)
            except OSError:
                log.info('  failed to delete '+d)

def get_latest(d,h=lambda x,y:True):
    found=[0,None]
    if isdir(d):
        for f in listdir(d):
            p=join(d,f)
            if isdir(p):
                cur=[getctime(p),p]
                if cur[0]>found[0]:
                    skip=found
                    found=cur
                else:
                    skip=cur
                h(skip,found)
    return found[1]

###################################################
###################################################
## compatibility handling
###################################################
###################################################

def prepare_args(build_cfg, path, args):
    log.info("  cleanup command line for selected xmake version")
#     keep --xmake-version and -X option in order to be stored in release-metatada file
#     args=remove_arg('--xmake-version',1,args)
#     args=remove_arg('-X',1,args)
    args=remove_arg('--default-xmake-version',1,args)
    args=remove_arg('--buildruntime',1,args)

    p=join(path,'xmake','options.py')
    targetopts=None
    if is_existing_file(p):
        log.info("  loading options for selected xmake version")
        mod = imp.load_source('targetoptions', p)
        if hasattr(mod, 'features'):
            features=mod.features
            log.info("  found xmake version with features "+str(features))
        else:
            log.info("  found featureless xmake version")
            features={}
        targetopts=mod.cli_parser()
    else:
        log.info('  falling back to default options for older xmake version')
        targetopts=options.base_09_options();
        features={}

    if targetopts is not None:
        def handle_option(o,args):
            # option arguments must be ignored, but here only a basic option parsing is done just by looking
            # for option markers.
            if options.cli_parser().has_option(o): # WORKARROUND: ignore option arguments, if they look like options
                #log.info("    opt: "+o)
                if o != '-V' and not o.startswith('--variant-') and not targetopts.has_option(o):
                    index=contains(o,'=')
                    if index>=0:
                        k=o[:index]
                    else:
                        k=o
                    #log.info("found unsupported option "+k)
                    nargs=curopts.get_option(k).nargs
                    log.warning("given option '"+k+"' with "+str(nargs)+" arg(s) is not supported by selected xmake version -> option omitted")
                    if k!=o:
                        nargs=0
                    args=remove_arg(o,nargs,args)
            return args

        curopts=options.cli_parser()
        for a in [ x for x in args] :
            if a.startswith('-'):
                if a == '--':
                    break
                #log.info("  arg: "+a)
                if a.startswith('--'):
                    args=handle_option(a,args)
                else:
                    for o in a[1:]:
                        args=handle_option('-'+o,args)

    args=handle_features(features,args)
    if targetopts.has_option("--buildruntime"):
        log.info("  passing buildruntime "+build_cfg.runtime())
        tmp=["--buildruntime", build_cfg.runtime() ]
        tmp.extend(args)
        args=tmp
    else:
        log.info("  using legacy mode to detect build runtime in selected xmake version")

    if '--xmake-version' not in args and '-X' not in args and build_cfg.xmake_version():
        if '--' in args:
            indexOfDashDash = args.index('--')
            args.insert(indexOfDashDash, build_cfg.xmake_version())
            args.insert(indexOfDashDash, '--xmake-version')
        else:
            args.extend(['--xmake-version', build_cfg.xmake_version()])

    log.info("effective args: "+str(args))
    return args



###################################################
# explicit compatibility handling
###################################################

#
# The bootstrapper must always be up to date with the feature state to be able to handle older xmake versions
# correctly.
# THis part here checks whether the actually xmake version intended to be used, uses more features than expected
# by the actual bootstrapper version.
# If this is the case, the bootstrapper is potentially not able to handle command line given for the newer xmake version.
# Or it cannot strip doen such command lines to be usable for an older xmake version.

def inconsistent(msg):
    log.warning(msg,log.INFRA)
    log.warning("!!!!!!!!!! Please update the bootstrapper to an appropriate version",log.INFRA)
    log.warning("!!!!!!!!!! At least the used xmake version should be required. If this does not prevent this",log.INFRA)
    log.warning("!!!!!!!!!! message, there is an inconsistency between the features supported by xmake and their handling",log.INFRA)
    log.warning("!!!!!!!!!! in the bootstrapper part of the same xmake version",log.INFRA)


###################################################
# strip down the usage of extended repository notation format if used together with an older
# xmake version

def check_initial_feature(feature,state):
    #log.info("  checking consistency of "+feature)
    if state is not "initial":
        inconsistent("unexpected feature state for "+feature+": "+state)

def check_repotypes(feature,state):
    return check_initial_feature(feature,state)

def cleanup_repotypes(feature,state,args):
    '''
    Remove all repository arguments with qualified repository types
    '''
    def match(v):
        ix=v[0].find('=')
        return ix>=0
    if state is None:
        args=remove_dedicated_arg("--import-repo",1,match,args)
        args=remove_dedicated_arg("--export-repo",1,match,args)
        args=remove_dedicated_arg("--deploy-credentials-key",1,match,args)
        args=remove_dedicated_arg("--deploy-user",1,match,args)
        args=remove_dedicated_arg("--deploy-password",1,match,args)
        args=remove_dedicated_arg("-I",1,match,args)
        args=remove_dedicated_arg("-E",1,match,args)
        args=remove_dedicated_arg("-U",1,match,args)
        args=remove_dedicated_arg("-P",1,match,args)
    return args


###################################################
# docker access allows root access to complete filesystem
# therefore an xmake version must restrict itself to standard docker scenarios
# if the requested version does not support this, the build execution must be rejected

def forbid_docker(feature,state,args):
    '''
    If docker is available on this host,only docker aware xmake versions may be used
    '''
    if utils.which('docker') is not None:
        raise XmakeException("non-docker-aware xmake versions may not be used on this host")
    return args

###################################################

feature_handling={
   options.F_REPOTYPES: [ check_repotypes, cleanup_repotypes ],
   options.F_DOCKER:    [ check_initial_feature, forbid_docker ]
}

def get_feature_state(f,features):
    if f in features:
        s=features[f]
        if s is None: s="initial"
    else:
        s=None
    return s

def check_consistency(features):
    '''
    Check whether the used xmake version uses features unknown to the actual boot strapper version.
    In This case the bootstrapper should urgently be updated to be sure to handle those features
    correctly.
    '''
    known=set(feature_handling.keys())
    found=set(features.keys())

    for f in known:
        if f in found: found.remove(f)
    if len(found)>0:
        inconsistent("the selected xmake version uses features unknown to the actual bootstrapper version: "+
                            str([x for x in found]))
    else:
        for f in feature_handling.keys():
            func=feature_handling[f][0]
            if func is not None and features.has_key(f):
                func(f,get_feature_state(f,features))

def handle_features(features,args):
    '''
    handle features whose state differs from the one known by the bootstrapper
    assuming that the command line is expected to follow the contract supported by the bootstrapper version
    '''
    check_consistency(features)
    for f in feature_handling.keys():
        func=feature_handling[f][1]
        if not options.features.has_key(f):
            raise XmakeException("inconsistency between local feature set and feature handling implementation ("+f+")")
        if not features.has_key(f) or features[f]!=options.features[f]:
            log.info("  adapting command line feature "+f+": "+str(get_feature_state(f,features)))
            args=func(f,get_feature_state(f,features),args)
    return args


###################################################
# bootstrapper update
###################################################
def select_bootstrapper(f,argv):
    parser = OptionParser()
    parser.add_option( '--select-bootstrapper', dest="boot", action='store_true', help="the bootstrapper version to use")
    (values,args)=parser.parse_args(argv[1:],Bunch(boot=False))
    if not values.boot:
        raise XmakeException("inconsistent use of bootstrapper option")

    if len(args) == 0:
        "check and notify about the actually configured bootstrapper"
        if isfile(f):
            log.info("determining bootstrapper")
            v=get_first_line(f,'cannot read '+f)
            if v!=None:
                log.info("actual bootstrapper version is "+v)
            else:
                log.info("no bootstrapper version configured in "+f)
        else:
            log.info("no bootstrapper version configured")
    else:
        "set or change the bootstrapper version to use"
        if len(args)!=1:
            raise XmakeException("only one version argument possible")
        (v,_)=load_latest(args[0])
        with open(f,"w") as b:
            b.write(v+"\n")
            log.info("setting bootstrapper to version "+v)


###################################################
# boot strapper main function
###################################################


xmake_status='installed'
build_cfg=None

def main(argv=sys.argv):
    try:
        bootstrap(argv)
    except SystemExit:
        raise
    except BaseException as ex:
        log.error(str(ex), log.INFRA)
        log.exception(ex)
        sys.exit(1)

def prepare_bootstrap():
    global XMAKE_PKG_NEXUS, XMAKE_PKG_REPO
    if os.environ.has_key("XMAKE_NEXUS_HOST"):
        XMAKE_PKG_NEXUS=os.environ.get("XMAKE_NEXUS_HOST")
    if os.environ.has_key("XMAKE_NEXUS_REPO"): XMAKE_PKG_REPO = os.environ.get("XMAKE_NEXUS_REPO")

def handle_bootstrapper(xmake_inst_dir,argv):
    f=join(xmake_inst_dir,'BOOTSTRAPPER_VERSION')
    #log.info("looking for "+f)
    if len(argv)>1 and argv[1]=='--select-bootstrapper':
        select_bootstrapper(f,argv)
        sys.exit(0)

    if isfile(f):
        log.info("determining bootstrapper")
        v=get_first_line(f,'cannot read '+f)
        if v!=None:
            (v,l)=load_latest(v)
            if (l!=None):
                cmd=[sys.executable, join(l,'xmake','bootstrap.py'),'--bootstrap']
                cmd.extend(argv[1:])
                flush()
                rc=subprocess.call(cmd)
                sys.exit(rc)

def bootstrap(argv=sys.argv):
    prepare_bootstrap()
    xmake_inst_dir = inst.get_installation_dir()
    v=inst.get_logical_xmake_version()
    if v != None:
        log.info( 'logical version is '+str(v))
    v=inst.get_technical_xmake_version()
    if v != None:
        log.info( 'technical version is '+v)
    log.info( 'python version is '+str(sys.version_info[0])+"."+str(sys.version_info[1])+"."+str(sys.version_info[2]))
    if not (sys.version_info[0]==2 and sys.version_info[1]>=7):
        log.error( "python version 2.7+ required to run xmake")
        sys.exit(2)
    handle_bootstrapper(xmake_inst_dir,argv)
    bootstrap2(argv)

def determine_xmake_version(build_cfg):
    log.info( 'determining required xmake version...')
    v=build_cfg.xmake_version()
    vf=join(build_cfg.cfg_dir(),XMAKE_VERSION)
    if not is_existing_directory(build_cfg.cfg_dir()):
        vf=join(build_cfg.component_dir(),"."+XMAKE_VERSION)
    if v is None and isfile(vf):
        v=get_first_line(vf,'cannot read '+XMAKE_VERSION)
    if v is None:
        config=build_cfg.xmake_cfg()
        if config is not None:
            s='xmake'
            if (config.has_section(s)):
                if config.has_option(s, "xmake-version"):
                    v=config.get(s,'xmake-version')
    build_cfg._xmake_version=v
    return v

def bootstrap2(argv):
    global xmake_status, build_cfg
    prepare_bootstrap()
    xmake_inst_dir = inst.get_installation_dir()
    if len(argv)>1 and argv[1]=='--bootstrap':
        xmake_status='bootstrap'
        sys.argv=argv=argv[0:1]+argv[2:]
    else:
        if isfile(join(xmake_inst_dir,'.loaded')):
            log.warning( 'directly using loaded sub level version of xmake')
            xmake_status='loaded'

    if xmake_status=='loaded':
        run(argv)
    else:
        log.info( 'bootstrapping xmake...')
        build_cfg = BuildConfig()
        (args,_,_) = setup_config(build_cfg, True)
        log.info("component root is "+build_cfg.component_dir())
        log.info( 'build runtime is ' + build_cfg.runtime())
        create_gendir(build_cfg)
        log.start_logfile(join(build_cfg.genroot_dir(),"boot.log"))
        determine_version_suffix(build_cfg, args.version) # required by xmake version check below

        if args.use_current_xmake_version:
            log.warning( 'using actually installed version as requested by option --use-current-xmake-version')
            run(argv)
        else:
            v=determine_xmake_version(build_cfg)
            if v==None:
                log.warning( 'no xmake version specified (please maintain file '+XMAKE_VERSION+" or xmake.cfg in project's cfg folder")
                log.info("default version is "+str(args.default_xmake_version))
                if args.default_xmake_version==None:
                    if build_cfg.is_release() or build_cfg.is_milestone():
                        raise XmakeException('no version specified for xmake for a productive build')
                    else:
                        log.warning( 'using actually installed version')
                        run(argv)
                else:
                    v=args.default_xmake_version
                    log.warning( 'using explicit default version '+v)
            if v==None:
                log.error("do not know any xmake version to use -> exit")
                sys.exit(2)
            else:
                v=find_latest(v)
                log.info( 'required xmake version is '+v)
                if v.endswith("-SNAPSHOT"):
                    if build_cfg.is_release() or build_cfg.is_milestone():
                        log.info("version suffix is "+str(build_cfg.version_suffix()))
                        log.error( 'this is a snapshot version, it cannot be used for release or milestone builds')
                        raise XmakeException('snapshot version specified for xmake for a realease or milestone build')
                    else:
                        log.warning( 'this is a snapshot version, it cannot be used for release builds')
                l=get_xmake_version(v, build_cfg)
                if is_existing_file(xmake_loaded): os.remove(xmake_loaded)
                log.info( 'required xmake version found at '+l)
                if test_mode:
                    cmd=[sys.executable, join(l,'xmake','bootstrap.py'), '--use-current-xmake-version']
                else:
                    cmd=[sys.executable, join(l,'xmake','xmake.py')]
                log.info( 'starting xmake...')
                cmd.extend(prepare_args(build_cfg, l,argv[1:]))
                if build_cfg.component_dir()!=None: os.chdir(build_cfg.component_dir())
                flush()
                log.stop_logfile()
                rc=subprocess.call(cmd)
                sys.exit(rc)


def run(argv):
    log.stop_logfile()
    print 'INFO: running xmake...'
    if test_mode:
        build_cfg = BuildConfig()
        setup_config(build_cfg, True)
    else:
        xmake.main(argv)
    sys.exit(0)

if __name__ == '__main__':
    main(sys.argv)
