'''
Created on 18.10.2014

@author: D021770 - I050906
'''
import logging
import utils
import subprocess
import os
import string
import re
import threading
import time

class _MonitoringWorker(threading.Thread):
    MESSAGE_ALIVE="WARNING: no activity in xmake logs since {0} seconds but changes detected in the gen directory"
    def __init__(self, build_cfg, wait):
        threading.Thread.__init__(self)
        self.logging_event=threading.Event()
        self.monitoring_stop_event=threading.Event()
        self.wait=wait
        self.build_cfg=build_cfg

    def __del__(self):
        self.monitoring_stop_event.set()    
        if self.is_alive(): 
            self.join()

    def run(self):
        def _monitoring_fileWalker(args,dirname,names):
            '''
            checks files in names'''
            args[1]['files']+=len(names)
            for f in names:
                if os.path.join(dirname,f)==os.path.join(self.build_cfg.genroot_dir(),"build.log") or os.path.join(dirname,f)==os.path.join(self.build_cfg.genroot_dir(),"boot.log"): continue
                st=os.stat(os.path.join(dirname,f))    
                args[1]['global_size']+=st.st_size
                if st.st_mtime>args[0]: args[1]['change']=True
        walker_detection={'change':False,'global_size':0,'files':0}
        last_time=time.time()
        if self.build_cfg.component_dir(): os.path.walk(self.build_cfg.genroot_dir(),_monitoring_fileWalker,[last_time,walker_detection])
        last_global_size=walker_detection['global_size']
        last_files=walker_detection['files']
    
        is_main_thread_active = lambda : any((i.name == "MainThread") and i.is_alive() for i in threading.enumerate())
        while not self.monitoring_stop_event.is_set() and is_main_thread_active():
            time.sleep(0.1)
            new_time=time.time()
            if new_time-last_time>self.wait:
                dirname=self.build_cfg.genroot_dir() if self.build_cfg.component_dir() else None
                if dirname:
                    walker_detection['change']=False
                    walker_detection['global_size']=0
                    walker_detection['files']=0
                    os.path.walk(dirname,_monitoring_fileWalker,[new_time,walker_detection])
                    if  not self.logging_event.is_set() and (walker_detection['global_size']!=last_global_size or walker_detection['files']!=last_files or walker_detection['change']):
                        _logGuessLevel(_MonitoringWorker.MESSAGE_ALIVE.format(str(self.wait)))
                    last_global_size=walker_detection['global_size']
                    last_files=walker_detection['files']
                self.logging_event.clear()
                last_time=new_time

_logging_monitoring=None

def logging_monitoring_enable(build_cfg, wait=1200):
    global _logging_monitoring
    _logging_monitoring=_MonitoringWorker(build_cfg,wait)
    _logging_monitoring.start()

class _TailThread(threading.Thread):
    def __init__(self, prefixPath=None, filename=None, fromBegining=False, handler=None, fileInput=None):
        threading.Thread.__init__(self)
        self.handler = handler
        self.prefixPath=prefixPath
        self.filename=filename
        self.stopTailingOpenLoop=threading.Event()
        self.stopTailingReadingLoop=threading.Event()
        self.forceStop=threading.Event()
        self.fromBegining=fromBegining
        self.opened=False
        self.first_call=True
        self.fileInput=fileInput        
        self.is_main_thread_active = lambda : any((i.name == "MainThread") and i.is_alive() for i in threading.enumerate())
        self.fullFilename=os.path.join(self.prefixPath,self.filename) if self.prefixPath else self.filename

    def read(self, fileInput):
        if self.first_call:
            if(self.fromBegining==False): fileInput.seek(0, 2)
            self.first_call = False
        while True:
            latest_data = fileInput.readline()
            if latest_data:
                if self.handler:
                    self.handler(latest_data),
                _logGuessLevel(latest_data, '('+self.filename+')' if self.filename else None)
            if not ((not self.stopTailingReadingLoop.is_set() or latest_data) and not self.forceStop.is_set() and self.is_main_thread_active()): 
                break

    def tail_F(self):
        while not self.stopTailingOpenLoop.is_set() and not self.forceStop.is_set() and self.is_main_thread_active():            
            try:
                with open(self.fullFilename, 'r') as fileInput:
                    self.read(fileInput)
            except IOError as e:
                pass

    def run(self):
        self.read(self.fileInput) if self.fileInput else self.tail_F()
        
    def stop(self,forceStop=False):
        self.stopTailingOpenLoop.set()
        self.stopTailingReadingLoop.set()
        if forceStop: self.forceStop.set()

    def flush(self):
        if self.filename and self.first_call and self.fromBegining:
            try:
                with open(self.fullFilename) as fileInput:
                    for line in fileInput:
                        if line: 
                            if self.handler:
                                self.handler(line),
                            _logGuessLevel(line, '('+self.filename+')')
            except IOError:
                pass
        
class Tail:
    filename=""
    reader=None       
    
    def __init__(self, prefixPath, filename):
        self.filename=filename
        self.prefixPath=prefixPath
        
    def start(self, fromBegining=False):
        self.reader = _TailThread(self.prefixPath, self.filename, fromBegining)
        self.reader.start()

    def stop(self,forceStop=False):
        self.reader.stop(forceStop)
        if self.reader.is_alive(): self.reader.join()
        self.reader.flush()
        
'''
import time

tailedFile=Tail('C:/Users/i051432/toto.log')
tailedFile.start(True)
time.sleep(15) # delays for 5 seconds
tailedFile.stop()
'''
        
class ExecEnv(object):
    def __init__(self):
        self.cwd = None
        self.env = dict(os.environ)

    def log_execute(self, args, handler=None):
        if self.cwd is not None:
            info('executing in '+self.cwd)
        return log_execute(args, handler=handler, env=self.env, cwd=self.cwd)

    def log_execute_shell(self, args, handler=None):
        if self.cwd is not None:
            info('executing in '+self.cwd)
        return log_execute_shell(args, handler=handler, env=self.env, cwd=self.cwd)
            
class CacheLogHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self._log_records = []

    def handle(self, record):
        self._log_records.append(record)

    def attach_file_handler(self, filelog_hdlr):
        for log_record in self._log_records:
            filelog_hdlr.emit(log_record)

INFRA = 'INFRA'

_consolelog_hdlr = logging.StreamHandler()
_consolelog_hdlr.setLevel(logging.INFO)  # display INFO and above log levels
_consolelog_hdlr.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))

_filelog_hdlr = None
_cachelog_hdlr = CacheLogHandler()

logging.addLevelName(logging.WARNING, 'WARN')  # WARNING rename WARN
logger = logging.getLogger()
logger.setLevel(logging.NOTSET)  # get all log levels
logger.addHandler(_cachelog_hdlr)
logger.addHandler(_consolelog_hdlr)

class _MonitoringHandler(logging.Handler):
    def emit(self, record):
        global _logging_monitoring
        if _logging_monitoring:
            _logging_monitoring.logging_event.set()
        
logger.addHandler(_MonitoringHandler())


def start_logfile(path):
    debug('START LOGGING IN FILE:' + path)
    global logger, _filelog_hdlr, _cachelog_hdlr
    if path and not _filelog_hdlr:
        _filelog_hdlr = logging.FileHandler(path)
        _filelog_hdlr.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s', '%H:%M:%S'))
        _cachelog_hdlr.attach_file_handler(_filelog_hdlr)
        logger.removeHandler(_cachelog_hdlr)
        _cachelog_hdlr.close()
        logger.addHandler(_filelog_hdlr)
        info('log file is ' + path)


def stop_logfile():
    debug('STOP LOGGING IN FILE')
    global logger, _filelog_hdlr
    if _filelog_hdlr:
        logger.removeHandler(_filelog_hdlr)
        _filelog_hdlr.close()
    pass


def log_file_content(path):
    global logger
    with open(path) as f:
        c = f.read()
        debug(str(c))


def expand_variables(env):
    if not env:
        env = dict(os.environ)

    if 'XMAKE_ENV_FILE' in env:
        additional_env = {}
        with open(env['XMAKE_ENV_FILE'], 'r') as f:
            for line in f.readlines():
                index = line.index('=')
                (key, value) = (line[:index], line[index+1:])
                additional_env[key] = value.strip()

        additional_env_not_resolved = {}
        for _ in range(5):
            for key, value in additional_env.items():
                if env:
                    additional_env[key] = string.Template(additional_env[key]).safe_substitute(env)
                    if additional_env[key].find('$') == -1:
                        env[key] = additional_env[key]
                        debug('set environment variable {}={}'.format(key, additional_env[key]))
                    else:
                        additional_env_not_resolved[key] = additional_env[key]

            if len(additional_env_not_resolved.items()) > 0:
                additional_env = additional_env_not_resolved
            else:
                additional_env_not_resolved = {}
                break
        for key, value in additional_env_not_resolved.items():
            warning('cannot expand/resolve environment variable {}={}'.format(key, value))
    return env


def log_execute(args, handler=None, env=None, cwd=None, shell=False):
    utils.flush()
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=shell, env=expand_variables(env), cwd=cwd)
    
    reader = _TailThread(fileInput=p.stdout, handler=handler, fromBegining=True)
    rc = None 
    try:
        reader.start()
    
        # Wait until subprocess is done
        rc = p.wait()
    
    finally:
        # Wait until we've processed all output
        reader.stop(False)
        if reader.is_alive(): reader.join()
    
        utils.flush()
    return rc


def log_execute_shell(args, handler=None, env=None, cwd=None):
    return log_execute(args, handler, env, cwd, True)


def _message(cat, *args):
    msg = ' '.join([str(x) for x in args])
    if msg.endswith('\n'):
        msg = msg[:-1]
    if msg.endswith('\r'):
        msg = msg[:-1]

    if cat == INFRA:
        return '({}) '.format(cat) + msg

    return msg


def setConsoleLevel(lvl):
    global _consolelog_hdlr
    _consolelog_hdlr.setLevel(lvl)


def exception(ex):
    global logger
    logger.log(logging.ERROR, str(ex))
    logger.log(logging.DEBUG, ex, exc_info=True)


def debug(*msg):
    global logger
    logger.debug(_message(None, *msg))


def info(*msg):
    global logger
    logger.info(_message(None, *msg))


def error(msg, cat=None):
    global logger
    logger.error(_message(cat, *(msg,)))


def warning(msg, cat=None):
    global logger
    logger.warning(_message(cat, *(msg,)))


def _logGuessLevel(msg, prefix=None):
    global logger
    logLevel = logging.INFO
    logMsg = msg

    m = re.search(r'^(?P<level>(?:(?:INFORMATION|INFO):|\[(?:INFORMATION|INFO)\]|\((?:INFORMATION|INFO)\))\s)', logMsg, re.IGNORECASE)
    if m:
        logLevel = logging.INFO
    else:
        m = re.search(r'^(?P<level>(?:(?:WARNING|WARN):|\[(?:WARNING|WARN)\]|\((?:WARNING|WARN)\))\s)', logMsg, re.IGNORECASE)
        if m:
            logLevel = logging.WARNING
        else:
            m = re.search(r'^(?P<level>(?:(?:ERROR|ERR):|\[(?:ERROR|ERR)\]|\((?:ERROR|ERR)\))\s)', logMsg, re.IGNORECASE)
            if m:
                logLevel = logging.ERROR

    try:
        if m and m.group('level'):
            logMsg = msg.replace(m.group('level'), '')
    except IndexError:
        pass

    logger.log(logLevel, _message(None, *((prefix if prefix else '')+logMsg,)))
