'''
XbrlSemanticRDFDB.py implements an RDF database interface for Arelle, based
on a concrete realization of the Abstract Model PWD 2.0 layer.  This is a semantic
representation of XBRL information.

This module may save directly to a NanoSparqlServer or to append to a file of RDF Turtle.
See http://sourceforge.net/apps/mediawiki/bigdata/index.php?title=NanoSparqlServer

This module provides the execution context for saving a dts and instances in
XBRL RDF graph.  It may be loaded by Arelle's RSS feed, or by individual
DTS and instances opened by interactive or command line/web service mode.

Example dialog or command line parameters for operation:

    host:  the supporting host for NanoSparqlServer or "rdfTurtleFile" to append to a turtle file
    port:  the host port (80 is default) if a NanoSparqlServer
    user, password:  if needed for server
    database:  the top level path segment for the NanoSparqlServer or disk file path if rdfTurtleFile
    timeout:


See COPYRIGHT.md for copyright information.

to do:

1) add AMTF cube regions (dimensions)
    HF - don't believe this is either feasible or has a use case in a graph model
2) check existence of (shared) documents and contained elements before adding
3) tuple structure declaration (particles in elements of data dictionary?)
4) tuple structure (instance facts)
5) add footnote resources to relationships (and test with EDInet footnote references)
6) test some filings with text blocks (shred them?)  (30mB - 50mB sized text blocks?)
7) add mappings to, or any missing relationships, of Charlie's financial model

---

rdflib pass


'''

import os, io, time, json, socket, logging, zlib, datetime
from arelle.ModelDtsObject import ModelConcept, ModelResource, ModelRelationship
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelDocument import Type
from arelle import XbrlConst, XmlUtil, UrlUtil
import urllib.request
from urllib.error import HTTPError, URLError
from lxml import etree

TRACERDFFILE = None
#TRACERDFFILE = r"c:\temp\rdfDBtrace.log"  # uncomment to trace RDF on connection (very big file!!!)

RDFTURTLEFILE_HOSTNAME = "rdfTurtleFile"
RDFXMLFILE_HOSTNAME = "rdfXmlFile"

def insertIntoDB(modelXbrl,
                 user=None, password=None, host=None, port=None, database=None, timeout=None,
                 product=None, rssItem=None, **kwargs):
    rdfdb = None
    try:
        rdfdb = XbrlSemanticRdfDatabaseConnection(modelXbrl, user, password, host, port, database, timeout)
        rdfdb.insertXbrl(rssItem=rssItem)
        rdfdb.close()
    except Exception as ex:
        if rdfdb is not None:
            try:
                rdfdb.close(rollback=True)
            except Exception as ex2:
                pass
        raise # reraise original exception with original traceback

def isDBPort(host, port, db, timeout=10):
    if host in (RDFTURTLEFILE_HOSTNAME, RDFXMLFILE_HOSTNAME):
        return True
    # determine if postgres port
    t = 2
    while t < timeout:
        try:
            conn = urllib.request.urlopen("http://{0}:{1}/{2}/status".format(host, port or '80', db))
            return True # success but doesn't need password
        except HTTPError:
            return False # success, this is really a postgres socket, wants user name
        except URLError:
            return False # something is there but not postgres
        except socket.timeout:
            t = t + 2  # relax - try again with longer timeout
    return False

# deferred rdflib import
Namespace = URIRef = Literal = Graph = L = XSD = RDF = RDFS = None
DEFAULT_GRAPH_CLASS = None


# namespaces act as abstract model classes

XML = XBRL = XBRLI = LINK = QName = Filing = DTS = Aspect = AspectType = None
DocumentTypes = RoleType = ArcRoleType = Relationship = ArcRoleCycles = None
DataPoint = Context = Period = Unit = None
SEC = None

def initRdflibNamespaces():
    global Namespace, URIRef, Literal, Graph, L, XSD, RDF, RDFS, DEFAULT_GRAPH_CLASS
    if Namespace is None:
        from rdflib import Namespace, URIRef, Literal, Graph
        from rdflib import Literal as L
        from rdflib.namespace import XSD, RDF, RDFS
        DEFAULT_GRAPH_CLASS = Graph
    global XML, XBRL, XBRLI, LINK, QName, Filing, DTS, Aspect, AspectType, \
           DocumentTypes, RoleType, ArcRoleType, Relationship, ArcRoleCycles, \
           DataPoint, Context, Period, Unit, \
           SEC
    if XML is None:
        XML = Namespace("http://www.w3.org/XML/1998/namespace")
        XBRL = Namespace("http://xbrl.org/2013/rdf/")
        XBRLI = Namespace("http://www.xbrl.org/2003/instance#")
        LINK = Namespace("http://www.xbrl.org/2003/linkbase#")
        QName = Namespace("http://xbrl.org/2013/rdf/QName/")
        Filing = Namespace("http://xbrl.org/2013/rdf/Filing/")
        DTS = Namespace("http://xbrl.org/2013/rdf/DTS/")
        DocumentTypes = {Type.INSTANCE: XBRL.Instance,
                         Type.INLINEXBRL: XBRL.InlineHtml,
                         Type.SCHEMA: XBRL.Schema,
                         Type.LINKBASE: XBRL.Linkbase,
                         Type.UnknownXML: XML.Document}
        Aspect = Namespace("http://xbrl.org/2013/rdf/Aspect#")
        AspectType = Namespace("http://xbrl.org/2013/rdf/Aspect/Type#")
        RoleType = Namespace("http://xbrl.org/2013/rdf/DTS/RoleType#")
        ArcRoleType = Namespace("http://xbrl.org/2013/rdf/DTS/ArcRoleType#")
        Relationship = Namespace("http://xbrl.org/2013/rdf/DTS/Relationship#")
        ArcRoleCycles = Namespace("http://xbrl.org/2013/rdf/DTS/ArcRoleType/Cycles/")
        DataPoint = Namespace("http://xbrl.org/2013/rdf/DataPoint/")
        Context = Namespace("http://xbrl.org/2013/rdf/Context/")
        Period = Namespace("http://xbrl.org/2013/rdf/Period/")
        Unit = Namespace("http://xbrl.org/2013/rdf/Unit/")

        SEC = Namespace("http://www.sec.gov/")

def modelObjectDocumentUri(modelObject):
    return URIRef( UrlUtil.ensureUrl(modelObject.modelDocument.uri) )

def modelObjectUri(modelObject):
    return URIRef('#'.join((modelObjectDocumentUri(modelObject),
                            XmlUtil.elementFragmentIdentifier(modelObject))))

def qnameUri(qname, sep='#'):
    return URIRef(sep.join((qname.namespaceURI, qname.localName)))

def qnamePrefix_Name(qname, sep='_'):
    # substitutte standard prefixes for commonly-defaulted xmlns namespaces
    prefix = {XbrlConst.xsd: 'xsd',
              XbrlConst.xml: 'xml',
              XbrlConst.xbrli: 'xbrli',
              XbrlConst.link: 'link',
              XbrlConst.gen: 'gen',
              XbrlConst.xlink: 'xlink'
              }.get(qname.namespaceURI, qname.prefix)
    return L(sep.join((prefix, qname.localName)))

def modelObjectQnameUri(modelObject, sep='#'):
    return qnameUri(modelObject.qname, sep)

class XRDBException(Exception):
    def __init__(self, code, message, **kwargs ):
        self.code = code
        self.message = message
        self.kwargs = kwargs
        self.args = ( self.__repr__(), )
    def __repr__(self):
        return _('[{0}] exception: {1}').format(self.code, self.message % self.kwargs)



class XbrlSemanticRdfDatabaseConnection():
    def __init__(self, modelXbrl, user, password, host, port, database, timeout):
        try:
            initRdflibNamespaces()
        except ImportError:
            raise XRDBException("xrdfDB:MissingRdflib",
                                _("Rdflib is not installed or is not available in this build"))
        self.modelXbrl = modelXbrl
        self.disclosureSystem = modelXbrl.modelManager.disclosureSystem
        #self.conn = RexProConnection(host, int(port or '8182'), (database or 'emptygraph'),
        #                             user=user, password=password)
        self.isRdfTurtleFile = host == RDFTURTLEFILE_HOSTNAME
        self.isRdfXmlFile = host == RDFXMLFILE_HOSTNAME
        if self.isRdfTurtleFile or self.isRdfXmlFile:
            self.turtleFile = database
        else:
            connectionUrl = "http://{0}:{1}".format(host, port or '80')
            self.url = connectionUrl
            if database:
                self.url += '/' + database
            # Create an OpenerDirector with support for Basic HTTP Authentication...
            auth_handler = urllib.request.HTTPBasicAuthHandler()
            if user:
                auth_handler.add_password(realm=None,
                                          uri=connectionUrl,
                                          user=user,
                                          passwd=password)
            self.conn = urllib.request.build_opener(auth_handler)
            self.timeout = timeout or 60
        self.verticePropTypes = {}

    def close(self, rollback=False):
        try:
            if not (self.isRdfTurtleFile or self.isRdfXmlFile):
                self.conn.close()
            self.__dict__.clear() # dereference everything
        except Exception as ex:
            self.__dict__.clear() # dereference everything
            raise

    @property
    def isClosed(self):
        return not bool(self.__dict__)  # closed when dict is empty

    def showStatus(self, msg, clearAfter=None):
        self.modelXbrl.modelManager.showStatus(msg, clearAfter)

    def initializeGraph(self, graph=None):
        g =  graph or DEFAULT_GRAPH_CLASS()
        g.bind("xml", XML)
        g.bind("xbrl", XBRL)
        g.bind("xbrli", XBRLI)
        g.bind("link", LINK)
        g.bind("qname", QName)
        g.bind("filing", Filing)
        g.bind("dts", DTS)
        g.bind("aspect", Aspect)
        g.bind("aspectType", AspectType)
        g.bind("roleType", RoleType)
        g.bind("arcRoleType", ArcRoleType)
        g.bind("arcroleCycles", ArcRoleCycles)
        g.bind("relationship", Relationship)
        g.bind("dataPoint", DataPoint)
        g.bind("context", Context)
        g.bind("period", Period)
        g.bind("unit", Unit)
        g.bind("sec", SEC)
        return g

    def execute(self, activity, graph=None, query=None):
        if graph is not None:
            headers = {'User-agent':   'Arelle/1.0',
                       'Accept':       'application/sparql-results+json',
                       'Content-Type': "text/turtle; charset='UTF-8'"}
            data = graph.serialize(format='pretty-xml' if self.isRdfXmlFile else 'turtle',
                                   encoding='utf=8')
        elif query is not None:
            headers = {'User-agent':   'Arelle/1.0',
                       'Accept':       'application/sparql-results+json'}
            data = ("query=" + query).encode('utf-8')
        else:
            return None
        # turtle may be mixture of line strings and strings with \n-separated lines
        if TRACERDFFILE:
            with io.open(TRACERDFFILE, "ab") as fh:
                fh.write(b"\n\n>>> sent: \n")
                fh.write(data)
        if (self.isRdfTurtleFile or self.isRdfXmlFile) and data is not None:
            with io.open(self.turtleFile, "ab") as fh:
                fh.write(data)
            return None
        if graph is not None or query is not None:
            url = self.url + "/sparql"
        request = urllib.request.Request(url,
                                         data=data,
                                         headers=headers)
        try:
            with self.conn.open(request, timeout=self.timeout) as fp:
                results = fp.read().decode('utf-8')
            try:
                results = json.loads(results)
            except ValueError:
                pass # leave results as string
        except HTTPError as err:
            results = err.fp.read().decode('utf-8')
        if TRACERDFFILE:
            with io.open(TRACERDFFILE, "a", encoding='utf-8') as fh:
                fh.write("\n\n>>> received: \n{0}".format(str(results)))
        if isinstance(results, str) and query is not None:
            parser = etree.HTMLParser()
            htmlDoc = etree.parse(io.StringIO(results), parser)
            body = htmlDoc.find("//body")
            if body is not None:
                error = "".join(text for text in body.itertext())
            else:
                error = results
            raise XRDBException("xrdfDB:DatabaseError",
                                _("%(activity)s not successful: %(error)s"),
                                activity=activity, error=error)
        return results

    def commit(self, graph):
        self.execute("Saving RDF Graph", graph=graph)

    def loadGraphRootVertices(self):
        self.showStatus("Load/Create graph root vertices")
        pass

    def getDBsize(self):
        self.showStatus("Get database size")
        return 0

    def insertXbrl(self, rssItem):
        try:
            # must also have default dimensions loaded
            from arelle import ValidateXbrlDimensions
            ValidateXbrlDimensions.loadDimensionDefaults(self.modelXbrl)

            #initialVcount, initialEcount = self.getDBsize() # don't include in timing, very slow
            startedAt = time.time()

            # find pre-existing documents in server database
            self.identifyPreexistingDocuments()

            g = self.initializeGraph()
            self.insertSchema(g)

            # self.load()  this done in the verify step
            self.insertFiling(rssItem,g)
            self.insertDocuments(g)
            self.insertDataDictionary(g) # XML namespaces types aspects
            #self.insertRelationshipTypeSets()
            #self.insertResourceRoleSets()
            #self.insertAspectValues()
            self.modelXbrl.profileStat(_("XbrlSemanticRdfDB: DTS insertion"), time.time() - startedAt)
            startedAt = time.time()
            self.insertDataPoints(g)
            self.modelXbrl.profileStat(_("XbrlSemanticRdfDB: data points insertion"), time.time() - startedAt)
            startedAt = time.time()
            self.insertRelationshipSets(g)
            self.modelXbrl.profileStat(_("XbrlSemanticRdfDB: Relationships insertion"), time.time() - startedAt)
            self.insertValidationResults(g)
            self.modelXbrl.profileStat(_("XbrlSemanticRdfDB: Validation results insertion"), time.time() - startedAt)
            #startedAt = time.time()
            #self.insertValidCombinations()
            #self.modelXbrl.profileStat(_("XbrlSemanticRdfDB: Valid Combinations insertion"), time.time() - startedAt)
            self.showStatus("Committing entries")
            self.commit(g)
            self.modelXbrl.profileStat(_("XbrlSemanticRdfDB: insertion committed"), time.time() - startedAt)
            #finalVcount, finalEcount = self.getDBsize()
            #self.modelXbrl.modelManager.addToLog("added vertices: {0}, edges: {1}, total vertices: {2}, edges: {3}".format(
            #              finalVcount - initialVcount, finalEcount - initialEcount, finalVcount, finalEcount))
            self.showStatus("DB insertion completed", clearAfter=5000)
        except Exception as ex:
            self.showStatus("DB insertion failed due to exception", clearAfter=5000)
            raise

    def insertSchema(self, g):
        if True:  # if schema not defined
            self.showStatus("insert schema")
            # XML schema
            g.add( (XML.QName, RDF.type, RDFS.Class) )

            # Filings schema
            g.add( (XBRL.Filing, RDF.type, RDFS.Class) )

            g.add( (XML.Document, RDF.type, RDFS.Class) )
            g.add( (XBRL.Schema, RDFS.subClassOf, XML.Document) )
            g.add( (XBRL.Linkbase, RDFS.subClassOf, XML.Document) )
            g.add( (XBRL.Instance, RDFS.subClassOf, XML.Document) )
            g.add( (XBRL.InlineHtml, RDFS.subClassOf, XML.Document) )

            # Aspect schema

            # Relationships schema

            # DataPoints schema

    def insertFiling(self, rssItem, g):
        self.showStatus("insert filing")
        # accession graph -> document vertices
        new_filing = {}
        if self.modelXbrl.modelDocument.creationSoftwareComment:
            new_filing['creation_software'] = self.modelXbrl.modelDocument.creationSoftwareComment
        datetimeNow = datetime.datetime.now()
        datetimeNowStr = XmlUtil.dateunionValue(datetimeNow)
        entryUri = URIRef( modelObjectDocumentUri(self.modelXbrl) )
        if rssItem is not None:  # sec accession
            # set self.
            filingType = "SEC_filing"
            # for an RSS Feed entry from SEC, use rss item's accession information
            new_filing['filingNumber'] = filingNumber = rssItem.accessionNumber
            new_filing['acceptedTimestamp'] = XmlUtil.dateunionValue(rssItem.acceptanceDatetime)
            new_filing['filingDate'] = XmlUtil.dateunionValue(rssItem.filingDate)
            new_filing['entityId'] = rssItem.cikNumber
            new_filing['entityName'] = rssItem.companyName
            new_filing['SICCode'] = rssItem.assignedSic
            new_filing['SECHtmlUrl'] = rssItem.htmlUrl
            new_filing['entryUrl'] = URIRef( rssItem.url )
            self.filingDTS = rssItem.htmlUrl
            self.filingURI = URIRef( self.filingDTS )
        else:
            # not an RSS Feed item, make up our own accession ID (the time in seconds of epoch)
            intNow = int(time.time())
            new_filing['filingNumber'] = filingNumber = str(intNow)
            self.filingId = int(time.time())    # only available if entered from an SEC filing
            filingType = "independent_filing"
            new_filing['acceptedTimestamp'] = datetimeNowStr
            new_filing['filingDate'] = datetimeNowStr
            new_filing['entryUrl'] = URIRef( UrlUtil.ensureUrl(self.modelXbrl.fileSource.url) )
            self.filingDTS = Filing[filingNumber]
            self.filingURI = URIRef( self.filingDTS )

        g.add( (self.filingURI, RDF.type, XBRL.Filing) )
        for n, v in new_filing.items():
            g.add( (self.filingURI, Filing[n], L(v)) )

        # for now only one report per filing (but SEC may have multiple in future, such as form SD)
        self.reportURI = URIRef( modelObjectDocumentUri(self.modelXbrl) )
        g.add( (self.reportURI, RDF.type, XBRL.Report) )
        g.add( (self.filingURI, Filing.report, self.reportURI) )
        g.add( (self.reportURI, Filing.filing, self.filingURI) )

        # relationshipSets are a dts property
        self.relationshipSets = [(arcrole, ELR, linkqname, arcqname)
                                 for arcrole, ELR, linkqname, arcqname in self.modelXbrl.baseSets.keys()
                                 if ELR and (arcrole.startswith("XBRL-") or (linkqname and arcqname))]

    def identifyPreexistingDocuments(self):
        self.existingDocumentUris = set()
        if not (self.isRdfTurtleFile or self.isRdfXmlFile):
            docFilters = []
            for modelDocument in self.modelXbrl.urlDocs.values():
                if modelDocument.type == Type.SCHEMA:
                    docFilters.append('STR(?doc) = "{}"'.format(UrlUtil.ensureUrl(modelDocument.uri)))
            results = self.execute(
                "select",
                query="""
                    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                    PREFIX DTS: <http://xbrl.org/2013/rdf/DTS/>
                    SELECT distinct ?doc WHERE { ?doc rdf:type DTS:Document
                    FILTER( """ + '\n|| '.join(docFilters) + ") .}")
            try:
                for result in results['results']['bindings']:
                    doc = result['doc']
                    if doc.get('type') == 'uri':
                        self.existingDocumentUris.add(doc['value'])
            except KeyError:
                pass # no existingDocumentUris

    def insertDocuments(self, g):
        # filing->documents
        #
        self.showStatus("insert documents")
        documents = []
        for modelDocument in self.modelXbrl.urlDocs.values():
            docUri = URIRef( modelObjectDocumentUri(modelDocument) )
            if UrlUtil.ensureUrl(modelDocument.uri) not in self.existingDocumentUris:
                g.add( (docUri, RDF.type, XBRL.Document) )
                g.add( (docUri, XBRL.url, docUri ) )
                g.add( (docUri, XBRL.documentType, DocumentTypes.get(modelDocument.type,
                                                             DocumentTypes.get(Type.UnknownXML))) )
                for doc, ref in modelDocument.referencesDocument.items():
                    if doc.inDTS and ref.referenceTypes & {"href", "import", "include"}:
                        g.add( (docUri, XBRL.references, URIRef( modelObjectDocumentUri(doc) )) )
            g.add( (self.filingURI, Filing.document, docUri) )
            if modelDocument.uri == self.modelXbrl.modelDocument.uri: # entry document
                g.add( (self.reportURI, DTS.EntryPoint, docUri) )

    def conceptsUsed(self):
        conceptsUsed = set(f.qname for f in self.modelXbrl.factsInInstance)

        for cntx in self.modelXbrl.contexts.values():
            for dim in cntx.qnameDims.values():
                conceptsUsed.add(dim.dimensionQname)
                if dim.isExplicit:
                    conceptsUsed.add(dim.memberQname)
                else:
                    conceptsUsed.add(dim.typedMember.qname)
        for defaultDim, defaultDimMember in self.modelXbrl.qnameDimensionDefaults.items():
            conceptsUsed.add(defaultDim)
            conceptsUsed.add(defaultDimMember)
        for roleTypes in (self.modelXbrl.roleTypes, self.modelXbrl.arcroleTypes):
            for modelRoleTypes in roleTypes.values():
                for modelRoleType in modelRoleTypes:
                    for qn in modelRoleType.usedOns:
                        conceptsUsed.add(qn)
        for relationshipSetKey in self.relationshipSets:
            relationshipSet = self.modelXbrl.relationshipSet(*relationshipSetKey)
            for rel in relationshipSet.modelRelationships:
                if isinstance(rel.fromModelObject, ModelConcept):
                    conceptsUsed.add(rel.fromModelObject)
                if isinstance(rel.toModelObject, ModelConcept):
                    conceptsUsed.add(rel.toModelObject)
        for qn in (XbrlConst.qnXbrliIdentifier, XbrlConst.qnXbrliPeriod, XbrlConst.qnXbrliUnit):
            conceptsUsed.add(qn)

        conceptsUsed -= {None}  # remove None if in conceptsUsed
        return conceptsUsed

    def insertDataDictionary(self, g):
        # separate graph
        # document-> dataTypeSet -> dataType
        # do all schema dataTypeSet vertices

        self.type_id = {}
        self.aspect_id = {}
        self.aspect_proxy_uri = {}
        self.roleType_id = {}
        self.arcroleType_id = {}


        '''
        if any((not self.document_isNew[modelDocument.uri])
               for modelDocument in self.modelXbrl.urlDocs.values()):
            conceptsUsed = self.conceptsUsed()
        '''
        conceptsUsed = self.conceptsUsed()

        for modelDocument in self.modelXbrl.urlDocs.values():
            self.showStatus("insert DataDictionary " + modelDocument.basename)
            # don't re-output existing documents
            if modelDocument.type == Type.SCHEMA:
                isNewDocument = True # self.document_isNew[modelDocument.uri]
                modelConcepts = [modelConcept
                                 for modelConcept in self.modelXbrl.qnameConcepts.values()
                                 if modelConcept.modelDocument is modelDocument and
                                    (isNewDocument or modelConcept in conceptsUsed)]
                if UrlUtil.ensureUrl(modelDocument.uri) not in self.existingDocumentUris:
                    # adding document as new
                    for modelType in self.modelXbrl.qnameTypes.values():
                        if modelType.modelDocument is modelDocument:
                            typeUri = modelObjectUri(modelType)
                            typeQnameUri = qnameUri(modelType)
                            docUri = modelObjectDocumentUri(modelType)
                            g.add( (docUri, XBRL.dataType, typeUri) )
                            g.add( (typeUri, XBRL.document, docUri) )

                            g.add( (typeUri, RDF.type, XBRL.DataType) )
                            g.add( (typeUri, RDF.type, XBRL.QName) )
                            g.add( (typeUri, QName.namespace, L(modelDocument.targetNamespace)) )
                            g.add( (typeUri, QName.localName, L(modelType.name)) )

                            xbrliBaseType = modelType.baseXbrliTypeQname
                            if not isinstance(xbrliBaseType, (tuple,list)):
                                xbrliBaseType = (xbrliBaseType,)
                            for baseType in xbrliBaseType:
                                if baseType is not None:
                                    baseTypeUri = qnameUri(baseType)
                                    g.add( (typeUri,
                                            AspectType.baseXbrliType,
                                            baseTypeUri) )
                                    if baseType.namespaceURI == "http://www.w3.org/2001/XMLSchema":
                                        g.add( (typeUri, AspectType.baseXsdType, baseTypeUri) )

                            typeDerivedFrom = modelType.typeDerivedFrom
                            if not isinstance(typeDerivedFrom, (tuple,list)): # list if a union
                                typeDerivedFrom = (typeDerivedFrom,)
                            for dt in typeDerivedFrom:
                                if dt is not None:
                                    dtUri = modelObjectUri(dt)
                                    g.add( (typeUri, AspectType.derivedFrom, dtUri))

                            for prop in ('isTextBlock', 'isDomainItemType'):
                                propertyValue = getattr(modelType, prop, None)
                                if propertyValue:
                                    g.add( (typeUri, AspectType[prop], L(propertyValue)) )
                    conceptAspects = []
                    for modelConcept in modelConcepts:
                        conceptUri = modelObjectUri(modelConcept)
                        conceptQnameUri = modelObjectQnameUri(modelConcept)
                        docUri = modelObjectDocumentUri(modelConcept)
                        g.add( (docUri, XBRL.aspect, conceptUri) )
                        g.add( (conceptUri, XBRL.document, docUri) )

                        g.add( (conceptUri, RDF.type, XBRL.Aspect) )
                        g.add( (conceptUri, RDF.type, XBRL.QName) )
                        g.add( (conceptUri, QName.namespace, L(modelConcept.qname.namespaceURI)) )
                        g.add( (conceptUri, QName.localName, L(modelConcept.qname.localName)) )

                        g.add( (conceptUri, Aspect.isAbstract, L(modelConcept.isAbstract)) )
                        if modelConcept.periodType:
                            g.add( (conceptUri, Aspect.periodType, L(modelConcept.periodType)) )
                        if modelConcept.balance:
                            g.add( (conceptUri, Aspect.balance, L(modelConcept.balance)) )

                        for prop in ('isItem', 'isTuple', 'isLinkPart',
                                     'isNumeric', 'isMonetary', 'isExplicitDimension',
                                     'isDimensionItem', 'isPrimaryItem',
                                     'isTypedDimension', 'isDomainMember', 'isHypercubeItem',
                                     'isShares', 'isTextBlock', 'isNillable'):
                            propertyValue = getattr(modelConcept, prop, None)
                            if propertyValue:
                                g.add( (conceptUri, Aspect[prop], L(propertyValue)) )

                        conceptType = modelConcept.type
                        if conceptType is not None:
                            typeUri = modelObjectUri(conceptType)
                            g.add( (conceptUri, XBRL.dataType, typeUri) )

                        substitutionGroup = modelConcept.substitutionGroup
                        if substitutionGroup is not None:
                            sgUri = modelObjectUri(substitutionGroup)
                            g.add( (conceptUri, XBRL.substitutionGroup, sgUri) )
                    for modelRoleTypes in self.modelXbrl.roleTypes.values():
                        for modelRoleType in modelRoleTypes:
                            rtUri = modelObjectUri(modelRoleType)
                            docUri = modelObjectDocumentUri(modelRoleType)
                            g.add( (docUri, XBRL.roleType, rtUri) )
                            g.add( (rtUri, XBRL.document, docUri) )

                            g.add( (rtUri, RDF.type, DTS.RoleType) )
                            g.add( (rtUri, RoleType.roleUri, URIRef(modelRoleType.roleURI)) )
                            g.add( (rtUri, RoleType.definition, L(modelRoleType.definition)) )
                            #g.add( (rt_uri, LinkRoleType.cyclesAllowed, LinkRoleType.cycles[rt.cyclesAllowed or "none"]) )

                            for qn in modelRoleType.usedOns:
                                usedOnConcept = self.modelXbrl.qnameConcepts[qn]
                                g.add( (rtUri, RoleType.usedOn, modelObjectUri(usedOnConcept)) )
                                # note that QNames are defined in the documents that define the element
                    for modelArcroleTypes in self.modelXbrl.arcroleTypes.values():
                        for modelArcroleType in modelArcroleTypes:
                            rt_uri = modelObjectUri(modelArcroleType)
                            doc_uri = modelObjectDocumentUri(modelArcroleType)
                            g.add( (doc_uri, XBRL.arcroleType, rt_uri) )
                            g.add( (rtUri, XBRL.document, docUri) )

                            g.add( (rt_uri, RDF.type, DTS.ArcRoleType) )
                            g.add( (rt_uri, ArcRoleType.roleUri, URIRef(modelArcroleType.arcroleURI)) )
                            g.add( (rt_uri, ArcRoleType.definition, L(modelArcroleType.definition)) )
                            g.add( (rt_uri, ArcRoleType.cyclesAllowed, ArcRoleCycles[modelArcroleType.cyclesAllowed]) )

                            for qn in modelArcroleType.usedOns:
                                usedOnConcept = self.modelXbrl.qnameConcepts[qn]
                                g.add( (rt_uri, ArcRoleType.usedOn, modelObjectUri(usedOnConcept)) )
                    activity = "Insert data dictionary types, aspects, roles, and arcroles for " + modelDocument.uri


    '''
    def insertValidCombinations(self):
        # document-> validCombinationsSet-> cubes
        self.showStatus("insert ValidCombinations")

        drsELRs = set(ELR
                      for arcrole, ELR, linkqname, arcqname in self.modelXbrl.baseSets.values()
                      if arcrole == XbrlConst.all)
        hasHcRels = self.modelXbrl.relationshipSet(XbrlConst.all).modelRelationships
        hcConcepts = set(hasHcRel.toModelObject for hasHcRel in hasHcRels)

        # one cube region per head pri item with multiple cube regions
        for hcConcept in hcConcepts:
            # include any other concepts in this pri item with clean inheritance
            for drsELR in drsELRs:
                # each ELR is another cube region

        for allRel in val.modelXbrl.relationshipSet(XbrlConst.all, ELR)
        drsPriItems(val, fromELR, fromPriItem

        ... this becomes an unweildly large model, don't see a use case for compiling it out
'''
    def insertAspectProxies(self, qnames, g):
        aspectQnames = [qname
                        for qname in qnames
                        if qname not in self.aspect_proxy_uri and qname in self.modelXbrl.qnameConcepts]
        for qname in aspectQnames:
            self.insertAspectProxy(qname,
                                   URIRef( "{}/AspectProxy/{}".format(self.reportURI, qnamePrefix_Name(qname)) ),
                                   g)

    def insertAspectProxy(self, aspectQName, aspectProxyUri, g):
        concept = self.modelXbrl.qnameConcepts[aspectQName]
        g.add( (aspectProxyUri, RDF.type, DTS.AspectProxy) )
        g.add( (aspectProxyUri, DTS.aspect, modelObjectUri(concept) ) )
        g.add( (aspectProxyUri, DTS.report, self.reportURI ) )
        g.add( (self.reportURI, DTS.aspectProxy, aspectProxyUri ) )
        self.aspect_proxy_uri[aspectQName] = aspectProxyUri


    def aspectQnameProxyURI(self, qname):
        if hasattr(qname, "modelDocument"):
            return self.aspect_proxy_uri.get(qname.qname)
        elif qname in self.modelXbrl.qnameConcepts:
            return self.aspect_proxy_uri.get(qname)
        return None

    def insertDataPoints(self, g):
        # separate graph
        # document-> dataTypeSet -> dataType
        self.showStatus("insert DataPoints")

        # note these initial aspects Qnames used also must be in conceptsUsed above
        dimensions = [] # index by hash of dimension
        dimensionIds = {}  # index for dimension
        if self.modelXbrl.modelDocument.type in (Type.INSTANCE, Type.INLINEXBRL):
            contextAspectValueSelections = {}  # contexts processed already
            unitIDs = set()  # units processed already
            periodURIs = {}
            entityIdentifierURIs = {}
            for fact in self.modelXbrl.factsInInstance:
                factUri = modelObjectUri(fact)
                docUri = modelObjectDocumentUri(fact)
                baseXsdType = fact.concept.baseXsdType if fact.concept is not None else None

                g.add( (factUri, RDF.type, XBRL.DataPoint) )
                g.add( (docUri, XBRL.dataPoint, factUri) )
                g.add( (factUri, XBRL.document, docUri) )
                self.insertAspectProxies( (fact.qname,), g )
                g.add( (factUri, XBRL.baseItem, self.aspectQnameProxyURI(fact.qname) ) )

                # fact related to aspectProxy below
                g.add( (factUri, XML.id, L(XmlUtil.elementFragmentIdentifier(fact))) )
                g.add( (factUri, XML.sourceLine, L(fact.sourceline)) )
                context = fact.context
                concept = fact.concept
                if context is not None:
                    if context.entityIdentifier not in entityIdentifierURIs:
                        entityScheme, entityIdentifier = context.entityIdentifier
                        entityIdentifierUri = URIRef( "{}/AspectProxy/{}/{}".format(
                                                      self.reportURI,
                                                      qnamePrefix_Name(XbrlConst.qnXbrliIdentifier),
                                                      entityIdentifier) )
                        self.insertAspectProxy(XbrlConst.qnXbrliIdentifier, entityIdentifierUri, g)
                        g.add( (entityIdentifierUri, RDF.type, DTS.EntityIdentifier) )
                        g.add( (entityIdentifierUri, XBRLI.scheme, L(entityScheme)) )
                        g.add( (entityIdentifierUri, XBRLI.identifier, L(entityIdentifier)) )
                        entityIdentifierURIs[context.entityIdentifier] = entityIdentifierUri
                    else:
                        entityIdentifierUri = entityIdentifierURIs[context.entityIdentifier]
                    g.add( (factUri, XBRLI.EntityIdentifier, entityIdentifierUri ) )

                    if context.isForeverPeriod:
                        period = "forever"
                    if context.isInstantPeriod:
                        endDate = XmlUtil.dateunionValue(context.instantDatetime, subtractOneDay=True).replace(':','_')
                        period = "instant/{}".format(endDate)
                    else:
                        startDate = XmlUtil.dateunionValue(context.startDatetime).replace(':','_')
                        endDate = XmlUtil.dateunionValue(context.endDatetime, subtractOneDay=True).replace(':','_')
                        period = "duration/{}/{}".format(startDate, endDate)
                    if period not in periodURIs:
                        periodUri = URIRef( "{}/AspectProxy/{}".format(self.reportURI, period) )
                        self.insertAspectProxy(XbrlConst.qnXbrliPeriod, periodUri, g)
                        g.add( (periodUri, RDF.type, DTS.Period) )
                        g.add( (periodUri, XBRL.isForever, L(context.isForeverPeriod)) )
                        g.add( (periodUri, XBRL.isInstant, L(context.isInstantPeriod)) )
                        if context.isStartEndPeriod:
                            d = context.startDatetime
                            if d.hour == 0 and d.minute == 0 and d.second == 0:
                                d = d.date()
                            g.add( (periodUri, XBRLI.startDate, L(d)) )
                        if context.isStartEndPeriod or context.isInstantPeriod:
                            d = context.endDatetime
                            if d.hour == 0 and d.minute == 0 and d.second == 0:
                                d = (d - datetime.timedelta(1)).date()
                            g.add( (periodUri, XBRLI.endDate, L(d)) )
                        periodURIs[period] = periodUri
                    else:
                        periodUri = periodURIs[period]
                    g.add( (factUri, XBRLI.Period, periodUri ) )

                    contextUri = modelObjectUri(context)
                    g.add( (factUri, XBRLI.contextId, L(context.id) ) )
                    if context.id not in contextAspectValueSelections:
                        contextAspectValueSelection = []
                        contextAspectValueSelections[context.id] = contextAspectValueSelection

                        for dimVal in context.qnameDims.values():
                            dimUri = modelObjectUri(dimVal)
                            self.insertAspectProxy(dimVal.dimensionQname, dimUri, g)
                            g.add( (dimUri, RDF.type, DTS.AspectValueSelection) )
                            contextAspectValueSelection.append(dimUri)
                            if dimVal.isExplicit:
                                self.insertAspectProxies( (dimVal.memberQname,), g)  # need imediate use of proxy
                                g.add( (dimUri, XBRLI.AspectValue, self.aspectQnameProxyURI(dimVal.memberQname) ) )
                            else:
                                g.add( (dimUri, DTS.typedValue, L(dimVal.typedMember.stringValue) ) )
                    else:
                        contextAspectValueSelection = contextAspectValueSelections[context.id]
                        for aspectValueSelectionUri in contextAspectValueSelection:
                            g.add( (factUri, XBRLI.aspectValueSelection, aspectValueSelectionUri) )
                    if fact.isNumeric:
                        if fact.precision == "INF":
                            g.add( (factUri, XBRLI.precision, L("INF")) )
                        elif fact.precision is not None:
                            g.add( (factUri, XBRLI.precision, L(fact.precision, datatype=XSD.integer)) )
                        if fact.decimals == "INF":
                            g.add( (factUri, XBRLI.decimals, L("INF")) )
                        elif fact.decimals is not None:
                            g.add( (factUri, XBRLI.decimals, L(fact.decimals, datatype=XSD.integer)) )
                        if fact.unit is not None:
                            unit = fact.unit
                            unitUri = modelObjectUri(unit)
                            g.add( (factUri, XBRLI.unit, unitUri) )
                            g.add( (factUri, XBRLI.unitId, L(unit.id)) )
                            if unit.id not in unitIDs:
                                unitIDs.add(unit.id)
                                self.insertAspectProxy(XbrlConst.qnXbrliUnit, unitUri, g)
                                g.add( (unitUri, RDF.type, DTS.Unit) )
                                g.add( (docUri, XBRL.defines, unitUri) )

                                mults, divs = unit.measures
                                for qn in mults:
                                    qnUri = qnameUri(qn)
                                    g.add( (unitUri, Unit.multiply, qnUri) )
                                    g.add( (qnUri, RDF.type, XBRL.Measure) )
                                    #if qn not in dumped_qnames:
                                    #    g = dump_xbrl_qname(qn, g)
                                    #    dumped_qnames.add(qn)
                                for qn in divs:
                                    qnUri = qnameUri(qn)
                                    g.add( (unitUri, Unit.divide, qnUri) )
                                    g.add( (qnUri, RDF.type, XBRL.Measure) )
                                    #if qn not in dumped_qnames:
                                    #    g = dump_xbrl_qname(qn, g)
                                    #    dumped_qnames.add(qn)
                    if fact.xmlLang is None and fact.concept is not None and fact.concept.baseXsdType is not None:
                        # The insert with base XSD type but no language
                        g.add( (factUri, DataPoint.value, L(fact.xValue, datatype=XSD[concept.baseXsdType])))
                    elif fact.xmlLang is not None:
                        # assuming string type with language
                        g.add( (factUri, DataPoint.value, L(fact.value, lang=fact.xmlLang)) )
                    else:
                        # Otherwise insert as plain liternal with no language or datatype
                        g.add( (factUri, DataPoint.value, L(fact.value)) )

                    if fact.modelTupleFacts:
                        g.add( (factUri, RDF.type, XBRL.tuple) )
                        for tupleFact in fact.modelTupleFacts:
                            g.add( (factUri, XBRLI.tuple, modelObjectUri(tupleFact)) )


        if self.modelXbrl.modelDocument.type in (Type.INSTANCE, Type.INLINEXBRL):
            for fact in self.modelXbrl.factsInInstance:
                factUri = modelObjectUri(fact)


    def insertRelationshipSets(self, g):
        self.showStatus("insert relationship sets")
        entryUrl = URIRef( modelObjectDocumentUri(self.modelXbrl) )
        aspectQnamesUsed = set()
        for i, relationshipSetKey in enumerate(self.relationshipSets):
            arcrole, linkrole, linkqname, arcqname = relationshipSetKey
            if linkqname:
                aspectQnamesUsed.add(linkqname)
            if arcqname:
                aspectQnamesUsed.add(arcqname)
        self.insertAspectProxies(aspectQnamesUsed, g)

        relSetURIs = {}
        for i, relationshipSetKey in enumerate(self.relationshipSets):
            arcrole, linkrole, linkqname, arcqname = relationshipSetKey
            if arcrole not in ("XBRL-formulae", "Table-rendering", "XBRL-footnotes") and linkrole and linkqname and arcqname:
                # skip paths and qnames for now (add later for non-SEC)
                relSetUri = URIRef("{}/RelationshipSet/{}/{}".format(
                                   self.filingURI,
                                   os.path.basename(arcrole),
                                   os.path.basename(linkrole)) )
                relSetURIs[relationshipSetKey] = relSetUri
                g.add( (relSetUri, RDF.type, XBRL.RelationshipSet) )
                g.add( (relSetUri, XBRL.arcrole, L(arcrole)) )
                g.add( (relSetUri, XBRL.linkrole, L(linkrole)) )
                g.add( (relSetUri, XBRL.arcname, self.aspectQnameProxyURI(arcqname)) )
                g.add( (relSetUri, XBRL.linkname, self.aspectQnameProxyURI(linkqname)) )
                g.add( (self.reportURI, XBRL.relationshipSet, relSetUri) )
                g.add( (relSetUri, XBRL.report, self.reportURI) )


        # do tree walk to build relationships with depth annotated, no targetRole navigation
        relE = [] # fromV, toV, label
        resources = set()
        aspectQnamesUsed = set()

        def walkTree(rels, parentRelUri, seq, depth, relationshipSetKey, relationshipSet, visited, relSetUri, doVertices):
            for rel in rels:
                if rel not in visited:
                    visited.add(rel)

                    if not doVertices:
                        _relProp = {'seq': L(seq),
                                    'depth': L(depth),
                                    'order': L(rel.orderDecimal),
                                    'priority': L(rel.priority),
                                    'relSet': relSetUri
                                    }
                    if isinstance(rel.fromModelObject, ModelConcept):
                        if doVertices:
                            aspectQnamesUsed.add(rel.fromModelObject.qname)
                            sourceUri = True
                        else:
                            sourceUri = self.aspectQnameProxyURI(rel.fromModelObject.qname)
                            sourceId = qnamePrefix_Name(rel.fromModelObject.qname)
                    else:
                        sourceUri = None # tbd
                    toModelObject = rel.toModelObject
                    if isinstance(toModelObject, ModelConcept):
                        if doVertices:
                            aspectQnamesUsed.add(toModelObject.qname)
                            targetUri = True
                        else:
                            targetUri = self.aspectQnameProxyURI(toModelObject.qname)
                            targetId = qnamePrefix_Name(toModelObject.qname)
                    elif isinstance(toModelObject, ModelResource):
                        if doVertices:
                            resources.add(toModelObject)
                            targetUri = 0 # just can't be None, but doesn't matter on doVertices pass
                        else:
                            if rel.preferredLabel:
                                _relProp['preferredLabel'] = URIRef(rel.preferredLabel)
                            if rel.arcrole in (XbrlConst.all, XbrlConst.notAll):
                                _relProp['cubeClosed'] = L(rel.closed)
                            elif rel.arcrole in (XbrlConst.dimensionDomain, XbrlConst.domainMember):
                                _relProp['aspectValueUsable'] = L(rel.usable)
                            elif rel.arcrole == XbrlConst.summationItem:
                                _relProp['weight'] = L(rel.weightDecimal)
                            if relationshipSet.arcrole == "XBRL-dimensions":
                                _relProp['arcrole'] = URIRef(rel.arcrole)
                            if toModelObject.role:
                                _relProp['resourceRole'] = URIRef(toModelObject.role)
                            targetUri = modelObjectUri(toModelObject)
                            targetId = toModelObject.modelDocument.basename + '#' + XmlUtil.elementFragmentIdentifier(toModelObject)
                    else:
                        targetUri = None # tbd
                    if sourceUri is not None and targetUri is not None:
                        targetRelSetUri = relSetUri
                        targetRelSetKey = relationshipSetKey
                        if relationshipSet.arcrole == "XBRL-dimensions" and rel.targetRole:
                            targetRelSet = self.modelXbrl.relationshipSet(relationshipSet.arcrole, rel.targetRole)
                            for i, relSetKey in enumerate(self.relationshipSets):
                                arcrole, ELR, linkqname, arcqname = relSetKey
                                if arcrole == "XBRL-dimensions" and ELR == rel.targetRole:
                                    targetRelationshipSetUri = relSetURIs[relSetKey]
                                    targetRelSetKey = relSetKey
                                    break
                            if not doVertices:
                                _relProp['targetLinkrole'] = URIRef(rel.targetRole)
                                _relProp['targetRelSet'] = URIRef(targetRelationshipSetUri)
                        else:
                            targetRelSetKey = relationshipSetKey
                            targetRelSet = relationshipSet
                        if doVertices:
                            relUri = None
                        else:
                            _relProp['from'] = sourceUri
                            _relProp['to'] = targetUri
                            _arcrole = os.path.basename(rel.arcrole)
                            relUri = URIRef("{}/Relationship/{}/{}/{}/{}".format(
                                            self.reportURI,
                                            _arcrole,
                                            os.path.basename(rel.linkrole),
                                            sourceId,
                                            targetId) )
                            _relProp['relURI'] = relUri
                            relPredNS = Namespace("http://xbrl.org/2013/rdf/DTS/Relationship/{}/"
                                                  .format(_arcrole))
                            g.bind(_arcrole, relPredNS)
                            _relProp['relPredicate'] = relPredNS[os.path.basename(rel.linkrole)]
                            if parentRelUri is not None:
                                g.add( (parentRelUri, Relationship.child, relUri) )
                            _relProp['relSetKey'] = relationshipSetKey

                            relE.append(_relProp)
                        seq += 1
                        seq = walkTree(targetRelSet.fromModelObject(toModelObject), relUri, seq, depth+1, targetRelSetKey, targetRelSet, visited, targetRelSetUri, doVertices)
                    visited.remove(rel)
            return seq


        for doVertices in range(1,-1,-1):  # pass 0 = vertices, pass 1 = edges
            for i, relationshipSetKey in enumerate(self.relationshipSets):
                arcrole, linkrole, linkqname, arcqname = relationshipSetKey
                if arcrole not in ("XBRL-formulae", "Table-rendering", "XBRL-footnotes") and linkrole and linkqname and arcqname:
                    relSetUri = relSetURIs[relationshipSetKey]
                    relationshipSet = self.modelXbrl.relationshipSet(*relationshipSetKey)
                    seq = 1
                    for rootConcept in relationshipSet.rootConcepts:
                        seq = walkTree(relationshipSet.fromModelObject(rootConcept), None, seq, 1, relationshipSetKey, relationshipSet, set(), relSetUri, doVertices)
            if doVertices:
                if resources:
                    for resource in resources:
                        resourceUri = modelObjectUri(resource)
                        g.add( (resourceUri, RDF.type, XBRL.resource) )
                        g.add( (resourceUri, XBRL.value, L(resource.stringValue)) )
                        if resource.role:
                            g.add( (resourceUri, XBRL.role, L(resource.role)) )

                self.insertAspectProxies(aspectQnamesUsed, g)
            else:
                for j, rel in enumerate(relE):
                    relUri = rel['relURI']
                    g.add( (rel['from'], rel['relPredicate'], rel['to']) )
                    g.add( (relUri, RDF.type, XBRL.relationship) )
                    relSetUri = relSetURIs[rel['relSetKey']]
                    g.add( (relUri, XBRL.relSet, relSetUri) )
                    g.add( (relSetUri, XBRL.relationship, relUri) )
                    if rel.get('depth', 0) == 1:
                        g.add( (relSetUri, XBRL.root, relUri) )
                    for k,v in rel.items():
                        if k not in ('relURI', 'relPredicate', 'relSetKey'):
                            g.add( (relUri, Relationship[k], v) )

                # TBD: do we want to link resources to the dts (by role, class, or otherwise?)

        resources = None

    def insertValidationResults(self, g):
        logEntries = []
        for handler in logging.getLogger("arelle").handlers:
            if hasattr(handler, "dbHandlerLogEntries"):
                logEntries = handler.dbHandlerLogEntries()
                break

        messages = []
        messageRefs = [] # direct link to objects
        firstLogMessage = True
        for i, logEntry in enumerate(logEntries):
            if firstLogMessage:
                self.showStatus("insert validation messages")
                firstLogMessage = False
            messageUri = URIRef("{}/Message/{}".format(self.reportURI, i+1))
            g.add( (messageUri, RDF.type, XBRL.Message) )
            g.add( (messageUri, XBRL.code, L(logEntry['code'])) )
            g.add( (messageUri, XBRL.level, L(logEntry['level'])) )
            g.add( (messageUri, XBRL.value, L(logEntry['message']['text'])) )
            g.add( (messageUri, XBRL.report, self.reportURI) )
            g.add( (self.reportURI, XBRL.message, messageUri) )
            # capture message ref's
            for ref in logEntry['refs']:
                modelObject = self.modelXbrl.modelObject(ref.get('objectId',''))
                # for now just find a concept
                aspectObj = None
                if isinstance(modelObject, ModelFact):
                    objUri = modelObjectUri(modelObject)
                elif isinstance(modelObject, ModelConcept):
                    # be sure there's a proxy
                    self.insertAspectProxies( (modelObject.qname,), g)  # need imediate use of proxy
                    objUri = self.aspectQnameProxyURI(modelObject.qname)
                elif isinstance(modelObject, ModelRelationship):
                    sourceId = qnamePrefix_Name(modelObject.fromModelObject.qname)
                    toModelObject = modelObject.toModelObject
                    if isinstance(toModelObject, ModelConcept):
                        targetId = qnamePrefix_Name(toModelObject.qname)
                    elif isinstance(toModelObject, ModelResource):
                        targetId = toModelObject.modelDocument.basename + '#' + XmlUtil.elementFragmentIdentifier(toModelObject)
                    else:
                        continue
                    objUri = URIRef("{}/Relationship/{}/{}/{}/{}".format(
                                    self.reportURI,
                                    os.path.basename(modelObject.arcrole),
                                    os.path.basename(modelObject.linkrole),
                                    sourceId,
                                    targetId) )
                else:
                    continue
                g.add( (objUri, XBRL.ref, messageUri) )
                g.add( (messageUri, XBRL.message, objUri) )
