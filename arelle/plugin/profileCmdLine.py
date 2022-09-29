'''
CmdLine Profiler is an example of a plug-in to command line processing that will profile all execution.

See COPYRIGHT.md for copyright information.
'''
import os
from arelle.Version import authorLabel, copyrightLabel

def profilerOptionExtender(parser, *args, **kwargs):
    parser.add_option("--saveProfilerReport",
                      action="store",
                      dest="profilerReportFile",
                      help=_("Run command line options under profiler and save report file.  Expect about 3x execution time to collect profiling statistics."))

def profilerCommandLineRun(cntlr, options, sourceZipStream=None, *args, **kwargs):
    from arelle import Locale
    import cProfile, pstats, sys, time
    profileReportFile = getattr(options, "profilerReportFile", None)
    if profileReportFile and not getattr(cntlr, "blockNestedProfiling", False):
        startedAt = time.time()
        cntlr.addToLog(_("invoking command processing under profiler"))
        statsFile = profileReportFile + ".bin"
        cntlr.blockNestedProfiling = True
        cProfile.runctx("cntlr.run(options, sourceZipStream)", globals(), locals(), statsFile)
        cntlr.addToLog(Locale.format_string(cntlr.modelManager.locale,
                                            _("profiled command processing completed in %.2f secs"),
                                            time.time() - startedAt))
        # specify a file for log
        priorStdOut = sys.stdout
        sys.stdout = open(profileReportFile, "w")

        statObj = pstats.Stats(statsFile)
        statObj.strip_dirs()
        statObj.sort_stats("time")
        statObj.print_stats()
        statObj.print_callees()
        statObj.print_callers()
        sys.stdout.flush()
        sys.stdout.close()
        del statObj
        sys.stdout = priorStdOut
        os.remove(statsFile)
        del cntlr.blockNestedProfiling
        sys.exit() # raise SYSTEM_EXIT to stop outer execution



__pluginInfo__ = {
    'name': 'CmdLine Profiler',
    'version': '1.0',
    'description': "This plug-in adds a profiling to command line (and web service) processing.  ",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'CntlrCmdLine.Options': profilerOptionExtender,
    'CntlrCmdLine.Utility.Run': profilerCommandLineRun,
}
