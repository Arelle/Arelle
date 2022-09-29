"""
See COPYRIGHT.md for copyright information.

This module emits the version.py file contents which are used in the
build process to indicate the time that this version was built.

"""
import datetime
import sys

if __name__ == "__main__":
    timestamp = datetime.datetime.utcnow()
    date_dash_ymd = timestamp.strftime("%Y-%m-%d")

    # add name suffix, like ER3 or TKTABLE
    if len(sys.argv) > 1 and sys.argv[1] and sys.platform not in ("linux",):
        date_dash_ymd += "-" + sys.argv[1]

    if sys.platform == "darwin":
        with open("buildRenameDmg.sh", "w") as fh:
            fh.write("cp dist_dmg/arelle.dmg dist/arelle-macOS-{}.dmg\n".format(date_dash_ymd))
    elif sys.platform.startswith("linux"):
        if len(sys.argv) > 1 and sys.argv[1]:
            sysName = sys.argv[1]
        else:
            sysName = "linux"
        with open("buildRenameLinux-x86_64.sh", "w") as fh:
            fh.write("mv dist/exe.linux-x86_64-{}.{}.tgz dist/arelle-{}-x86_64-{}.tgz\n"
                     .format(sys.version_info[0], sys.version_info[1], sysName, date_dash_ymd))
    elif sys.platform.startswith("win"):
        renameCmdFile = "buildRenamer.bat"
        with open("buildRenameX86.bat", "w") as fh:
            fh.write("rename dist\\arelle-win-x86.exe arelle-win-x86-{}.exe\n".format(date_dash_ymd))
        with open("buildRenameX64.bat", "w") as fh:
            fh.write("rename dist\\arelle-win-x64.exe arelle-win-x64-{0}.exe\n"
                     "rename dist\\arelle-win-x64.zip arelle-win-x64-{0}.zip\n"
                     .format(date_dash_ymd))
        with open("buildRenameSvr27.bat", "w") as fh:
            fh.write("rename dist\\arelle-svr-2.7.zip arelle-svr-2.7-{}.zip\n".format(date_dash_ymd))
        with open("buildRenameZip32.bat", "w") as fh:
            fh.write("rename dist\\arelle-cmd32.zip arelle-cmd32-{}.zip\n".format(date_dash_ymd))
        with open("buildRenameZip64.bat", "w") as fh:
            fh.write("rename dist\\arelle-cmd64.zip arelle-cmd64-{}.zip\n".format(date_dash_ymd))
