'''
Save DTS is an example of a plug-in to both GUI menu and command line/web service
that will save the files of a DTS into a zip file.

(c) Copyright 2012 Mark V Systems Limited, All rights reserved.
'''

import threading
from lxml import etree

def validateSchemaWithLxml(modelXbrl, cntlr=None):
    class schemaResolver(etree.Resolver):
        def resolve(self, url, id, context): 
            if url.startswith("file:///__"):
                url = importedFilepaths[int(url[10:])]
            filepath = modelXbrl.modelManager.cntlr.webCache.getfilename(url)
            return self.resolve_filename(filepath, context)
          
    entryDocument = modelXbrl.modelDocument
    # test of schema validation using lxml (trial experiment, commented out for production use)
    from arelle import ModelDocument
    imports = []
    importedNamespaces = set()
    importedFilepaths = []

    '''    
    for mdlSchemaDoc in entryDocument.referencesDocument.keys():
        if (mdlSchemaDoc.type == ModelDocument.Type.SCHEMA and 
            mdlSchemaDoc.targetNamespace not in importedNamespaces):
            # actual file won't pass through properly, fake with table reference
            imports.append('<xsd:import namespace="{0}" schemaLocation="file:///__{1}"/>'.format(
                mdlSchemaDoc.targetNamespace, len(importedFilepaths)))
            importedNamespaces.add(mdlSchemaDoc.targetNamespace)
            importedFilepaths.append(mdlSchemaDoc.filepath)
    '''    

    def importReferences(referencingDocument):
        for mdlSchemaDoc in referencingDocument.referencesDocument.keys():
            if (mdlSchemaDoc.type == ModelDocument.Type.SCHEMA and 
                mdlSchemaDoc.targetNamespace not in importedNamespaces):
                importedNamespaces.add(mdlSchemaDoc.targetNamespace)
                importReferences(mdlSchemaDoc)  # do dependencies first
                # actual file won't pass through properly, fake with table reference
                imports.append('<xsd:import namespace="{0}" schemaLocation="file:///__{1}"/>'.format(
                    mdlSchemaDoc.targetNamespace, len(importedFilepaths)))
                importedFilepaths.append(mdlSchemaDoc.filepath)
    importReferences(entryDocument)
    # add schemas used in xml validation but not DTS discovered
    for mdlDoc in modelXbrl.urlDocs.values():
        if mdlDoc.type in (ModelDocument.Type.INSTANCE, ModelDocument.Type.LINKBASE):
            schemaLocation = mdlDoc.xmlRootElement.get("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation")
            if schemaLocation:
                ns = None
                for entry in schemaLocation.split():
                    if ns is None:
                        ns = entry
                    else:
                        if ns not in importedNamespaces:
                            imports.append('<xsd:import namespace="{0}" schemaLocation="file:///__{1}"/>'.format(
                                ns, len(importedFilepaths)))
                            importedNamespaces.add(ns)
                            importedFilepaths.append(entry)
                        ns = None
    schemaXml = '<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema">\n{0}</xsd:schema>\n'.format(
                   '\n'.join(imports))
    # trace schema files referenced
    with open("c:\\temp\\test.xml", "w") as fh:
        fh.write(schemaXml)
    modelXbrl.modelManager.showStatus(_("lxml validator loading xml schema"))
    schema_root = etree.XML(schemaXml)
    import time
    startedAt = time.time()
    parser = etree.XMLParser()
    parser.resolvers.add(schemaResolver())
    schemaDoc = etree.fromstring(schemaXml, parser=parser, base_url=entryDocument.filepath+"-dummy-import.xsd")
    schema = etree.XMLSchema(schemaDoc)
    from arelle.Locale import format_string
    modelXbrl.info("info:lxmlSchemaValidator", format_string(modelXbrl.modelManager.locale, 
                                 _("schema loaded in %.2f secs"), 
                                        time.time() - startedAt))
    modelXbrl.modelManager.showStatus(_("lxml schema validating"))
    # check instance documents and linkbases (sort for inst doc before linkbases, and in file name order)
    for mdlDoc in sorted(modelXbrl.urlDocs.values(), key=lambda mdlDoc: (-mdlDoc.type, mdlDoc.filepath)):
        if mdlDoc.type in (ModelDocument.Type.INSTANCE, ModelDocument.Type.LINKBASE):
            startedAt = time.time()
            docXmlTree = etree.parse(mdlDoc.filepath)
            modelXbrl.info("info:lxmlSchemaValidator", format_string(modelXbrl.modelManager.locale, 
                                                _("schema validated in %.3f secs"), 
                                                time.time() - startedAt),
                                                modelDocument=mdlDoc)
            if not schema.validate(docXmlTree):
                for error in schema.error_log:
                    modelXbrl.error("lxmlSchema:{0}".format(error.type_name.lower()),
                            error.message,
                            modelDocument=mdlDoc,
                            sourceLine=error.line)
    modelXbrl.modelManager.showStatus(_("lxml validation done"), clearAfter=3000)
    
    if cntlr is not None:   
        # if using GUI controller, not cmd line or web service, select the errors window when done
        cntlr.uiThreadQueue.put((cntlr.logSelect, []))

def validateSchemaWithLxmlMenuEntender(cntlr, validationmenu):
    # Insert as 2nd menu item for the lxml schema validation
    validationmenu.insert_command(1, label="Validate schema with lxml", 
                                  underline=0, 
                                  command=lambda: validateSchemaWithLxmlMenuCommand(cntlr) )

def validateSchemaWithLxmlMenuCommand(cntlr):
    # save DTS menu item has been invoked
    if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
        cntlr.addToLog(_("No taxonomy loaded."))
        return
    # do the schema validation in background (and afterwards focus on GUI messages pane)
    thread = threading.Thread(target=lambda dts=cntlr.modelManager.modelXbrl, c=cntlr: validateSchemaWithLxml(dts, c))
    thread.daemon = True
    thread.start()

def validateSchemaWithLxmlCommandLineOptionExtender(parser):
    # extend command line options with a save DTS option
    parser.add_option("--validateSchemaWithLxml", 
                      action="store_true", 
                      dest="validateSchemaLxml", 
                      help=_("Validate the schema with lxml (experimental)"))

def validateSchemaWithLxmlCommandLineXbrlRun(cntlr, options, modelXbrl, *args):
    # extend XBRL-loaded run processing for this option
    if getattr(options, "validateSchemaLxml", False):
        if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
            cntlr.addToLog(_("No taxonomy loaded."))
            return
        validateSchemaWithLxml(cntlr.modelManager.modelXbrl)


'''
   Do not use _( ) in pluginInfo itself (it is applied later, after loading
'''

__pluginInfo__ = {
    'name': 'Validate Schema with Lxml',
    'version': '0.9',
    'description': "This plug-in provides schema validation using lxml.  As of 2012-05 "
                    " lxml does not properly schema validate XBRL schemas, which is why"
                    " it is provided in a plug-in instead of the main build.  "
                    "For the GUI, this feature is inserted to the tools->validation menu 2nd position.  "
                    "This is an experimental feature, not suitable for XBRL production use until lxml"
                    " schema validation becomes reliable for XBRL schemas.",
    'license': 'Apache-2',
    'author': 'Mark V Systems Limited',
    'copyright': '(c) Copyright 2012 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'CntlrWinMain.Menu.Validation': validateSchemaWithLxmlMenuEntender,
    'CntlrCmdLine.Options': validateSchemaWithLxmlCommandLineOptionExtender,
    'CntlrCmdLine.Xbrl.Run': validateSchemaWithLxmlCommandLineXbrlRun,
}
