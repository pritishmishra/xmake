'''
Created on 05.09.2014

@author: d021770
'''

import os
import utils
import sys
import tempfile
import log
import shutil
from xmake_exceptions import XmakeException
from os.path import join
from utils import is_existing_directory

class AppCache(object):
    def __init__(self, elem, root, retriever=None, finalizer=None):
        self._elem=elem
        self._root=root
        self._retriever=retriever
        self._finalizer=finalizer
        
    def has(self,aid):
        return is_existing_directory(self.path(aid))
    
    def get(self, aid, retriever=None, msg=None, archive=True):
        if retriever==None: retriever=self._retriever
        return self._install(aid,retriever,msg,archive)

    def root(self):
        return self._root
    
    def _install(self,aid,retrieve,msg=None,archive=True):
        d=self.path(aid)
        if is_existing_directory(d):
            return d
        a=retrieve(aid)
        if a==None: return None
        utils.mkdirs(os.path.dirname(d))
        f=tempfile.mkdtemp(suffix='.'+self._base(aid), dir=self._root)
        try:
            self._notify(aid,d,a,msg)
            if not archive:
                base=os.path.basename(a)
                ix=base.rfind('.')
                suf=base[ix:] if ix>=0 else ''
                if suf=='.gz':
                    base=base[:ix]
                    ix=base.rfind('.')
                    suf=(base[ix:] if ix>=0 else '')+suf
                    
                shutil.copy(a,join(f,'artifact'+suf))
            else:
              utils.expandArchive(a, f)
            if self._finalizer!=None:
                self._finalizer(aid,f)
            err=0
            while not is_existing_directory(d):
                try:
                    os.rename(f,d)
                except OSError:
                    if not is_existing_directory(d):
                        err=err+1
                    else:
                        log.error( 'cannot rename directory '+f+':'+str(sys.exc_info()),log.INFRA)
                        break
            utils.rmtree(f)
            if is_existing_directory(d):
                return d
            log.error( 'no folder '+d,log.INFRA)
            return None
        except:
            log.error( 'cannot expand archive '+a+':'+ str(sys.exc_info()),log.INFRA)
            utils.rmtree(f)
            raise XmakeException('ERR: cannot expand archive '+a+': '+str(sys.exc_info()))
        
    
        
    def _base(self,aid):
        if isinstance(aid, (list, tuple)): return aid[-1]
        return str(aid)
        
    def path(self,aid):
        d=None
        if isinstance(aid, (list, tuple)):
            d=self._root
            for p in aid: d=join(d,p)
            return d
        else:
            d=join(self._root,aid)
        return d

    def _notify(self,aid,d,a,msg=None):
        elem=msg if msg!=None else self._elem
        log.info( 'installing '+elem+' '+str(aid)+' into '+str(d))
        log.info( '  archive is '+a)