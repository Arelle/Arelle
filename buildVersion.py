'''
Created on May 28, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.

This module emits the version.py file contents which are used in the
build process to indicate the time that this version was built.

'''
import datetime, sys

if __name__ == "__main__":
    is64BitPython = sys.maxsize == 0x7fffffffffffffff
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
        
    with open("version.txt", "w") as fh:
        fh.write(timestamp.strftime("%Y-%m-%d %H:%M UTC"))
        

    distFileDate = timestamp.strftime("%Y-%m-%d")
    # add name suffix, like ER3 or TKTABLE
    if len(sys.argv) > 1 and sys.argv[1]:
        distFileDate += "-" + sys.argv[1]
        
    if sys.platform == "darwin":
        with open("buildRenameDmg.sh", "w") as fh:
            fh.write("mv dist_dmg/arelle.dmg dist_dmg/arelle-macOS-{}.dmg\n".format(distFileDate))
    if sys.platform == "linux2":
        with open("buildRenameLinux-x86_64.sh", "w") as fh:
            fh.write("mv dist/exe.linux-x86_64-{}.{}.tar.gz dist/arelle-linux-x86_64-{}.tar.gz\n"
                     .format(sys.version_info[0], sys.version_info[1], distFileDate))
    elif sys.platform == "linux": # python 3.3
        if len(sys.argv) > 1 and sys.argv[1]:
            sysName = sys.argv[1]
        else:
            sysName = "linux"
        with open("buildRenameLinux-x86_64.sh", "w") as fh:
            fh.write("mv dist/exe.linux-x86_64-{}.{}.tar.gz dist/arelle-{}-x86_64-{}.tar.gz\n"
                     .format(sys.version_info[0], sys.version_info[1], 
                             sysName, distFileDate))
    elif sys.platform == "sunos5":
        with open("buildRenameSol10Sun4.sh", "w") as fh:
            fh.write("mv dist/exe.solaris-2.10-sun4v{0}-{1}.{2}.tar.gz dist/arelle-solaris10-sun4{0}-{3}.tar.gz\n"
                     .format(".64bit" if is64BitPython else "",
                             sys.version_info[0],sys.version_info[1], 
                             distFileDate))
    elif sys.platform.startswith("win"):
        renameCmdFile = "buildRenamer.bat"
        with open("buildRenameX86.bat", "w") as fh:
            fh.write("rename dist\\arelle-win-x86.exe arelle-win-x86-{}.exe\n".format(distFileDate))
        with open("buildRenameX64.bat", "w") as fh:
            fh.write("rename dist\\arelle-win-x64.exe arelle-win-x64-{}.exe\n".format(distFileDate))
        with open("buildRenameSvr27.bat", "w") as fh:
            fh.write("rename dist\\arelle-svr-2.7.zip arelle-svr-2.7-{}.zip\n".format(distFileDate))
        with open("buildRenameZip32.bat", "w") as fh:
            fh.write("rename dist\\arelle-cmd32.zip arelle-cmd32-{}.zip\n".format(distFileDate))
        with open("buildRenameZip64.bat", "w") as fh:
            fh.write("rename dist\\arelle-cmd64.zip arelle-cmd64-{}.zip\n".format(distFileDate))
