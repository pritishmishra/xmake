'''
Created on 22.12.2014

@author: D021770
'''
from optparse import OptionParser

#
# Features keys of features relevant for the bootstrapper
#
F_REPOTYPES="repo-types" # xmake version supports multiple repository types
F_DOCKER="docker" # xmake version supports docker and restricts build execution to standard docker use cases

#
# The features attribute allows to specify supported features or feature flavors by assigning a features state to a feature key.
# The bootstrapper is able to read these declarations and control the bootstrapping by adding, modifying or removing of arguments
# passed to the actual xmake version to be used.
#
# This mechanism is intended to provide a possibility to react on incompatible changes.
# Whenever such a change is done, an entry must be made to this feature list. Together with this entry
# there must be a change in the bootstrapper to be able to call older version correctly
#
#!!! This also means, that the bootstrapper version MUST be updated, before the central landscape can be
#!!! switched to the new feature
#
features={ F_REPOTYPES:"initial",
           F_DOCKER:   "initial" }

def cli_parser():
    # Setup argument parser
    parser=base_09_options();
    parser.add_option(       '--base-version', dest='base_version', help="Overwrite base version declared in sources")
    parser.add_option('-O', '--buildplugin-option', dest='options', action='append', help="Build plugin options/settings")
    parser.add_option('-T', '--skip-test', dest='skip_test', action='store_true', help="skip the execution of the build plugin's test step")
    parser.add_option("-F", "--forwarding", dest="forwarding", help="target for result forwarding phase")
    parser.add_option(      '--buildruntime', dest='buildruntime', help='select the build runtime to use (will automatically be determined by default)')
    parser.add_option(      '--profiling', dest='profiling', help='activate a specific behaviour of the build plugin')
    return parser

def base_09_options():
    # Setup argument parser
    parser = OptionParser()
    parser._get_all_options()
    parser.add_option('-M', '--dependency_file', dest='dependency_file', help='optional multi-component dependency resolution file')
    parser.add_option('-b', '--build-script', dest='build_script', help='optional custom build tool launcher script (defaults to <project>/cfg/build.py if present, otherwise vmake')
    parser.add_option('-n', '--alternate-path', dest='alternate_path', help='optional give alternate path to discover plugin')
    parser.add_option('-B', '--skip-build-phase', dest='skip_build', action='store_true', help="skip the execution of the build plugin's build step")
    parser.add_option('-c', '--clean-build', dest='do_clean', action='store_true', help='perform a "clean" build (eradicate any previous build results)')
    parser.add_option('-s', '--purge-all', dest='do_purge_all', action='store_true', help='eradicate ALL previous build cfg and start build anew, only applying args from current command line')
    parser.add_option("-r", "--project-root-dir", dest="project_root_dir",  help="project root directory (default is configured from .xmake file)")
    parser.add_option("-l", "--gendir-label", dest="gendir_label", help="logical name of generation directory [default: 'gen']")
    parser.add_option("-g", "--gendir", dest="gendir", help="optional gen dir, [default: <project-root-dir/<label>>]")
    parser.add_option("-m", "--mode", dest="mode", help="build mode (e.g. dbg, rel, opt)")
    parser.add_option("-p", "--platform", dest="platform", help="build platform (e.g. ntintel)")
    parser.add_option("-I", "--import-repo", dest="import_repos", action='append', help="maven repository URL to import from. Specify multiple times to have more than repository.")
    parser.add_option("-i", '--import', dest="do_import", action='store_true', help="import from configured maven-repos before build")
    parser.add_option("-E", "--export-repo", dest="export_repos", action='append', help="maven upload repository URL")
    parser.add_option("-U", "--deploy-user", dest="deploy_users", action='append', help="user name for repository deployment")
    parser.add_option("-P", "--deploy-password", dest="deploy_passwords", action='append', help="password for repository deployment")
    parser.add_option(      "--deploy-credentials-key", dest="deploy_cred_keys", action='append', help='credential key for repository deployment (replaces -U,-P if specified)')
    parser.add_option("-e", "--export", dest="do_export", action='store_true', help="export build results after build")
    parser.add_option("-d", "--deploy", dest="do_deploy", action='store_true', help="deploy exported results to the configured maven repository (implies -e, requires -E)")
    parser.add_option("-R", "--promote", dest="do_promote", action='store_true', help="promote staged results to the configured maven repository")
    parser.add_option("-v", "--version", dest="version", help="build result version for build result exposure")
    parser.add_option(      "--show-info", dest="show_version", action="store_true", help="show xmake version info")
    parser.add_option("-X", "--xmake-version", dest="xmake_version", help="dedicated version of xmake used for the build")
    parser.add_option(      "--default-xmake-version", dest="default_xmake_version", help="xmake version to use if no version is specified in sources")
    parser.add_option(      '--scm-snapshot-url', dest="scm_snapshot_url", help="an unambiguous URL that identifies the source tree this build was based upon")
    parser.add_option(      '--productive', dest="productive", action='store_true', help='if set, the build behaves as a productive build, applying additional checks (e.g. existence of release metadata)')
    parser.add_option(      '--release', dest="release", help='if set with direct-shipment or indirect-shipment, the build behaves as a release build, applying additional checks (e.g. existence of release metadata or run MQR plugin)')
    parser.add_option(      '--use-current-xmake-version', dest="use_current_xmake_version", action='store_true', help='if set, the build uses the initially called version of xmake)')
    parser.add_option(      '--debug-xmake', dest="debug_xmake", action='store_true', help='provide more internal execution information in log')
    parser.add_option(      '--get-version', dest="get_version", action='store_true', help='get project version and make it available in gen/temp/project.version ')
    parser.add_option(      '--set-version', dest="set_version", help='set the given project version  ')
    parser.add_option(      '--drop-staging', dest="do_drop_staging", action='store_true', help="drop the given staging repository")
    parser.add_option(      '--staging-repo', dest="staging_repoid", action='store', help="Optional Staging repo ID for staging, closing and promoting")
    parser.add_option(      '--create-staging', dest="do_create_staging", action='store_true', help='Create staging repository')
    parser.add_option(      '--close-staging', dest="do_close_staging", action='store_true', help='Close staging repository')
    return parser
