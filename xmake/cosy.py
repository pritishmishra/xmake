'''
Created on 09.09.2014

@author: d021770
'''

import xml.etree.ElementTree as ET
from xmake_exceptions import XmakeException

namespaces={ "cosy": "urn:xml.sap.com:ArtifactRepository:ArtifactVariants:CoordinateSystem" }

class CoSy(object):
    def __init__(self,f):
        self._root=ET.parse(f)
        #for elem in self._root.getiterator():
        #    print elem.tag, elem.attrib
        self._dimensions=self._get_dimensions()
        
    def _get_dimensions(self):
        return [ x.get('name') for x in self._root.findall('.//cosy:dimension',namespaces)]
    def get_dimensions(self):
        return self._dimensions
    
    def get_dimension(self,d):
        if not d in self._dimensions:
            raise XmakeException('invalid dimension '+d)
        return [ x.get('name') for x in self._root.findall(".//cosy:dimension[@name='"+d+"']/cosy:value", namespaces)]
    
    def variant_coord_vector(self,coords):
        def coord(c):
            if coords.has_key(c): return coords[c]
            raise XmakeException("missing coordinate "+c)
        
        return [ coord(x) for x in self._dimensions ]
    
    def check_coords(self, coords):
        for c in self._dimensions:
            if coords.has_key(c):
                if not coords[c] in self.get_dimension(c):
                    raise XmakeException("invalid value '"+coords[c]+"' for variant dimension '"+c+"'")
            else:
                raise XmakeException("missing value for variant dimension '"+c+"'")
        for c in coords.keys():
            if not c in self._dimensions:
                raise XmakeException("invalid variant dimension '"+c+"'")
 
