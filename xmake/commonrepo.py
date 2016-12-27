'''
Created on 24.11.2014

@author: D021770
'''

import log

from os.path import join
from xmake_exceptions import XmakeException
from utils import is_existing_file, append_file_unique, stripToBlank

def validate_import_repo(repo):
        #urls must never contain whitespace and never start with -
        repo = repo.strip().replace('\t', ' ').replace('\n', ' ').replace('\r',' ')
        if ' ' in repo: raise XmakeException('invalid repository URL: no whitespace allowed: ' + repo)
        if repo.startswith('-'): raise XmakeException('invalid repository URL: must not start with hyphen character (-): ' + repo)
        return repo

def prepare_ai_command(build_cfg,roots, repos, suffix):
    ai_args = ['deploy', '--write-artifact-list', build_cfg.import_file(suffix)]
    for (name,path) in roots.items(): ai_args.extend(['-C', 'root.'+name+'='+path])
    for repo in repos: ai_args.extend(['--repo-url', validate_import_repo(repo)])
    ai_args.extend(['-DbuildRuntime=' + build_cfg.runtime()])
    ai_args.extend(['-DbuildBaseVersion=' + build_cfg.base_version()])
    ai_args.extend(['-DbuildVersion=' + build_cfg.version()])
    ai_args.extend(['-DbuildVersionSuffix=' + stripToBlank(build_cfg.version_suffix())])
    return ai_args
    
    
def create_import_script(build_cfg, name, imports):
    def root_imports(import_root):
        return '''
targetRootDir id:"%s",{
%s
}
''' % (import_root, '\n'.join(['artifactFile "%s"' % (gavstr) for gavstr in imports[import_root]]))
   
    mapping_script='''
    
imports dslVersion:"1.2", {
%s
}
''' % '\n'.join(map(root_imports,imports.keys()))
    #write file
    import_file=join(build_cfg.genroot_dir(), name)
    with open(import_file, 'w') as f:
        f.write(mapping_script)
    return import_file

def execute_ai(build_cfg, ai_args, script, prefix):
    ai=[build_cfg.tools().artifact_importer()]
    ai.extend(ai_args)
    ai.extend(["--temp-dir", build_cfg.temp_dir()])
    ai.extend(['-f',script])
    log.info('importing '+prefix)
    log.info( 'calling '+' '.join(ai))
    rc = log.log_execute(ai)

    log.info( prefix+"import resulted in RC==" + str(rc))
    if rc !=0:
        log.info( "import returned w/ RC==" + str(rc))
        log.error( "importer returned RC != 0 (see log output for further hints)")
        raise XmakeException(prefix+"import failed")
    log.info( prefix+"import finished successfully")
    
def assert_import_file(build_cfg):
    ifile=build_cfg.import_file()
    if not is_existing_file(ifile):
        with open(build_cfg.import_file(),"w"): pass

def update_import_file(build_cfg, suffix):
    append_file_unique(build_cfg.import_file(),build_cfg.import_file(suffix))
    
def append_import_file(build_cfg, imports): 
    # Open the import file in append mode & add only non existing GAVs in the case of running multiple times xmake -i with cache already filled without cleaning the gen dir   84 
    with open(build_cfg.import_file(), 'a+t') as infile:
        gavs=set()
        for line in infile:
            line=str.rstrip(line)
            gavs.add(line)
        for gavstr in imports:
            if not gavstr in gavs: infile.write(gavstr+"\n")
              

    