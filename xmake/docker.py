'''
Created on 24.03.2015

@author: D021770
'''

'''
Created on 24.03.2015

@author: D021770
'''
import os
import tarfile
import tempfile
import shutil
import json
import base64

import utils
import log
from xmake_exceptions import XmakeException

def get_layers_from_dir(d):
    layers=dict();
    root=[None]
    def gather(d,n):
        with open(os.path.join(d,n,'json'),"r") as j:
            pkg=json.load(j)
            if 'parent' in pkg:
                layers[n]=pkg["parent"]
            else:
                root[0]=n
    utils.handle_dir_entries(d, gather)
    return (root[0],layers)
    
def get_layers(ifile):
    
    def json_files(members):
        for tarinfo in members:
            (head,name)=os.path.split(tarinfo.name)
            if name == "json" and head != 'repository':
                yield tarinfo

    d=tempfile.mkdtemp(prefix=os.path.basename(ifile))
    tar = tarfile.open(ifile)
    try:
        tar.extractall(path=d, members=json_files(tar))
        tar.close()
        return get_layers_from_dir(d)
    finally:
        shutil.rmtree(d, True)
        
def get_image_id(ifile):
    (root,layers)=get_layers(ifile)
    return _get_image_id(layers)

def _get_image_id(layers):
    keys=set(layers.keys())
    for k in layers.keys():
        if layers[k] in keys: keys.remove(layers[k])
    if len(keys)!=1:
        return None
    return keys.pop()
    
def get_base(ifile):
    
    def base_file(members):
        for tarinfo in members:
            if tarinfo.name == "base":
                yield tarinfo

    d=tempfile.mkdtemp(prefix=os.path.basename(ifile))
    tar = tarfile.open(ifile)
    try:
        tar.extractall(path=d, members=base_file(tar))
        tar.close()
        p=os.path.join(d,"base")
        return utils.get_first_line(p, "cannot read base file") if utils.is_existing_file(p) else None
    finally:
        shutil.rmtree(d, True)
        
def load_image(ifile,echo=True):
    base=get_base(ifile)
    if base is not None:
        docker(["pull",base],echo=echo)
    docker(["load","-i",ifile],echo=echo)
        
def delete_env(env,key):
    if env.has_key(key): del env[key]
    
def docker(args,handler=None,dir=None,echo=True,home=None):
    tmp = [ 'docker' ]
            
    tmp.extend(args)
    env=dict(os.environ)
    delete_env(env,"HTTPS_PROXY")
    delete_env(env,"HTTP_PROXY")
    delete_env(env,"https_proxy")
    delete_env(env,"http_proxy")
    if home is not None: env["HOME"]=home
    if echo: log.info("running "+str(tmp))
    rc=log.log_execute(tmp,handler,env=env,cwd=dir)
    if rc > 0: 
        if not echo: log.error("failed docker command: "+str(tmp))
        raise XmakeException('ERR: docker returned %s' % str(rc))

def strip_image(ifile,base,ofile):
    d=tempfile.mkdtemp(prefix=os.path.basename(ifile))
    try:
        tar = tarfile.open(ifile)
        tar.extractall(path=d)
        tar.close()
        (root,layers)=get_layers_from_dir(d)
        id=_get_image_id(layers)
        delete=False
        while id != None:
            delete|=id.startswith(base)
            if delete:
                shutil.rmtree(os.path.join(d,id))
            
            id=layers[id] if layers.has_key(id) else None
        with open(os.path.join(d,"base"),"w") as f:
            f.write(base+"\n")
        tar = tarfile.open(ofile, "w:gz")
        def store(d,n):
            tar.add(os.path.join(d,n),arcname=n)
        utils.handle_dir_entries(d, store)
        tar.close()
    finally:
        shutil.rmtree(d, True)

def prepare_dockercfg(user, password, host):
        auth=base64.b64encode(user+":"+password)
        tmpdir=tempfile.mkdtemp("docker", "cfg")
        tmp=os.path.join(tmpdir,".dockercfg")
        if host == "index.docker.io": host="https://index.docker.io/v1/"
        with open(tmp,'w') as f:
            f.write("{\n")
            f.write("  \""+host+"\": {\n")
            f.write("    \"auth\": \""+auth+"\",\n")
            f.write("    \"email\": \"xmake@sap.com\"\n")
            f.write("  }\n")
            f.write("}\n")
        return tmpdir
    
def normalize_tag(name):
        name=name.lower()
        name=name.replace('.', '-')
        return name

def tag_image(image,tag,force=False):    
        log.info("setting tag "+tag)
        opt=['-f'] if force else None
        cmd=["tag"]
        if opt is not None:
            cmd.extend(opt)
        cmd.extend([image, tag])
        docker(cmd)
             
def _get_command(js=None, s=None):
    if s is not None:
        js=json.loads(s)
    if js[0].has_key("Config") and js[0]["Config"].has_key("Cmd"):
            return '['+ ','.join([ '"'+str(s)+'"' for s in js[0]["Config"]["Cmd"]])+']'
    else:
        return None

def get_command(image):
    out=[]
    def get(line):
        out.append(line)
    docker(["inspect",image], handler=get)
    return _get_command(s="\n".join(out))

###########################################################
# build config based operations
###########################################################
from config import DOCKERREPO

def repo_host(build_cfg):
        repo=build_cfg.export_repo(DOCKERREPO)
        if repo is not None:
            if repo.startswith("https://"):
                repo=repo[8:]
            else:
                if repo.startswith("http://"):
                    repo=repo[7:]
        return repo
    
def tag_name(build_cfg,gid,aid,tmp=False):
        if (build_cfg.is_release() or build_cfg.is_milestone()) and not tmp:
            tag=normalize_tag(gid+'/'+aid)+':'+build_cfg.version()
        else:
            if build_cfg.version_suffix() is None:
                tag=gid+'/'+aid+"-"+'TMP'
            else:
                tag=gid+'/'+aid+"-"+build_cfg.version_suffix()
            tag=normalize_tag(tag)
        if not tmp:
            repo=repo_host(build_cfg)
            tag=repo+"/"+tag
        return tag
      
            
###########################################################
def print_image(ifile):
    (root,layers)=get_layers(ifile)
    id=_get_image_id(layers)
    print 'Image:',id
    while id != None:
        print '  ',id
        id=layers[id] if layers.has_key(id) else None
        
    print 'Root:',root
    
if __name__ == '__main__':
    #ifile=os.path.join('..','..','gen','image.tar.gz')
    #ofile=os.path.join('..','..','gen','delta.tar.gz')
    #print_image(ifile)
    #strip_image(ifile,'f3c84ac3a0533f691c9fea4cc2c',ofile)
    ifile=os.path.join('..','..','tmp','inspect.json')
    with open(ifile,"r") as j:
        pkg=json.load(j)
        print _get_command(js=pkg)
           
