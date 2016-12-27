'''
Created on 21.07.2014

@author: D051236
'''

from os.path import join

from spi import ArchiveBasedTool


class tool(ArchiveBasedTool):
    def _import(self):
        return 'org.apache.download.ant:ant:tar.gz:bin'
    def _map_installation(self,d,version):
        return join(d,'apache-ant-'+version)