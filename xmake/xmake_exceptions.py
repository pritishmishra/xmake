'''
Created on 30.12.2013

@author: D051236
'''

class XmakeException(Exception):
    def __init__(self, msg):
        super(Exception).__init__(type(self))
        self.msg = "xmake ERROR: %s" % msg
    def __str__(self):
        return self.msg
    def __unicode__(self):
        return self.msg