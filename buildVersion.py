'''
Created on May 28, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.

This module emits the version.py file contents which are used in the
build process to indicate the time that this version was built.

'''
import datetime, sys

if __name__ == "__main__":
    timestamp = datetime.datetime.utcnow()
    
    versionPy = ("'''\n"
                 "This module represents the time stamp when Arelle was last built\n"
                 "\n"
                 "@author: Mark V Systems Limited\n"
                 "(c) Copyright {0} Mark V Systems Limited, All rights reserved.\n"
                 "\n"
                 "'''\n"
                 "version = '{1}'\n"
                 ).format(timestamp.year, 
                    timestamp.strftime("%Y-%m-%d %H:%M UTC")
                    )

    with open("arelle/Version.py", "w") as fh:
        fh.write(versionPy)

    distFileDate = timestamp.strftime("%Y-%m-%d")
    if sys.platform == "darwin":
        with open("buildRenameDmg.sh", "w") as fh:
            fh.write("mv dist_dmg/arelle.dmg dist_dmg/arelle-macOS-{0}.dmg\n".format(distFileDate))
    if sys.platform == "linux2":
        with open("buildRenameLinux-x86_64.sh", "w") as fh:
            fh.write("mv dist/exe.linux-x86_64-3.2.tar.gz dist/arelle-linux-x86_64-{0}.tar.gz\n".format(distFileDate))
    elif sys.platform.startswith("win"):
        renameCmdFile = "buildRenamer.bat"
        with open("buildRenameX86.bat", "w") as fh:
            fh.write("rename dist\\arelle-win-x86.exe arelle-win-x86-{0}.exe\n".format(distFileDate))
        with open("buildRenameX64.bat", "w") as fh:
            fh.write("rename dist\\arelle-win-x64.exe arelle-win-x64-{0}.exe\n".format(distFileDate))
        with open("buildRenameSvr27.bat", "w") as fh:
            fh.write("rename dist\\arelle-svr-2.7.zip arelle-svr-2.7-{0}.zip\n".format(distFileDate))
