'''
Save RSS Messages: custom log RSS messages

Intended to provide csv (or other) file for post-processing and database loading.

See COPYRIGHT.md for copyright information.
(Does not apply to the XBRL US Database schema and description.)

'''

import time, os, io, sys, logging
from arelle.Locale import format_string
from arelle.ModelDtsObject import ModelConcept, ModelRelationship, ModelLocator
from arelle.ModelInstanceObject import ModelFact
from arelle.Version import authorLabel, copyrightLabel

_saveMessagesFile = None

def saveMessages(saveMessagesFile, modelXbrl, rssItem=None, **kwargs):
    # get logging entries (needed to find which aspects to identify)
    if rssItem is not None:
        instanceFile = rssItem.accessionNumber
        companyName = rssItem.companyName
        formType = rssItem.formType
        filingDate = rssItem.filingDate
    else:
        # note that these fields could be obtained as with plugin xbrlDB/entityInformation.py
        instanceFile = modelXbrl.uri
        companyName = formType = filingDate = ""
    for handler in logging.getLogger("arelle").handlers:
        if hasattr(handler, "logEntries"):
            loggingEntries = handler.logEntries()
            messages = []
            messageRefs = []
            for i, logEntry in enumerate(loggingEntries):
                sequenceInReport = str(i+1)
                for ref in logEntry['refs']:
                    modelObject = modelXbrl.modelObject(ref.get('objectId',''))
                    sourceLine = ref.get('sourceLine', None)
                    refType = None
                    href = ref.get('href')
                    qname = value = None
                    # for now just find a concept
                    if isinstance(modelObject, ModelLocator): # dereference
                        modelObject = modelObject.dereference()
                    if isinstance(modelObject, ModelFact):
                        refType = "fact"
                        qname = str(modelObject.qname)
                        value = modelObject.value[0:32]
                    elif isinstance(modelObject, ModelRelationship):
                        refType = "rel"
                        _to = modelObject.toModelObject
                        _from = modelObject.fromModelObject
                        if isinstance(_to, ModelConcept):
                            qname = _to.qname
                        elif isinstance(_from, ModelConcept):
                            qname = _from.qname
                        value = os.path.basename(modelObject.arcrole)
                    elif isinstance(modelObject, ModelConcept):
                        refType = "concept"
                        qname = modelObject.qname
                    elif modelObject is not None:
                        refType = type(modelObject).__name__
                    messageRefs .append([instanceFile,
                                         sequenceInReport,
                                         href,
                                         sourceLine,
                                         refType,
                                         qname,
                                         value])
                _messageCode = logEntry['code']
                if _messageCode.startswith("DQC.US."):
                    _shortMessageCode = _messageCode.rpartition('.')[0]
                else:
                    _shortMessageCode = _messageCode
                messages.append([instanceFile,
                                 companyName, formType, filingDate,
                                 sequenceInReport,
                                 _messageCode, _shortMessageCode,
                                 logEntry['level'],
                                 logEntry['message']['text']])
            if messages:
                with open(saveMessagesFile, mode="at", encoding="utf-8") as fh:
                    fh.write(''.join(','.join(('"{}"'.format(str(c).replace('"', '""'))
                                               if c is not None else '')
                                                for c in m) + '\n'
                                     for m in messages))
                fileParts = os.path.splitext(saveMessagesFile)
                with open(fileParts[0] + "_refs" + fileParts[1], mode="at", encoding="utf-8") as fh:
                    fh.write(''.join(','.join(('"{}"'.format(str(c).replace('"', '""'))
                                               if c is not None else '')
                                                for c in mr) + '\n'
                                     for mr in messageRefs))

def saveMsgsCommandLineOptionExtender(parser, *args, **kwargs):
    # extend command line options to store to database
    parser.add_option("--saveMessagesFile",
                      action="store",
                      dest="saveMessagesFile",
                      help=_("File name into which to save messages.  "))

    logging.getLogger("arelle").addHandler(LogHandler())

def saveMsgsCommandLineXbrlLoaded(cntlr, options, modelXbrl, *args, **kwargs):
    from arelle.ModelDocument import Type
    if modelXbrl.modelDocument.type == Type.RSSFEED and getattr(options, "saveMessagesFile", False):
        modelXbrl.saveMessagesFile = options.saveMessagesFile

def saveMsgsCommandLineXbrlRun(cntlr, options, modelXbrl, *args, **kwargs):
    from arelle.ModelDocument import Type
    if (modelXbrl.modelDocument.type not in (Type.RSSFEED, Type.TESTCASE, Type.REGISTRYTESTCASE) and
        getattr(options, "saveMessagesFile", False)):
        saveMessages(options.saveMessagesFile, modelXbrl)

def saveMsgsValidateRssItem(val, modelXbrl, rssItem, *args, **kwargs):
    if hasattr(val.modelXbrl, 'saveMessagesFile'):
        saveMessages(val.modelXbrl.saveMessagesFile, modelXbrl, rssItem)

def saveMsgsTestcaseVariationXbrlLoaded(val, modelXbrl, *args, **kwargs):
    if _saveMessagesFile:
        return saveMessages(_saveMessagesFile, modelXbrl)

def saveMsgsrssWatchHasWatchAction(rssWatchOptions, *args, **kwargs):
    return rssWatchOptions.get("saveMessagesFile")

def saveMsgsrssDoWatchAction(modelXbrl, rssWatchOptions, rssItem, *args, **kwargs):
    saveMessagesFile = rssWatchOptions.get("saveMessagesFile")
    if saveMessagesFile:
        saveMessages(saveMessagesFile, modelXbrl)

def saveMsgsLoaderSetup(cntlr, options, *args, **kwargs):
    global _saveMessagesFile
    # set options to load from DB (instead of load from XBRL and store in DB)
    _saveMessagesFile = getattr(options, "saveMessagesFile", None)

class LogHandler(logging.Handler):
    def __init__(self):
        super(LogHandler, self).__init__()
        self.logRecordBuffer = []

    def flush(self):
        del self.logRecordBuffer[:]

    def logEntries(self, clear=True):
        entries = []
        for logRec in self.logRecordBuffer:
            message = { "text": self.format(logRec) }
            if logRec.args:
                for n, v in logRec.args.items():
                    message[n] = v
            entry = {"code": logRec.messageCode,
                     "level": logRec.levelname.lower(),
                     "refs": logRec.refs,
                     "message": message}
            entries.append(entry)
        if clear:
            del self.logRecordBuffer[:]
        return entries

    def emit(self, logRecord):
        self.logRecordBuffer.append(logRecord)


__pluginInfo__ = {
    'name': 'XBRL Database',
    'version': '1.2',
    'description': "This plug-in saves logger messages of instances for post processing.  ",
    'license': 'Apache-2 (Arelle plug-in), BSD license (pg8000 library)',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'CntlrCmdLine.Options': saveMsgsCommandLineOptionExtender,
    'CntlrCmdLine.Utility.Run': saveMsgsLoaderSetup,
    'CntlrCmdLine.Xbrl.Loaded': saveMsgsCommandLineXbrlLoaded,
    'CntlrCmdLine.Xbrl.Run': saveMsgsCommandLineXbrlRun,
    'RssWatch.HasWatchAction': saveMsgsrssWatchHasWatchAction,
    'RssWatch.DoWatchAction': saveMsgsrssDoWatchAction,
    'Validate.RssItem': saveMsgsValidateRssItem,
    'TestcaseVariation.Xbrl.Loaded': saveMsgsTestcaseVariationXbrlLoaded,
}
