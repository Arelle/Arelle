'''
See COPYRIGHT.md for copyright information.

Example Arelle REST API tester

Including EdgarRenderer testcases

Execute by running as a main program

'''
from subprocess import Popen, PIPE, STDOUT
import sys, os, io, time, shutil, urllib.request, traceback, zipfile, regex as re, socketserver

# (please change below directories for your environment)

# Linux paths
#ARELLE = "/Users/hermf/Documents/mvsl/projects/Arelle/ArelleProject/edgr24.1/arelleCmdLine.py"
#PYTHON = "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11"
#LOG_DIR = "/Users/hermf/temp/apiTest"
#EFM_DIR = "/Users/hermf/Documents/mvsl/projects/SEC/efm/conf/"

# Windows paths
#ARELLE = "/Users/hermf/Documents/mvsl/projects/Arelle/ArelleProject/edgr24.1/arelleCmdLine.py"
#PYTHON = "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11"
#LOG_DIR = "/Users/hermf/temp/apiTest"
#EFM_DIR = "/Users/hermf/Documents/mvsl/projects/SEC/efm/conf/"

# Mac paths
PYTHON = "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11"
ARELLE = "/Users/hermf/Documents/mvsl/projects/Arelle/ArelleProject/edgr24.1/arelleCmdLine.py"
LOG_DIR = "/Users/hermf/temp/apiTest"
EFM_DIR = "/Users/hermf/Documents/mvsl/projects/SEC/efm/conf/"

SEPERATE_WEBSERVER_LOG = True # true if co-mingling client and server logs doesn't work

ARELLE_RUN = [PYTHON, ARELLE]

WEBSERVER_HOST = "localhost" # port set dynamically
nextPort = 8090

WEBSERVER_ARGS = ["--webserver", "set-dynamically"]

# test case format
#    key = id, d = description, r = rest command, p = POST file

TESTCASES1 = { 
    # these tests run on a webserver which doesn't preload any plugins
    "00001": {"d": "About command", "r": "/about"},
    "00002": {"d": "Help command", "r": "/help"},
    "99999": {"d": "Stop web server", "r":"/rest/stopWebServer"}
    }

TESTCASES2 = { 
    # these are EdgarRenderer tests which run on a webserver which preloads 
    # the EdgarRenderer plugin on the command line which starts the webserver
    #
    # the test cases reference tests cases which are in the SEC Interactive Data test suite
    #
    # for the POST tests, the test cases need a zip file created by the user of the files in the test case
    # e.g. in test 00200-zPOST and other *zPOST tests, one must 
    # "zip i00200gd-20081231.zip *" in the test case directory before running these tests
    "00200-f": {
        "d":"i00200 simple example, rest file arg is htm file", "r":
            "/rest/xbrl/validation?media=html&efm-pragmatic&logFile=logFile.txt"
            f"&file={EFM_DIR}525-ix-syntax/efm/00-filing/i00200gd/i00200gd-20081231.htm"
        },
    "00200-zPOST": {
        "d":"i00200 simple example, POST zip file arg is htm file in zip", "r":
            "/rest/xbrl/validation?media=html&efm-pragmatic&logFile=logFile.txt&file=i00200gd-20081231.htm",
        "p": f"{EFM_DIR}525-ix-syntax/efm/00-filing/i00200gd/i00200gd-20081231.zip"
        },
    "17001-f": {
        "d":"17-redact 01ng, single doc IXDS, rest file arg is a file, return html errs", "r":
            "/rest/xbrl/validation?media=html&efm-pragmatic"
            f"&file={EFM_DIR}525-ix-syntax/efm/17-redaction/e17red001ng/e17red001ng-20081231.htm"
            "&logFile=logFile.txt"
        },
    "17001-d": {
        "d":"17-redact 01ng, single doc IXDS, rest file arg is directory, return html errs", "r":
            "/rest/xbrl/validation?media=html&efm-pragmatic"
            f"&file={EFM_DIR}525-ix-syntax/efm/17-redaction/e17red001ng"
            "&logFile=logFile.txt"
        },
    "17002-f": {
        "d":"17-redact 02gd, single doc IXDS, rest file arg is htm file name, return zip with dist subdir and logFile.txt", "r":
            "/rest/xbrl/validation?media=zip&efm-pragmatic&logFile=logFile.txt"
            f"&file={EFM_DIR}525-ix-syntax/efm/17-redaction/e17red002gd/e17red002gd-20081231.htm"
        },
    "17002-d": {
        "d":"17-redact 02gd, single doc IXDS, rest file arg is directory name, return zip with dist subdir and logFile.txt", "r":
            "/rest/xbrl/validation?media=zip&efm-pragmatic&logFile=logFile.txt"
            f"&file={EFM_DIR}525-ix-syntax/efm/17-redaction/e17red002gd/e17red002gd-20081231.zip"
        },
    "17002-p": {
        "d":"17-redact 02gd, single doc IXDS, rest file in rest path expression, return zip with dist subdir and logFile.txt", "r":
            "/rest/xbrl/"
            f"{EFM_DIR}525-ix-syntax/efm/17-redaction/e17red002gd/e17red002gd-20081231.htm"
            "/validation/xbrl?media=zip&efm-pragmatic&logFile=logFile.txt"
        },
    "17002-zGET": {
        "d":"17-redact 02gd, single doc IXDS, GET zip via file arg as zip file name, return zip with dist subdir and logFile.txt", "r":
            "/rest/xbrl/validation?media=zip&efm-pragmatic&logFile=logFile.txt"
            f"&file={EFM_DIR}525-ix-syntax/efm/17-redaction/e17red002gd/e17red002gd-20081231.zip"
        },
    "17002-zPOST": {
        "d":"17-redact 02gd, single doc IXDS, POST zip with file arg as htm file name, return zip with dist subdir and logFile.txt", "r":
            "/rest/xbrl/validation?media=zip&efm-pragmatic&file=e17red002gd-20081231.htm&logFile=logFile.txt",
        "p": f"{EFM_DIR}525-ix-syntax/efm/17-redaction/e17red002gd/e17red002gd-20081231.zip"
        },
    "17003-f": {
        "d":"17-redact 03gd, multi doc IXDS, rest file arg is a file, return zip with dist subdir", "r":
            "/rest/xbrl/validation?media=zip&efm-pragmatic&logFile=logFile.txt"
            # with filename specified won't discover other docs in directory for the IXDS
            f"&file={EFM_DIR}525-ix-syntax/efm/17-redaction/e17red003gd/e17red003gd-20081231.htm"
        },
    "17003-d": {
        "d":"17-redact 03gd, multi doc IXDS, rest file arg is directory, return zip with dist subdir", "r":
            "/rest/xbrl/validation?media=zip&efm-pragmatic&logFile=logFile.txt"
            # with directory specified will discover other docs in directory for the IXDS
            f"&file={EFM_DIR}525-ix-syntax/efm/17-redaction/e17red003gd"
        },
    "17003-p": {
        "d":"17-redact 03gd, multi doc IXDS, rest directory in rest path expression, return zip with dist subdir", "r":
            "/rest/xbrl/"
            f"{EFM_DIR}525-ix-syntax/efm/17-redaction/e17red003gd"
            "/validation/xbrl?media=zip&efm-pragmatic&logFile=logFile.txt"
        },
    "17003-zGET": {
        "d":"17-redact 03gd, multi doc IXDS, GET zip via file arg as zip file name, return zip with dist subdir", "r":
            "/rest/xbrl/validation?media=zip&efm-pragmatic&logFile=logFile.txt"
            f"&file={EFM_DIR}525-ix-syntax/efm/17-redaction/e17red003gd/e17red003gd-20081231.zip"
        },
    "17003-zGET-f": {
        "d":"17-redact 03gd, multi doc IXDS, GET zip via file arg as zip file name, file arg ignored, still discovers DTS, return zip with dist subdir", "r":
            "/rest/xbrl/validation?media=zip&efm-pragmatic&file=e17red003gd-20081231.htm&logFile=logFile.txt"
            # filename argument is ignored, while DTS is d iscovered
            f"&file={EFM_DIR}525-ix-syntax/efm/17-redaction/e17red003gd/e17red003gd-20081231.zip"
        },
    "17003-zPOST": {
        "d":"17-redact 03gd, multi doc IXDS, POST zip with no file arg so all ix files are discovered, return zip with dist subdir", "r":
            "/rest/xbrl/validation?media=zip&efm-pragmatic&logFile=logFile.txt",
        "p": f"{EFM_DIR}525-ix-syntax/efm/17-redaction/e17red003gd/e17red003gd-20081231.zip"
        },
    "17004": {
        "d":"17-redact 04gd, single doc IXDS, return zip with dist subdir", "r":
            "/rest/xbrl/validation?media=zip&efm-pragmatic&logFile=logFile.txt"
            f"&file={EFM_DIR}525-ix-syntax/efm/17-redaction/e17red004gd"
        },
    #"17005": {
    #    "d":"17-redact 05gd, single doc IXDS, return zip with dist subdir", "r":
    #        "/rest/xbrl/validation?media=zip&efm-pragmatic"
    #        f"&file={EFM_DIR}525-ix-syntax/efm/17-redaction/e17red005gd"},
    "99999": {"d":"Stop web server", "r": "/rest/stopWebServer"}
    }

POST_TESTCASE = { # separate post test case for debugging separately
    "17003-zGET-f": {
        "d":"17-redact 03gd, multi doc IXDS, GET zip via file arg as zip file name, file arg blocks DTS discovery, return zip with dist subdir", "r":
            "/rest/xbrl/validation?media=zip&efm-pragmatic&file=e17red003gd-20081231.htm&logFile=logFile.txt"
            # with filename specified won't discover other docs in directory for the IXDS
            f"&file={EFM_DIR}525-ix-syntax/efm/17-redaction/e17red003gd/e17red003gd-20081231.zip"
        },
    "99999": {"d":"Stop web server", "r": "/rest/stopWebServer"}
    }

WEBSERVER_RUNS = (
    # each run represents additional arguments to webserver
    ("Run plain web server without any extra arguments", 
     [], 
     TESTCASES1),
    ("Run webserver preloading EdgarRenderer", 
     ["--plugins", "EdgarRenderer"], 
     TESTCASES2),
    )

# remove leading _ to run just below
_WEBSERVER_RUNS = (
    # debug running just POST_TESTCASE instead of whole suite
    ("Run webserver preloading EdgarRenderer", 
     ["--plugins", "EdgarRenderer"], 
     POST_TESTCASE),
    )

REDLINE_REDACT_TEST = [
    "+Generating rendered reports in Reports/dissem",
    "-The rendering engine was unable to produce output due to an internal error",
    "-traceback:",
    # no EFM, xbrl ix messages
    "-[EFM.5", "-[EFM.6", "-[xbrl.", "-[ix11."]

VALIDATIONS = {
    # html validation, minimal expected content
    "00001": ["+>About arelle<"],
    "00002": ["+>Arelle web API<"],
    "00200": ["+submissionType 8-K, attachmentDocumentType 8-K"],
    "17001": ["+[EFM.17Ad-27.disallowedRedact]", "-Exception"],
    "17002": {"hasDissem": True, 
              "numFiles": 22, 
              "logFile.txt": REDLINE_REDACT_TEST},
    "17003-f":  {
              # with file specified won't discover other docs in the IXDS
              "logFile.txt": ["+[xbrl.4.6.1:itemContextRef]"]},
    "17003": {"hasDissem": True, 
              "numFiles": 24, 
              "logFile.txt": REDLINE_REDACT_TEST},
    "17004": {"hasDissem": True, 
              "numFiles": 22, 
              "logFile.txt": REDLINE_REDACT_TEST},
    "17005": {"hasDissem": True, 
              "numFiles": 22, 
              "logFile.txt": REDLINE_REDACT_TEST},
    "99999": ["+>Good bye...<"]
    }

logFile = svrLogFile = None
validationCounts = {"pass": 0, "fail": 0, "exceptions": 0}

jsonPattern = re.compile(br"^\s*[\[\{].*[\]\}]\s*$")
htmlPattern = re.compile(br"^\s*(<\?xml[^>]*\?>\s*)?<x?html[\s>]")

def log(
        msg: str, 
        flush: bool = False
    ) -> None:
    print(msg, file=logFile)
    if flush:
        logFile.flush()
    
def logContent(
        testNbr: str, 
        suffix: str, 
        content: bytes
    ) -> None:
    with io.open(os.path.join(LOG_DIR, "out", f"{testNbr}.{suffix}"), mode="ba") as fh:
        fh.write(content)
    
def logStdout(
        p: Popen, 
        flush: bool = False
    ) -> None:
    # log any stdout/stderr in pipe
    if SEPERATE_WEBSERVER_LOG:
        if flush:
            svrLogFile.flush()
    elif not p.stdout.closed and p.stdout.readable():
        stdoutStr = p.stdout.read()
        if stdoutStr:
            log(f"[webserverStdout]")
            log(stdoutStr, flush=flush)
            
def runTest(
        id: str,
        test: dict
    ) -> None:
    startedAt = time.time()
    log(f"[testStart] {id} {test['d']}")
    try:
        data = None
        headers = {}
        if "p" in test: # file to post
            postFile = test["p"]
            headers["Content-Type"] = "application/x-zip"
            headers["Content-Length"] = os.stat(postFile).st_size
            data = io.open(postFile, "rb")
        time.sleep(4)
        req = urllib.request.Request(f"http://{WEBSERVER_ARGS[1]}{test['r']}", data=data, headers=headers)
        with urllib.request.urlopen(req) as r:
            execTime = time.time() - startedAt
            content = r.fp.read()
            status = r.getcode()
        if content.startswith(b"\x50\x4b\x03\x04"):
            # zip contents
            ft = "zip"
        elif jsonPattern.match(content):
            # test contents
            ft = "json"
            logContent(id, ft, content)
        elif htmlPattern.match(content):
            # test contents
            ft = "html"
            logContent(id, ft, content)
        else:
            # test contents
            ft = "txt"
        log(f"[testResult] type={ft} time={execTime:.4f} status={status} length={r.length}")
        if ft == "zip":
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                log("zip contents:\n" + "\n".join("   " + il.filename for il in zf.infolist()))
        logContent(id, ft, content)
        val = validateResults(id, ft, content)
        log(f"[validationStatus] {val}")
        if val == "Pass":
            validationCounts["pass"] += 1
        else:
            validationCounts["fail"] += 1
    except Exception as ex:
        log(f"[testException] {ex} \n {traceback.format_exception(*sys.exc_info())}")
        validationCounts["exceptions"] += 1
    

def run() -> None:
    # set up log directory
    shutil.rmtree(LOG_DIR, ignore_errors=True)
    os.makedirs(os.path.join(LOG_DIR, "out"), exist_ok=True)
    global logFile, svrLogFile
    logFile = io.open(os.path.join(LOG_DIR, "log.txt"), mode="wt")
    if SEPERATE_WEBSERVER_LOG:
        svrLogFile = io.open(os.path.join(LOG_DIR, "serverlog.txt"), mode="wt")
        stdout = stderr = svrLogFile
    else:
        stdout = PIPE
        stderr = STDOUT
    startedAt = time.time()
    # loop through testcases
    for runTitle, runArgs, testcases in WEBSERVER_RUNS:
        try:
            # find port which is free
            with socketserver.TCPServer(("localhost", 0), None) as s:
                free_port = s.server_address[1]
            WEBSERVER_ARGS[1] = f"{WEBSERVER_HOST}:{free_port}"
            # start web server
            log(f"[startWebServer] {runTitle}", flush=True)
            pid = None
            with Popen(ARELLE_RUN + WEBSERVER_ARGS + runArgs, stdout=stdout, stderr=stderr, text=True) as p:
                pid = p.pid
                time.sleep(2)
                if not SEPERATE_WEBSERVER_LOG:
                    os.set_blocking(p.stdout.fileno(), False)
                for id, test in sorted(testcases.items()):
                    print(f"test {id}")
                    rtnCode = p.poll()
                    if rtnCode is not None: # server has quit
                        log(f"[webserverQuit] code={rtnCode}", flush=True)
                        logStdout(p)
                        break
                    else: # server is still running
                        logStdout(p)
                        runTest(id, test)
                time.sleep(2)
                logStdout(p, flush=True)
                if SEPERATE_WEBSERVER_LOG:
                    svrLogFile.flush()
                time.sleep(2)
                p.kill()
                
        except Exception as ex:
            log(f"[webserverException] {ex} \n {traceback.format_exception(*sys.exc_info())}", flush=True)
            validationCounts["exceptions"] += 1
    
    testingTime = time.time() - startedAt
    log(f"[testSummary] pass={validationCounts['pass']} fail={validationCounts['fail']} exceptions={validationCounts['exceptions']} time={testingTime:.2f}")
            
    if logFile is not None:
        logFile.close()
    if svrLogFile is not None:
        svrLogFile.close()
        
def validateContent(
        tests: list,
        content: bytes,
        where: str
    ) -> str:
    lcContent = content.lower()
    messages = []
    for test in tests:
        notExpected = test.startswith("-")
        expct = test[(test[0] in ("+","-")):]
        lcExpct = expct.lower()
        if isinstance(content, bytes):
            lcExpct = lcExpct.encode("utf-8")
        if notExpected and lcExpct in lcContent:
            messages.append(f"Not expecting \"{expct}\"")
        elif not notExpected and lcExpct not in lcContent:
            messages.append(f"Missing \"{expct}\"")
    if messages:
        return f"Fail {where}: {', '.join(messages)}"
    return "Pass"
        
def validateResults(
        testNbr: str, 
        fileType: str, 
        content: bytes
    ) -> str:
    testShortNbr = testNbr.partition("-")[0]
    if fileType == "html":
        tests = VALIDATIONS.get(testNbr, VALIDATIONS.get(testShortNbr,["missing test"]))
        return validateContent(tests, content, "html")
    elif fileType == "zip":
        numFiles = 0
        hasDissem = False
        v = VALIDATIONS.get(testNbr, VALIDATIONS.get(testShortNbr,{}))
        msgs = []
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            numFiles = sum(not il.is_dir() for il in zf.infolist())
            hasDissem = any(il.filename.startswith("dissem/") for il in zf.infolist())
            if "logFile.txt" in v:
                tests = v["logFile.txt"]
                if any(il.filename == "logFile.txt" for il in zf.infolist()):
                    with zf.open("logFile.txt") as lf:
                        log = lf.read()
                        msgs.append( validateContent(tests, log, "logFile") )
        if "hasDissem" in v:
            if hasDissem != v["hasDissem"]:
                msgs.append(  f"Fail: Expecting dissem = {v.get('hasDissem', False)}, has dissem = {hasDissem}" )
        if "numFiles" in v:
            if numFiles != v["numFiles"]:
                msgs.append( f"Fail: Expected {v.get('numFiles', 0)} files, has {numFiles} files" )
        if any(m.startswith("Fail") for m in msgs):
            return "\n ".join(m for m in msgs if m.startswith("Fail"))
        return "Pass"
    return f"Missing validation check for test {testNbr}"
        
if __name__ == "__main__":
    run()