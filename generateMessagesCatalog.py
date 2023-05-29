'''
See COPYRIGHT.md for copyright information.
'''
import os, time, io, ast, sys, traceback

def entityEncode(arg):  # be sure it's a string, vs int, etc, and encode &, <, ".
    return str(arg).replace("&","&amp;").replace("<","&lt;").replace('"','&quot;')

if __name__ == "__main__":
    startedAt = time.time()
    
    idMsg = []
    numArelleSrcFiles = 0

    arelleSrcPath = (os.path.dirname(__file__) or os.curdir) + os.sep + "arelle"
    for arelleSrcDir in (arelleSrcPath, 
                         arelleSrcPath + os.sep + "plugin",
                         arelleSrcPath + os.sep + "plugin" + os.sep + "validate" + os.sep + "EFM",
                         # arelleSrcPath + os.sep + "plugin" + os.sep + "validate" + os.sep + "ESEF",
                         arelleSrcPath + os.sep + "plugin" + os.sep + "EdgarRenderer"
                         # arelleSrcPath + os.sep + "plugin" + os.sep + "validate" + os.sep + "GL"
                         ):
        if not os.path.exists(arelleSrcDir):
            continue
        for moduleFilename in os.listdir(arelleSrcDir):
            if moduleFilename.endswith(".py"):
                numArelleSrcFiles += 1
                fullFilenamePath = arelleSrcDir + os.sep + moduleFilename
                refFilename = fullFilenamePath[len(arelleSrcPath)+1:].replace("\\","/")
                with open(fullFilenamePath, encoding="utf-8") as f:
                    tree = ast.parse(f.read(), filename=moduleFilename)
                    for item in ast.walk(tree):
                        try:
                            if (isinstance(item, ast.Call) and
                                (getattr(item.func, "attr", '') or getattr(item.func, "id", '')) # imported function could be by id instead of attr
                                in ("info","warning","log","error","exception")):
                                    funcName = item.func.attr
                                    iArgOffset = 0
                                    if funcName == "info":
                                        level = "info"
                                    elif funcName == "warning":
                                        level = "warning"
                                    elif funcName == "error":
                                        level = "error"
                                    elif funcName == "exception":
                                        level = "exception"
                                    elif funcName == "log":
                                        levelArg = item.args[0]
                                        if isinstance(levelArg,ast.Str):
                                            level = levelArg.s.lower()
                                        else:
                                            if any(isinstance(elt, (ast.Call, ast.Name))
                                                   for elt in ast.walk(levelArg)):
                                                level = "(dynamic)"
                                            else:
                                                level = ', '.join(elt.s.lower()
                                                                  for elt in ast.walk(levelArg)
                                                                  if isinstance(elt, ast.Str))
                                        iArgOffset = 1
                                    msgCodeArg = item.args[0 + iArgOffset]  # str or tuple
                                    if isinstance(msgCodeArg,ast.Str):
                                        msgCodes = (msgCodeArg.s,)
                                    elif isinstance(msgCodeArg, ast.Call) and getattr(msgCodeArg.func, "id", '') == 'ixMsgCode':
                                        msgCodes = ("ix{{ver.sect}}:{}".format(msgCodeArg.args[0].s),)
                                    else:
                                        if any(isinstance(elt, (ast.Call, ast.Name))
                                               for elt in ast.walk(msgCodeArg)):
                                            msgCodes = ("(dynamic)",)
                                        else:
                                            msgCodes = [elt.s 
                                                        for elt in ast.walk(msgCodeArg)
                                                        if isinstance(elt, ast.Str)]
                                    msgArg = item.args[1 + iArgOffset]
                                    if isinstance(msgArg, ast.Str):
                                        msg = msgArg.s
                                    elif isinstance(msgArg, ast.Call) and getattr(msgArg.func, "id", '') == '_':
                                        msg = msgArg.args[0].s
                                    elif any(isinstance(elt, (ast.Call,ast.Name))
                                             for elt in ast.walk(msgArg)):
                                        msg = "(dynamic)"
                                    else:
                                        continue # not sure what to report
                                    keywords = []
                                    for keyword in item.keywords:
                                        if keyword.arg == 'modelObject':
                                            pass
                                        elif keyword.arg == 'messageCodes':
                                            msgCodeArg = keyword.value
                                            if any(isinstance(elt, (ast.Call, ast.Name))
                                                   for elt in ast.walk(msgCodeArg)):
                                                pass # dynamic
                                            else:
                                                msgCodes = [elt.s 
                                                            for elt in ast.walk(msgCodeArg)
                                                            if isinstance(elt, ast.Str)]
                                        else:
                                            keywords.append(keyword.arg)
                                    for msgCode in msgCodes:
                                        idMsg.append((msgCode, msg, level, keywords, refFilename, item.lineno))                                        
                        except (AttributeError, IndexError):
                            pass
                    

    lines = []
    for id,msg,level,args,module,line in idMsg:
        try:
            if args and any(isinstance(arg,str) for arg in args):
                argAttr = "\n         args=\"{0}\"".format(
                            entityEncode(" ".join(arg for arg in args if arg is not None)))
            else:
                argAttr = ""
            lines.append("<message code=\"{0}\"\n         level=\"{3}\"\n         module=\"{4}\" line=\"{5}\"{2}>\n{1}\n</message>"
                      .format(id, 
                              entityEncode(msg),
                              argAttr,
                              level,
                              module,
                              line))
        except Exception as ex:
            print(ex)
            print("traceback {}".format(traceback.format_tb(sys.exc_info()[2])))
    os.makedirs(arelleSrcPath + os.sep + "doc", exist_ok=True)
    with io.open(arelleSrcPath + os.sep + "doc" + os.sep + "messagesCatalog.xml", 'wt', encoding='utf-8') as f:
        f.write(
'''<?xml version="1.0" encoding="utf-8"?>
<messages
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:noNamespaceSchemaLocation="messagesCatalog.xsd"
    variablePrefix="%("
    variableSuffix=")s"
    variablePrefixEscape="" >
<!-- 
This file contains Arelle messages text.   Each message has a code 
that corresponds to the message code in the log file, level (severity), 
args (available through log file), and message replacement text.

(Messages with dynamically composed error codes or text content 
(such as ValidateXbrlDTS.py line 158 or lxml parser messages) 
are reported as "(dynamic)".)

-->

''')
        f.write("\n\n".join(sorted(lines)))
        f.write("\n\n</messages>")
        
    with io.open(arelleSrcPath + os.sep + "doc" + os.sep + "messagesCatalog.xsd", 'wt', encoding='utf-8') as f:
        f.write(
'''<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" elementFormDefault="unqualified"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <xs:element name="messages">
    <xs:complexType>
      <xs:sequence>
        <xs:element maxOccurs="unbounded" name="message">
          <xs:complexType>
            <xs:simpleContent>
              <xs:extension base="xs:string">
                <xs:attribute name="code" use="required" type="xs:normalizedString"/>
                <xs:attribute name="level" use="required" type="xs:token"/>
                <xs:attribute name="module" type="xs:normalizedString"/>
                <xs:attribute name="line" type="xs:integer"/>
                <xs:attribute name="args" type="xs:NMTOKENS"/>
              </xs:extension>
            </xs:simpleContent>
          </xs:complexType>
        </xs:element>
      </xs:sequence>
      <xs:attribute name="variablePrefix" type="xs:string"/>
      <xs:attribute name="variableSuffix" type="xs:string"/>
      <xs:attribute name="variablePrefixEscape" type="xs:string"/>
    </xs:complexType>
  </xs:element>
</xs:schema>
''')
    
    print("Arelle messages catalog {0:.2f} secs, {1} formula files, {2} messages".format( time.time() - startedAt, numArelleSrcFiles, len(idMsg) ))