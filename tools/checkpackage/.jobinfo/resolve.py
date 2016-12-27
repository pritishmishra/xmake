import sys

def log( text, stdErrAlso=False ):
    logFile.write( text + '\n' )
    if stdErrAlso:
        sys.stderr.write( text + '\n' )


def parse( file, treeish, testSpec ):
    log( "\n------------------------------" )
    log( "file:"+file )
    log( "treeish:"+treeish )
    log( "testSpec:"+testSpec )
    log( "------------------------------" )
    resultCommits = []
    for line in open(file).readlines():
        arr = line.split('\t')
        commitId = arr[0].strip()
        revSpec = arr[1].strip()
        log( "'"+commitId+"' : '"+revSpec+"'" )
        if commitId.startswith(treeish):
            log( "    TREEISH MATCHES!" )
            if not (commitId in resultCommits):
                resultCommits.append(commitId)
        if revSpec == testSpec:
            log( "    TEST SPEC MATCHES!" )
            if not (commitId in resultCommits):
                resultCommits.append(commitId)
    return resultCommits


def getHeadTestSpec( treeish ):
    return treeish if treeish.startswith('refs/') else 'refs/heads/' + treeish 


def getTagTestSpec( treeish ):
    if treeish.startswith('refs/'):
        if treeish.endswith('^{}'):
            return treeish[:-3]
        else:
            return treeish
    else:
        if treeish.endswith('^{}'):
            return 'refs/tags/' + treeish[:-3]
        else:
            return 'refs/tags/' + treeish


def getFixedAnnotatedTagTestSpec( treeish ):
    if treeish.startswith('refs/'):
        if treeish.endswith('^{}'):
            return treeish
        else:
            return treeish + '^{}'
    else:
        if treeish.endswith('^{}'):
            return 'refs/tags/' + treeish
        else:
            return 'refs/tags/' + treeish + '^{}'


def getExpectedCommit ( headCommits, tagCommits, resolvedTagCommits ):
    if len(headCommits) == 1:
        return headCommits[0]
    if len(headCommits) > 1:
        raise StandardError('More than one matching head commits: ' + str(headCommits))
    if len(tagCommits) == 1:
        if len(resolvedTagCommits) == 1  and resolvedTagCommits[0] != tagCommits[0]:
            return resolvedTagCommits[0]
        else:
            return tagCommits[0]
    if len(tagCommits) > 1:
        raise StandardError('More than one matching tag commits: ' + str(tagCommits))
    return None


def resolve( treeish, headsFile, tagsFile, onlyTags ):
    headCommits = [] if onlyTags else parse(headsFile, treeish, getHeadTestSpec(treeish) )
    tagCommits = parse(tagsFile, treeish, getTagTestSpec(treeish) )
    resAnnoTagCommits = parse(tagsFile, treeish, getFixedAnnotatedTagTestSpec(treeish) )
    if not onlyTags:
      log( "\nMatching Head Commits: " + str(headCommits) )
    log( "Matching Tag Commits : " + str(tagCommits) )
    log( "Matching (resolved) Tag Commits : " + str(resAnnoTagCommits) )
    return getExpectedCommit( headCommits, tagCommits, resAnnoTagCommits)


treeish = sys.argv[1]
headsFile = sys.argv[2]
tagsFile = sys.argv[3]
logFilePath = sys.argv[4]
logFile = open(logFilePath, "w")
onlyTags = len(sys.argv) > 5 and sys.argv[5] in ['True', 'true', '1']
log( "Checking " + ("branches and " if not onlyTags else "") + "tags for '" + str(treeish) + "' (Log file: " + logFilePath +")" , True )
commitId = resolve( treeish, headsFile, tagsFile, onlyTags )
log( "Identified CommitId: " + str(commitId), True )
if onlyTags:
  effectiveCommitId = "" if commitId is None else commitId
else:
  effectiveCommitId = treeish if commitId is None else commitId
log( "Effective CommitId: " + str(effectiveCommitId), True )
sys.stdout.write(effectiveCommitId)

