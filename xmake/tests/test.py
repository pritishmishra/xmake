'''
Created on 21.01.2014
'''
import sys
import os

dirname = os.path.dirname(os.path.realpath(__file__))
sys.path.append(dirname+'/../')
sys.path.append(dirname+'/../../externals')

import pep8
import coverage
import unittest
import traceback
from bootstrap import cleanup_repotypes
from utils import remove_arg, remove_dedicated_arg
from utils import runtime, runtime_ga, restore_mapping
from ExternalTools import tool_gav

# checks sources according to the linter rules
pep8style = pep8.StyleGuide({'ignore': (pep8.DEFAULT_IGNORE+',E501').split(','), 'exclude': ('*/tests/*',)}, paths=[dirname+'/../'])
report = pep8style.check_files()
if report.total_errors:
    print '*' * 80
    print '* found {} python code style violation{} (PEP 8)'.format(str(report.total_errors), 's' if report.total_errors>1 else '')
    print '*' * 80
    print '\n'

cov = coverage.Coverage(source=[dirname+'/../'], omit=[dirname+'/*', '*/__init__.py'])
cov.start()

#################################
# Test Exception
#################################

class TestFailed(Exception):
    def __init__(self, *msg):
        super(Exception).__init__(type(self))
        if (msg!=None and len(msg)>0):
            self.msg = "Test failed: "+" ".join([str(x) for x in msg])
        else:
            self._msg="Test failed"
    def __str__(self):
        return self.msg
    def __unicode__(self):
        return self.msg

#################################
# internal state
#################################
class TestState(object):
    def __init__(self,func):
        self._func=func
        self._errors=[]

    def is_ok(self):
        return len(self._errors)==0

    def out(self):
        print 'Test '+self._func.__name__+'('+self._func.__module__+') '+('OK' if self.is_ok() else 'FAILED')
        for e in self._errors:
            print '    ',e

test_funcs=[]
test_states=[]
current_msg=None
current=None

def set_test_error(*msg):
    global current_msg
    current_msg=" ".join([str(x) for x in msg])
    current._errors.append(current_msg)
    print current_msg

#################################
# Test Annotations
#################################

def Test(func):
    test_funcs.append(func)
    return func

def NestedTest(func):
    def catch(*args):
        try:
            func(*args)
        except TestFailed as ex:
            if current_msg==None:
                set_test_error(str(ex))
    return catch

#################################
# assertions
#################################

def assertEquals(msg,exp,res):
    if exp!=res:
        set_test_error(msg,'failed: expected:',exp,'found:',res)
        raise TestFailed(msg,'failed: expected:',exp,'found:',res)

#################################
# main test execution
#################################
def executeTests():
    global current, current_msg
    failed=0
    succeeded=0
    for f in test_funcs:
        print '*** execute', f.__name__+'('+f.__module__+')'
        try:
            current=TestState(f)
            current_msg=None
            test_states.append(current)
            f()
            if current.is_ok():
                succeeded=succeeded+1
            else:
                failed=failed+1
                print '-> test failed by nested tests'
        except TestFailed as ex:
            failed=failed+1
            if current_msg==None:
                set_test_error(str(ex))
        except BaseException as ex:
            print '-> test failed with unexpected exception:',str(ex)
            traceback.print_exc()
            failed=failed+1
            set_test_error('test failed with unexpected exception: '+str(ex))
    print
    print '*' * 80
    print '* test.py'
    print '*' * 80
    for s in test_states:
        s.out()
    if failed>0:
        print str(failed)+" test(s) failed"
        sys.exit(1)

################################################################################
#
# Test Code
#
################################################################################


args=['-a', '-ie', '--d=ef', '--def', '0.8', '-bla']

@NestedTest
def test(title, exp, arg, n):
    global args
    tmp=[ x for x in args ]
    res=remove_arg(arg,n,tmp)
    assertEquals(title,exp,res)
    print title, 'OK'

@Test
def testRemoveArg():
    test('short -i', ['-a', '-e', '--d=ef', '--def', '0.8', '-bla'], '-i',0)
    test('short -e', ['-a', '-i', '--d=ef', '--def', '0.8', '-bla'], '-e',0)
    test('short -a', ['-ie', '--d=ef', '--def', '0.8', '-bl'], '-a',0)
    test("long 1", ['-a', '-ie', '--d=ef', '-bla'],  '--def',1)
    test("concat short 1", ['-a', '-ie', '--d=ef', '--def', '0.8'],  '-b',1)
    test("concat long 1", ['-a', '-ie', '--def', '0.8', '-bla'],  '--d',1)

@NestedTest
def testDedicated(title, exp, arg, n):
    def match(v):
        #print "match",str(v)
        return v[0].find('=')>=0
    args=['-B', '--import-repo', 'NPM=X', '--debug-xmake', '-I', 'NPM=Y', '--export-repo=X=Y', '--import-repo', 'bla', '-EB=C', '-r', '.']
    res=remove_dedicated_arg(arg,n,match,args)
    assertEquals(title,exp,res)
    print title, 'OK'

@Test
def testRemoveRedivated():
    testDedicated('import long', [ '-B', '--debug-xmake', '-I', 'NPM=Y', '--export-repo=X=Y', '--import-repo', 'bla', '-EB=C', '-r', '.' ], '--import-repo', 1)
    testDedicated('export long', ['-B', '--import-repo', 'NPM=X', '--debug-xmake', '-I', 'NPM=Y', '--import-repo', 'bla', '-EB=C', '-r', '.'], '--export-repo', 1)
    testDedicated('import short', ['-B', '--import-repo', 'NPM=X', '--debug-xmake', '--export-repo=X=Y', '--import-repo', 'bla', '-EB=C', '-r', '.'], '-I', 1)
    testDedicated('export short', ['-B', '--import-repo', 'NPM=X', '--debug-xmake', '-I', 'NPM=Y', '--export-repo=X=Y', '--import-repo', 'bla', '-r', '.'], '-E', 1)

@Test
def testcleanup_repo_args():
    args=['-B', '--import-repo', 'NPM=X', '--debug-xmake', '-I', 'NPM=Y', '--export-repo=X=Y', '--import-repo', 'bla', '-EB=C', '-r', '.']
    res=cleanup_repotypes("repo-types",None,args)
    assertEquals("remove types repos",['-B','--debug-xmake', '--import-repo', 'bla', '-r', '.'],res)

@NestedTest
def testRTGA(ga,vmode,rt,res):
    if rt==None:
        assertEquals(ga+'->'+str(rt),res,runtime_ga(ga,vmode))
    else:
        assertEquals(ga+'->'+str(rt),res,runtime_ga(ga,vmode,rt))
    print ga+'->'+str(rt), 'OK'

@Test
def testRuntimeGA():
    rt=runtime()
    testRTGA('gid:aid','group', None, 'gid.'+rt+':aid')
    testRTGA('gid:aid','classifier', None, 'gid:aid::'+rt)
    testRTGA('gid:aid:','classifier', None, 'gid:aid::'+rt)
    testRTGA('gid:aid::','classifier', None, 'gid:aid::'+rt)
    testRTGA('gid:aid:zip','classifier', None, 'gid:aid:zip:'+rt)
    testRTGA('gid:aid:zip:','classifier', None, 'gid:aid:zip:'+rt)
    testRTGA('gid:aid:zip:cl','classifier', None, 'gid:aid:zip:cl'+'-'+rt)
    testRTGA('gid:aid::cl','classifier', None, 'gid:aid::cl'+'-'+rt)
    rt='bla'
    testRTGA('gid:aid','group', rt, 'gid.'+rt+':aid')
    testRTGA('gid:aid','classifier', rt, 'gid:aid::'+rt)
    testRTGA('gid:aid:','classifier', rt, 'gid:aid::'+rt)
    testRTGA('gid:aid::','classifier', rt, 'gid:aid::'+rt)
    testRTGA('gid:aid:zip','classifier', rt, 'gid:aid:zip:'+rt)
    testRTGA('gid:aid:zip:','classifier', rt, 'gid:aid:zip:'+rt)
    testRTGA('gid:aid:zip:cl','classifier', rt, 'gid:aid:zip:cl'+'-'+rt)
    testRTGA('gid:aid::cl','classifier', rt, 'gid:aid::cl'+'-'+rt)

@NestedTest
def testToolGav(gav,res):
    comp=tool_gav(gav)
    assertEquals(gav,res,comp)

@Test
def testToolGAVs():
    testToolGav('com.sap.prd.xmake:xmake:tar.gz:bin:boot-1',['com.sap.prd.xmake','xmake','tar.gz','bin','boot-1'])
    testToolGav('com.sap.prd.xmake:xmake:tar.gz:boot-1',['com.sap.prd.xmake','xmake','tar.gz','','boot-1'])
    testToolGav('com.sap.prd.xmake:xmake:boot-1',['com.sap.prd.xmake','xmake','zip','','boot-1'])


class Bla:
    def __init__(self):
        self._value="bla"

    def get(self):
        return self._value

class Blub:
    def __init__(self):
        self.get=None

@Test
def testFunctionPointer():
    bla=Bla()
    blub=Blub()
    blub.get=bla.get

    assertEquals("fpointer", "bla", blub.get())

@Test
def testRestore():
    orig=dict()
    orig["a"]="a"
    orig["b"]="b"
    orig["c"]="c"

    save=dict(orig)

    orig["b"]="B"
    orig["d"]="D"
    del orig["c"]

    restore_mapping(orig,save)
    assertEquals("mapping", save, orig)

executeTests()

# Discover all test modules
testModuleNames = []
for d in os.walk(dirname):
    currentDir = d[0].replace(dirname, '').replace(os.sep, '.')
    currentDir = currentDir[1:] if currentDir.startswith('.') else currentDir
    for f in d[2]:
        if '.pyc' not in f and f!='test_helpers.py' and f != '__init__.py' and '.py' in f:
            if f == 'test.py' and currentDir == '':
                continue
            prefix = ''
            if currentDir != '':
                prefix = currentDir + '.'
            testModuleNames.append('{}{}'.format(prefix, f.replace('.py', '')))

# Build test suites
suites = []
for testModuleName in testModuleNames:
    testModule = __import__(testModuleName, globals(), locals(), ['Test'], -1)
    suites.append({'testcases':unittest.TestLoader().loadTestsFromTestCase(testModule.Test), 'moduleName': testModule.__name__})

suitetestresultfail = False
for suite in suites:
    print '\n'
    print '*' * 80
    print '* ' + suite['moduleName']
    print '*' * 80
    for testcase in suite['testcases']:
        result = unittest.TestResult(verbosity=2)
        testcase.run(result)
        if result.errors:
            print '>', testcase, 'ERROR'
            for (t1, t2) in result.errors:
                print '\t', t1
                print '\t', t2
            suitetestresultfail = True
        elif result.failures:
            print '>', testcase, 'FAILURE'
            for (t1, t2) in result.failures:
                print '\t', t1
                print '\t', t2
            suitetestresultfail = True
        elif result.skipped:
            print '>', testcase, 'SKIPPED'
            for (t1, t2) in result.skipped:
                print '\t', t1
                print '\t', t2
        else:
            print testcase, 'OK'

cov.stop()
cov.save()

if suitetestresultfail:
    print "test(s) failed"
    sys.exit(1)

print '\n'
print '*' * 80
print '* Code coverage'
print '*' * 80
cov.html_report(directory=dirname+'/../../../gen/htmlcov')
cov.report()
