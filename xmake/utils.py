'''
Created on 24.12.2013

@author: Christian Cwienk (d051236)
'''

import ConfigParser

import os
import platform
import sys
import inspect
import zipfile
import tarfile
import shutil
import stat
import log
from distutils.errors import DistutilsError
from xmake_exceptions import XmakeException
from os.path import dirname, realpath, join, isfile

class Bunch:
    def __init__(self, **kwds):
        self.__dict__.update(kwds)

ConfigParser.ConfigParser.optionxform = str  # make the configuration case sensitive
class IterableAwareCfgParser(ConfigParser.ConfigParser):
    '''a ConfigParser impl that is capable of (heuristically) restoring iterables that were previously stored

    parsing is based on the assumption that iterable types are automatically stored in the following format:
      ['value0', 'value1', ..]
    Note that this assumption may lead to situations where values are erroneously interpreted as iterables.
    Also, nested iterables are not supported.
    '''
    def get(self, section, option):
        raw = ConfigParser.ConfigParser.get(self, section, option)
        if raw is None or not isinstance(raw, basestring): return raw
        raws = raw.strip()
        if len(raws) < 2 or not raws[-1] == ']' or not raws[0] == '[': return raw
        raws = raws [1:-1] # strip enclosing []
        return [x.strip()[1:-1] if x.strip().startswith("'") else x.strip() for x in raws.split(',')]

class UnrecognizedFormat(DistutilsError):
    """Couldn't recognize the archive type"""

def default_filter(src,dst):
    """The default progress/filter callback; returns True for all files"""
    return dst

def ensure_directory(path):
    """Ensure that the parent directory of `path` exists"""
    dirname = os.path.dirname(path)
    if not os.path.isdir(dirname):
        os.makedirs(dirname)

def unpack_zipfile(filename, extract_dir, progress_filter=default_filter):
    """Unpack zip `filename` to `extract_dir`

    Raises ``UnrecognizedFormat`` if `filename` is not a zipfile (as determined
    by ``zipfile.is_zipfile()``).  See ``unpack_archive()`` for an explanation
    of the `progress_filter` argument.
    """

    if not zipfile.is_zipfile(filename):
        raise UnrecognizedFormat("%s is not a zip file" % (filename,))

    z = zipfile.ZipFile(filename)
    try:
        for info in z.infolist():
            name = info.filename

            # don't extract absolute paths or ones with .. in them
            if name.startswith('/') or '..' in name:
                continue

            target = os.path.join(extract_dir, *name.split('/'))
            target = progress_filter(name, target)
            if not target:
                continue
            if name.endswith('/'):
                # directory
                ensure_directory(target)
            else:
                # file
                ensure_directory(target)
                data = z.read(info.filename)
                f = open(target,'wb')
                try:
                    f.write(data)
                finally:
                    f.close()
                    del data
            unix_attributes = info.external_attr >> 16
            if unix_attributes:
                os.chmod(target, unix_attributes)
    finally:
        z.close()


def restore_mapping(m,d):
    for (k,v) in d.items():
        if not m.has_key(k) or m[k]!=v: m[k]=v
    for k in m.keys():
        if not d.has_key(k): del m[k]

def isBlank(str):
    return str is None or len(str.strip())==0

def stripToBlank(str):
    if str is None or len(str)==0:
        return ''
    return str.strip()

def contains(l,e):
    try:
        return l.index(e)
    except ValueError:
        return -1

def cat(n):
    with open(n) as f:
        print f.read()

def get_first_line(file_object, err, mode='r'):
    with open (file_object, mode) as f:
        return read_first_line(f,err)

def read_first_line(f,err):
        lines = f.readlines()
        lines = filter(lambda(x): not ( x.strip().startswith('#') or len(x.strip())==0), lines)
        if not len(lines) > 0: raise XmakeException(err)
        return lines[0].strip()

def touch_file(path):
    if os.path.isdir(path):
        os.utime(path,None)
    else:
        with open(path,"w+"): os.utime(path, None)

def validate_path(path,relative=True):
    if path is None: return path
    path=path.replace('/', os.path.sep)
    if relative and os.path.isabs(path):
        raise XmakeException('only relative paths allowed for relative archive paths')
    return path

def append_file(target, source):
    with open(target, 'a') as outfile:
        with open(source) as infile:
            for line in infile:
                outfile.write(line)

def append_file_unique(target, source):
    s=set()
    o=set()
    with open(target) as infile:
            for line in infile:
                o.add(line)
    with open(source) as infile:
            for line in infile:
                s.add(line)
    s-=o
    with open(target, 'a') as outfile:
        for line in s:
            outfile.write(line)


def mkdirs(f):
    if (not is_existing_directory(f)): os.makedirs(f)

def rmtree(d):
    if (is_existing_directory(d)):
        def onerror(func, path, exc_info):
            if not os.access(path, os.W_OK):
                os.chmod(path, stat.S_IWUSR)
                func(path)
            else:
                raise
        shutil.rmtree(d, onerror=onerror)
    else:
        if is_existing_file(d):
            raise IOError(str(d)+" is no directory")

def expandArchive(p,d):
    try:
        mkdirs(d)
        if tarfile.is_tarfile(p):
            with tarfile.TarFile.open(p,'r') as tar:
                tar.extractall(d)
        else:
#             z=zipfile.ZipFile(p)
#             mkdirs(d)
#             z.extractall(d)
            unpack_zipfile(p, d)
        return d
    except:
        log.error( "cannot expand archive "+p+": "+str(sys.exc_info()[0]),log.INFRA)
        rmtree(d)
        raise

def is_existing_file(file_or_none): return True if file_or_none is not None and os.path.isfile(file_or_none) else False
def is_existing_directory(dir_or_none): return True if dir_or_none is not None and os.path.isdir(dir_or_none) else False

def handle_dir_entries(d,h):
    names = os.listdir(d)
    if names is not None:
        for name in names:
            h(d,name)

def which(program):
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    def ext_candidates(fpath):
        yield fpath
        for ext in os.environ.get("PATHEXT", "").split(os.pathsep):
            yield fpath + ext

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            for candidate in ext_candidates(exe_file):
                if is_exe(candidate):
                    return candidate

    return None

def is_method_or_function(obj, argc=0):
    return callable(obj) and len(inspect.getargspec(obj)[0]) == argc+1 if inspect.isclass(type(obj)) else argc

def has_method(class_instance, method_name, formal_param_count = 0):
    '''returns a boolean value indicating whether or not the given class instance has a method with the given name
    and the given amount of formal parameters. Note that the first argument (reference to 'self') is not included.
    A method 'a.someMethod(self)' has a formal_param_count of 0 in the sense of this function'''
    return hasattr(class_instance, method_name) and callable(getattr(class_instance,method_name)) and len(inspect.getargspec(getattr(class_instance,method_name))[0]) == formal_param_count + 1


def flush():
    sys.stdout.flush()
    sys.stderr.flush()

_platform_mapping={'linux2':'linux'}
_system_mapping={}
_machine_mapping={}
_runtime_mapping={'linux_x86_64':'linuxx86_64',
                  'windows_amd64':'ntamd64',
                  'darwin_x86_64':'darwinintel64',
                  'linux_ppc64':'linuxppc64',
                  'linux_ppc64le':'linuxppc64le',
                  'sunos_sun4v':'sun_64',
                  'sunos_i86pc':'sunx86_64',
                  'hp-ux_ia64':'hpia64',
                  'aix_6_1':'rs6000_64',
                  'linux_s390x':'linuxs390x',
                  'linux_i686':'linuxintel',
                  'windows_x86':'ntintel',
                  'aix_5_2':'rs6000_52_64',
                  'sunos_sun4us':'sun_64_solaris9'}
_bit_mapping={'linuxx86_64': 64,
              'ntamd64': 64,
              'darwinintel64': 64,
              'linuxppc64': 64,
              'linuxppc64le': 64,
              'sun_64': 64,
              'sunx86_64': 64,
              'hpia64': 64,
              'rs6000_64': 64,
              'linuxs390x': 32,
              'linuxintel': 32,
              'ntintel':32,
              'rs6000_52_64': 64,
              'sun_64_solaris9': 64}
_runtime=None

def _map(v,m):
    if m.has_key(v): return m[v]
    else: return v

def runtime():
    global _runtime
    if _runtime == None:
        pf=_map(sys.platform,_platform_mapping)
        sy=_map(platform.system(),_system_mapping)
        if sy.lower()=='aix':
            ma=platform.version()+"_"+platform.release()
        else:
            ma=_map(platform.machine(),_machine_mapping)
        _runtime=_map((sy+"_"+ma).lower(),_runtime_mapping)
    return _runtime

def runtime_gid(gid,rt=runtime()):
    return gid+"."+rt
def runtime_classifier(c,rt=runtime()):
    return c+"-"+rt if c!= None and len(c)>0 else rt

# gid:aid:type:classifier:version
def runtime_ga(ga,vmode='group', rt=runtime()):
    comp=ga.split(':')
    gid= runtime_gid(comp[0],rt) if vmode=='group' else comp[0]
    aid= comp[1]
    ty= comp[2] if len(comp)>=3 else None
    cf= comp[3] if len(comp)>=4 else None
    cf= runtime_classifier(cf,rt) if vmode=='classifier' else cf
    ga=gid+':'+aid
    if ty!=None or cf!=None: ga=ga+':'+(ty if ty!=None else '')
    if cf!=None: ga=ga+':'+cf
    return ga

##############################

def add_list_entry(d,k,e):
    if d.has_key(k):
        d.get(k).append(e)
    else:
        d[k]=[e]

def get_entry(d,k):
    return d.get(k) if d.has_key(k) else None

def set_single_entry(d,k,e):
    d[k]=e

##############################

def remove_arg(a,n, args):
    def match(v): return True
    return remove_dedicated_arg(a,n,match,args)

def remove_dedicated_arg(a,n,match,args):
    found=True
    while found:
        found=False
        for i in range(len(args)):
            if args[i].startswith('--'):
                if args[i].startswith(a):
                    if args[i]==a:
                        if match(args[i+1:i+n+1]):
                            args=args[:i]+args[i+n+1:]
                            found=True
                            break
                    else:
                        if args[i].startswith(a+"="):
                            if match([args[i][len(a)+1:]]):
                                args=args[:i]+args[i+1:]
                                found=True
                                break
            else: # potential accumulated flag arg
                if args[i].startswith('-') and len(a)==2:
                    if args[i] == a:
                        if match(args[i+1:i+n+1]):
                            args=args[:i]+args[i+n+1:]
                            found=True
                            break
                    else:
                        if n>0 and args[i].startswith(a):
                            if match([args[i][len(a):]]):
                                args=args[:i]+args[i+1:]
                                found=True
                                break
                        else:
                            ix=args[i].find(a[1])
                            if ix>0 and n==0:
                                args[i]=args[i][:ix]+args[i][ix+1:]
                                found=True
                                break
    return args
##############################

def get_bit_count(rt):
    if _bit_mapping.has_key(rt):
        return _bit_mapping[rt]
    return 64

def sys_info():
    print 'RUNTIME:', runtime()
    print 'os.name:', os.name
    print 'platform.uname: ', str(platform.uname())
    print 'system   :', platform.system()
    print 'node     :', platform.node()
    print 'release  :', platform.release()
    print 'version  :', platform.version()
    print 'machine  :', platform.machine()
    print 'processor:', platform.processor()
    print
    print 'sys.platform:', sys.platform
    if sys.platform == 'win32':
        print 'platform.win32_ver:', platform.win32_ver()
    if os.name == 'posix':
        print 'os.uname:',str(os.uname())


if __name__ == '__main__':
    sys_info()
