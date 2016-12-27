'''
Created on 27.03.2015

@author: I050906
'''

from os.path import join

from spi import ArchiveBasedTool


class tool(ArchiveBasedTool):
    def _import(self):
        return 'org.apache.maven:apache-maven:zip:bin'
    def _map_installation(self,d,version):
        return join(d,'apache-maven-'+version)