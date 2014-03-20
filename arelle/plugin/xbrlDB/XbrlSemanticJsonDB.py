'''
XbrlSemanticJsonDB.py implements an JSON database interface for Arelle, based
on a concrete realization of the Abstract Model PWD 2.0 layer.  This is a semantic 
representation of XBRL information. 

This module may save directly to a JSON Server (TBD) or to append to a file of JSON.

This module provides the execution context for saving a dts and instances in 
XBRL JSON graph.  It may be loaded by Arelle's RSS feed, or by individual
DTS and instances opened by interactive or command line/web service mode.

Example dialog or command line parameters for operation:

    host:  the supporting host for JSON Server or "jsonFile" to append to a JSON file
    port:  the host port (80 is default) if a JSON Server
    user, password:  if needed for server
    database:  the top level path segment for the JSON Server or disk file path if jsonFile
    timeout: 
    

(c) Copyright 2013 Mark V Systems Limited, California US, All rights reserved.  
Mark V copyright applies to this software, which is licensed according to the terms of Arelle(r).

to do:

1) add AMTF cube regions (dimensions)
    HF - don't believe this is either feasible or has a use case in a graph model
2) check existence of (shared) documents and contained elements before adding
3) tuple structure declaration (particles in elements of data dictionary?)
4) tuple structure (instance facts)
5) add footnote resources to relationships (and test with EDInet footnote references)
6) test some filings with text blocks (shred them?)  (30mB - 50mB sized text blocks?)
7) add mappings to, or any missing relationships, of Charlie's financial model


'''

import os, io, time, json, socket, logging, zlib, datetime
from arelle.ModelDtsObject import ModelConcept, ModelResource, ModelRelationship
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelDocument import Type
from arelle import XbrlConst, XmlUtil, UrlUtil
import urllib.request
from urllib.error import HTTPError, URLError
from lxml import etree
from decimal import Decimal
import datetime

TRACEJSONFILE = None
#TRACEJSONFILE = r"c:\temp\jsonDBtrace.log"  # uncomment to trace JSON on connection (very big file!!!)

JSONFILE_HOSTNAME = "jsonFile"

def insertIntoDB(modelXbrl, 
                 user=None, password=None, host=None, port=None, database=None, timeout=None,
                 product=None, rssItem=None, **kwargs):
    jsondb = None
    try:
        jsondb = XbrlSemanticJsonDatabaseConnection(modelXbrl, user, password, host, port, database, timeout)
        jsondb.insertXbrl(rssItem=rssItem)
        jsondb.close()
    except Exception as ex:
        if jsondb is not None:
            try:
                jsondb.close(rollback=True)
            except Exception as ex2:
                pass
        raise # reraise original exception with original traceback    
    
def isDBPort(host, port, db, timeout=10):
    if host == JSONFILE_HOSTNAME:
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

# top level JSON Graph object keynames
FILINGS = "filings"
DOCUMENTS = "documents"
 
def modelObjectDocumentUri(modelObject):
    return UrlUtil.ensureUrl(modelObject.modelDocument.uri)
 
def modelObjectUri(modelObject):
    return '#'.join((modelObjectDocumentUri(modelObject), 
                     XmlUtil.elementFragmentIdentifier(modelObject)))
 
def qnameUri(qname, sep='#'):
    return sep.join((qname.namespaceURI, qname.localName))
 
def qnamePrefix_Name(qname, sep=':'):
    # substitutte standard prefixes for commonly-defaulted xmlns namespaces
    prefix = {XbrlConst.xsd: 'xsd',
              XbrlConst.xml: 'xml',
              XbrlConst.xbrli: 'xbrli',
              XbrlConst.link: 'link',
              XbrlConst.gen: 'gen',
              XbrlConst.xlink: 'xlink'
              }.get(qname.namespaceURI, qname.prefix)
    return sep.join((prefix, qname.localName))
 
def modelObjectQnameUri(modelObject, sep='#'):
    return qnameUri(modelObject.qname, sep)

def modelObjectNameUri(modelObject, sep='#'):
    return '#'.join((modelObjectDocumentUri(modelObject), 
                     modelObject.name)) # for schema definitions with name attribute

class XJDBException(Exception):
    def __init__(self, code, message, **kwargs ):
        self.code = code
        self.message = message
        self.kwargs = kwargs
        self.args = ( self.__repr__(), )
    def __repr__(self):
        return _('[{0}] exception: {1}').format(self.code, self.message % self.kwargs)
            
def jsonDefaultEncoder(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, (datetime.date, datetime.datetime)):
        return XmlUtil.dateunionValue(obj)
    raise TypeError("Type {} is not supported for json output".format(type(obj).__name__))

class XbrlSemanticJsonDatabaseConnection():
    def __init__(self, modelXbrl, user, password, host, port, database, timeout):
        self.modelXbrl = modelXbrl
        self.disclosureSystem = modelXbrl.modelManager.disclosureSystem
        #self.conn = RexProConnection(host, int(port or '8182'), (database or 'emptygraph'),
        #                             user=user, password=password)
        self.isJsonFile = host == JSONFILE_HOSTNAME
        if self.isJsonFile:
            self.jsonFile = database
        else:
            connectionUrl = "http://{0}:{1}".format(host, port or '80')
            self.url = connectionUrl + '/' + database
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
            if not self.isJsonFile:
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
        
    def execute(self, activity, graph=None, query=None):
        if graph is not None:
            headers = {'User-agent':   'Arelle/1.0',
                       'Accept':       'application/json',
                       'Content-Type': "text/json; charset='UTF-8'"}
            data = _STR_UNICODE(json.dumps(graph, 
                                           sort_keys=True,  # allow comparability of json files
                                           ensure_ascii=False, 
                                           indent=2, 
                                           default=jsonDefaultEncoder)) # might not be unicode in 2.7
        elif query is not None:
            headers = {'User-agent':   'Arelle/1.0',
                       'Accept':       'application/json'}
            data = ("query=" + query)
        else:
            return None
        # turtle may be mixture of line strings and strings with \n-separated lines
        if TRACEJSONFILE:
            with io.open(TRACEJSONFILE, 'at', encoding='utf-8') as fh:
                fh.write("\n\n>>> sent: \n")
                fh.write(data)
        if self.isJsonFile and data is not None:
            with io.open(self.jsonFile, 'at', encoding='utf-8') as fh:
                fh.write(data)
            return None
        if graph is not None or query is not None:
            url = self.url + "/json"
        request = urllib.request.Request(url,
                                         data=data.encode('utf-8'),
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
        if TRACEJSONFILE:
            with io.open(TRACEJSONFILE, "a", encoding='utf-8') as fh:
                fh.write("\n\n>>> received: \n{0}".format(str(results)))
        if isinstance(results, str) and query is not None:
            parser = etree.HTMLParser()
            htmlDoc = etree.parse(io.StringIO(results), parser)
            body = htmlDoc.find("//body")
            if body is not None:
                error = "".join(text for text in body.itertext())
            else:
                error = results
            raise XJDBException("jsonDB:DatabaseError",
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
            
            g = {FILINGS:{},
                 DOCUMENTS:{}}
            self.insertSchema(g)
            
            # self.load()  this done in the verify step
            self.insertFiling(rssItem,g)
            self.insertDocuments(g)
            self.insertDataDictionary() # XML namespaces types aspects
            #self.insertRelationshipTypeSets()
            #self.insertResourceRoleSets()
            #self.insertAspectValues()
            self.modelXbrl.profileStat(_("XbrlSemanticJsonDB: DTS insertion"), time.time() - startedAt)
            startedAt = time.time()
            self.insertDataPoints()
            self.modelXbrl.profileStat(_("XbrlSemanticJsonDB: data points insertion"), time.time() - startedAt)
            startedAt = time.time()
            self.insertRelationshipSets()
            self.modelXbrl.profileStat(_("XbrlSemanticJsonDB: Relationships insertion"), time.time() - startedAt)
            self.insertValidationResults()
            self.modelXbrl.profileStat(_("XbrlSemanticJsonDB: Validation results insertion"), time.time() - startedAt)
            #startedAt = time.time()
            #self.insertValidCombinations()
            #self.modelXbrl.profileStat(_("XbrlSemanticJsonDB: Valid Combinations insertion"), time.time() - startedAt)
            self.showStatus("Committing entries")
            self.commit(g)
            self.modelXbrl.profileStat(_("XbrlSemanticJsonDB: insertion committed"), time.time() - startedAt)
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
            # Filings schema

            # Aspect schema
            
            # Relationships schema
            
            # DataPoints schema
        
    def insertFiling(self, rssItem, g):
        self.showStatus("insert filing")
        # accession graph -> document vertices
        new_filing = {'documents': []}
        if self.modelXbrl.modelDocument.creationSoftwareComment:
            new_filing['creation_software'] = self.modelXbrl.modelDocument.creationSoftwareComment
        datetimeNow = datetime.datetime.now()
        datetimeNowStr = XmlUtil.dateunionValue(datetimeNow)
        entryUri = modelObjectDocumentUri(self.modelXbrl)
        if rssItem is not None:  # sec accession
            # set self.
            new_filing['filingType'] = "SEC filing"
            # for an RSS Feed entry from SEC, use rss item's accession information
            new_filing['filingNumber'] = filingNumber = rssItem.accessionNumber
            new_filing['acceptedTimestamp'] = XmlUtil.dateunionValue(rssItem.acceptanceDatetime)
            new_filing['filingDate'] = XmlUtil.dateunionValue(rssItem.filingDate)
            new_filing['entityId'] = rssItem.cikNumber
            new_filing['entityName'] = rssItem.companyName
            new_filing['SICCode'] = rssItem.assignedSic 
            new_filing['SECHtmlUrl'] = rssItem.htmlUrl 
            new_filing['entryUrl'] = rssItem.url
            self.filingURI = rssItem.htmlUrl
        else:
            # not an RSS Feed item, make up our own accession ID (the time in seconds of epoch)
            intNow = int(time.time())
            new_filing['filingNumber'] = filingNumber = str(intNow)
            self.filingId = int(time.time())    # only available if entered from an SEC filing
            new_filing['filingType'] = "independent filing"
            new_filing['acceptedTimestamp'] = datetimeNowStr
            new_filing['filingDate'] = datetimeNowStr
            new_filing['entryUrl'] = UrlUtil.ensureUrl(self.modelXbrl.fileSource.url)
            self.filingURI = filingNumber
            
        g[FILINGS][self.filingURI] = new_filing
        self.filing = new_filing
            
        # for now only one report per filing (but SEC may have multiple in future, such as form SD)
        self.reportURI = modelObjectDocumentUri(self.modelXbrl)
        self.report = {'filing': self.filingURI,
                       'aspectProxies': {},
                       'relationshipSets': {},
                       'dataPoints': {},
                       'messages': {}}
        new_filing['reports'] = {self.reportURI: self.report}
            
        # relationshipSets are a dts property
        self.relationshipSets = [(arcrole, ELR, linkqname, arcqname)
                                 for arcrole, ELR, linkqname, arcqname in self.modelXbrl.baseSets.keys()
                                 if ELR and (arcrole.startswith("XBRL-") or (linkqname and arcqname))]
        
    def identifyPreexistingDocuments(self):
        self.existingDocumentUris = set()
        if not self.isJsonFile:
            docFilters = []
            for modelDocument in self.modelXbrl.urlDocs.values():
                if modelDocument.type == Type.SCHEMA:
                    docFilters.append('STR(?doc) = "{}"'.format(UrlUtil.ensureUrl(modelDocument.uri)))
            results = self.execute(
                # TBD: fix up for Mongo DB query
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
        
    def insertDocuments(self,g):
        # accession->documents
        # 
        self.showStatus("insert documents")
        documents = self.documents = g[DOCUMENTS]
        for modelDocument in self.modelXbrl.urlDocs.values():
            docUri = modelObjectDocumentUri(modelDocument)
            if docUri not in self.existingDocumentUris:
                documents[docUri] = {
                    'url': docUri,
                    'documentType': Type.typeName[modelDocument.type],
                    'references': [modelObjectDocumentUri(doc)
                                   for doc, ref in modelDocument.referencesDocument.items()
                                   if doc.inDTS and ref.referenceType in ("href", "import", "include")],
                    'resources': {}
                    }
            self.filing['documents'].append(docUri)
            if modelDocument.uri == self.modelXbrl.modelDocument.uri: # entry document
                self.report['entryPoint'] = docUri
                
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

    def insertDataDictionary(self):
        # separate graph
        # document-> dataTypeSet -> dataType
        # do all schema dataTypeSet vertices
            
        self.type_id = {}
        self.aspect_id = {}
        self.aspect_proxy = {}
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
            docUri = modelObjectDocumentUri(modelDocument)
            document = self.documents[docUri]
            # don't re-output existing documents
            if modelDocument.type == Type.SCHEMA:
                isNewDocument = True # self.document_isNew[modelDocument.uri]
                modelConcepts = [modelConcept
                                 for modelConcept in self.modelXbrl.qnameConcepts.values()
                                 if modelConcept.modelDocument is modelDocument and
                                    (isNewDocument or modelConcept in conceptsUsed)]
                if docUri not in self.existingDocumentUris:
                    # adding document as new
                    document['dataTypes'] = dataTypes = {}
                    for modelType in self.modelXbrl.qnameTypes.values():
                        if modelType.modelDocument is modelDocument:
                            dataTypes[modelType.name] = dataType = {
                                'dataType': modelObjectNameUri(modelType),
                                'document': modelObjectDocumentUri(modelType),
                                'url': modelObjectUri(modelType),
                                'namespaceURI': modelType.qname.namespaceURI,
                                'localName': modelType.name,
                                }
                            xbrliBaseType = modelType.baseXbrliTypeQname
                            if not isinstance(xbrliBaseType, (tuple,list)):
                                xbrliBaseType = (xbrliBaseType,)
                            for baseType in xbrliBaseType:
                                if baseType is not None:
                                    dataType['baseType'] = qnameUri(baseType)
                                    if baseType.namespaceURI == "http://www.w3.org/2001/XMLSchema":
                                        dataType['baseXsdType'] = qnameUri(baseType)
                     
                            typeDerivedFrom = modelType.typeDerivedFrom
                            if not isinstance(typeDerivedFrom, (tuple,list)): # list if a union
                                typeDerivedFrom = (typeDerivedFrom,)
                            for dt in typeDerivedFrom:
                                if dt is not None:
                                    dataType['derivedFrom'] = modelObjectNameUri(dt)
                     
                            for prop in ('isTextBlock', 'isDomainItemType'):
                                propertyValue = getattr(modelType, prop, None)
                                if propertyValue:
                                    dataType[prop] = propertyValue
                    document['aspects'] = aspects = {}
                    for modelConcept in modelConcepts:
                        aspects[modelConcept.name] = aspect = {
                            'document': modelObjectDocumentUri(modelConcept),
                            'url': modelObjectUri(modelConcept),
                            'namespaceURI': modelConcept.qname.namespaceURI,
                            'localName': modelConcept.name,
                            'isAbstract': modelConcept.isAbstract
                            }
                        if modelConcept.periodType:
                            aspect['periodType'] = modelConcept.periodType
                        if modelConcept.balance:
                            aspect['balance'] = modelConcept.balance
                 
                        for prop in ('isItem', 'isTuple', 'isLinkPart', 
                                     'isNumeric', 'isMonetary', 'isExplicitDimension', 
                                     'isDimensionItem', 'isPrimaryItem',
                                     'isTypedDimension', 'isDomainMember', 'isHypercubeItem',
                                     'isShares', 'isTextBlock', 'isNillable'):
                            propertyValue = getattr(modelConcept, prop, None)
                            if propertyValue:
                                aspect[prop] = propertyValue
                 
                        conceptType = modelConcept.type
                        if conceptType is not None:
                            aspect['dataType'] = modelObjectNameUri(conceptType)
                        
                        substitutionGroup = modelConcept.substitutionGroup
                        if substitutionGroup is not None:
                            aspect['substitutionGroup'] = modelObjectNameUri(substitutionGroup)
                    document['roleTypes'] = roleTypes = {}
                    for modelRoleTypes in self.modelXbrl.roleTypes.values():
                        for modelRoleType in modelRoleTypes:
                            roleTypes[modelRoleType.roleURI] = roleType = {
                                'document': modelObjectDocumentUri(modelRoleType),
                                'url': modelObjectUri(modelRoleType),
                                'roleURI': modelRoleType.roleURI,
                                'definition': modelRoleType.definition,
                                'usedOn': [modelObjectUri(self.modelXbrl.qnameConcepts[qn]) 
                                           for qn in modelRoleType.usedOns]
                                }
                    document['arcroleTypes'] = arcroleTypes = {}
                    for modelArcroleTypes in self.modelXbrl.arcroleTypes.values():
                        for modelArcroleType in modelArcroleTypes:
                            arcroleTypes[modelRoleType.roleURI] = arcroleType = {
                                'document': modelObjectDocumentUri(modelArcroleType),
                                'url': modelObjectUri(modelArcroleType),
                                'arcroleURI': modelArcroleType.roleURI,
                                'definition': modelArcroleType.definition,
                                'usedOn': [modelObjectUri(self.modelXbrl.qnameConcepts[qn]) 
                                           for qn in modelArcroleType.usedOns],
                                'cyclesAllowed': modelArcroleType.cyclesAllowed
                                }

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
    def insertAspectProxies(self, qnames):
        aspectQnames = [qname 
                        for qname in qnames 
                        if qname not in self.aspect_proxy_uri and qname in self.modelXbrl.qnameConcepts]
        for qname in aspectQnames:
            self.insertAspectProxy(qname, qnamePrefix_Name(qname))
            
    def insertAspectProxy(self, aspectQName, aspectProxyUri):
        concept = self.modelXbrl.qnameConcepts[aspectQName]
        self.report['aspectProxies'][aspectProxyUri] = aspectProxy = {
            'report': self.reportURI,
            'document': modelObjectDocumentUri(concept),
            'name': concept.name
            }
        self.aspect_proxy[aspectQName] = aspectProxy
        self.aspect_proxy_uri[aspectQName] = aspectProxyUri
        return aspectProxy
    
    def aspectQnameProxy(self, qname):
        if hasattr(qname, "modelDocument"):
            return self.aspect_proxy.get(qname.qname)
        elif qname in self.modelXbrl.qnameConcepts:
            return self.aspect_proxy.get(qname)
        return None

    def aspectQnameProxyId(self, qname):
        if hasattr(qname, "modelDocument"):
            return self.aspect_proxy_uri.get(qname.qname)
        elif qname in self.modelXbrl.qnameConcepts:
            return self.aspect_proxy_uri.get(qname)
        return None

    def insertDataPoints(self):
        # separate graph
        # document-> dataTypeSet -> dataType
        self.showStatus("insert DataPoints")
        
        # note these initial aspects Qnames used also must be in conceptsUsed above
        dimensions = [] # index by hash of dimension
        dimensionIds = {}  # index for dimension
        if self.modelXbrl.modelDocument.type in (Type.INSTANCE, Type.INLINEXBRL):
            contextAspectValueSelections = {}  # contexts processed already
            unitIDs = set()  # units processed already
            periodProxies = {}
            entityIdentifierAspectProxies = {}
            dataPoints = self.report['dataPoints']
            for fact in self.modelXbrl.factsInInstance:
                self.insertAspectProxies( (fact.qname,) )
                factId = XmlUtil.elementFragmentIdentifier(fact)
                dataPoints[factId] = dataPoint = {
                    'document': modelObjectDocumentUri(fact),
                    'id': factId,
                    'sourceLine': fact.sourceline,
                    'dataPointUrl': modelObjectUri(fact),
                    'baseItem': self.aspectQnameProxyId(fact.qname)
                    }
                
                context = fact.context
                concept = fact.concept
                if context is not None:
                    if context.entityIdentifier not in entityIdentifierAspectProxies:
                        entityScheme, entityIdentifier = context.entityIdentifier
                        entityIdentifierAspectProxy = "{}/{}".format(
                                                  qnamePrefix_Name(XbrlConst.qnXbrliIdentifier),
                                                  entityIdentifier)
                        e = self.insertAspectProxy(XbrlConst.qnXbrliIdentifier, entityIdentifierAspectProxy)
                        e['scheme'] = entityScheme
                        e['identifier'] = entityIdentifier
                        entityIdentifierAspectProxies[context.entityIdentifier] = entityIdentifierAspectProxy
                    else:
                        entityIdentifierAspectProxy = entityIdentifierAspectProxies[context.entityIdentifier]
                    dataPoint['entityIdentifier'] = entityIdentifierAspectProxy

                    if context.isForeverPeriod:
                        period = "forever"
                    if context.isInstantPeriod:
                        endDate = XmlUtil.dateunionValue(context.instantDatetime, subtractOneDay=True).replace(':','_')
                        period = "instant/{}".format(endDate)
                    else:
                        startDate = XmlUtil.dateunionValue(context.startDatetime).replace(':','_')
                        endDate = XmlUtil.dateunionValue(context.endDatetime, subtractOneDay=True).replace(':','_')                        
                        period = "duration/{}/{}".format(startDate, endDate)
                    if period not in periodProxies:
                        periodProxy = "{}/{}".format(
                                                  qnamePrefix_Name(XbrlConst.qnXbrliPeriod),
                                                  period)
                        p = self.insertAspectProxy(XbrlConst.qnXbrliPeriod, periodProxy)
                        p['isForever'] = context.isForeverPeriod
                        p['isInstant'] = context.isInstantPeriod
                        if context.isStartEndPeriod:
                            d = context.startDatetime
                            if d.hour == 0 and d.minute == 0 and d.second == 0:
                                d = d.date()
                            p['startDate'] = d
                        if context.isStartEndPeriod or context.isInstantPeriod:
                            d = context.endDatetime
                            if d.hour == 0 and d.minute == 0 and d.second == 0:
                                d = (d - datetime.timedelta(1)).date()
                            p['endDate'] = d
                        periodProxies[period] = periodProxy
                    else:
                        periodProxy = periodProxies[period]
                    dataPoint['period'] = periodProxy
                    
                    dataPoint['contextUrl'] = modelObjectUri(context)
                    dataPoint['contextId'] = context.id
                    if context.id not in contextAspectValueSelections:
                        contextAspectValueSelections[context.id] = contextAspectValueSelection = []
                        
                        for dimVal in context.qnameDims.values():
                            dim = qnamePrefix_Name(dimVal.dimensionQname)
                            if dimVal.isExplicit:
                                self.insertAspectProxies( (dimVal.memberQname,) )  # need imediate use of proxy
                                v = self.aspectQnameProxyId(dimVal.memberQname)
                            else:
                                v = dimVal.typedMember.stringValue
                            dimProxy = "{}/{}".format(dim, v)
                            d = self.insertAspectProxy(dimVal.dimensionQname, dimProxy)
                            contextAspectValueSelection.append(dimProxy)
                            d['aspect'] = dim
                            if dimVal.isExplicit:
                                d['aspectValue'] = v
                            else:
                                d['typedValue'] = v
                    else:
                        contextAspectValueSelection = contextAspectValueSelections[context.id]
                    dataPoint['aspectValueSelections'] = contextAspectValueSelection
                    if fact.isNumeric:
                        if fact.precision == "INF":
                            dataPoint['precision'] = "INF"
                        elif fact.precision is not None:
                            dataPoint['precision'] = fact.precision
                        if fact.decimals == "INF":
                            dataPoint['decimals'] = "INF"
                        elif fact.decimals is not None:
                            dataPoint['decimals'] = fact.decimals
                        if fact.unit is not None:
                            unit = fact.unit
                            unitProxy = "{}/{}".format(
                                                      qnamePrefix_Name(XbrlConst.qnXbrliUnit),
                                                      unit.id)
                            dataPoint['unit'] = unitProxy
                            if unit.id not in unitIDs:
                                unitIDs.add(unit.id)
                                u = self.insertAspectProxy(XbrlConst.qnXbrliUnit, unitProxy)
                                u['unitId'] = unit.id
             
                                mults, divs = unit.measures
                                u['multiplyMeasures'] = [qnameUri(qn) for qn in mults]
                                if divs:
                                    u['divideMeasures'] = [qnameUri(qn) for qn in divs]
                    if fact.xmlLang is None and fact.concept is not None and fact.concept.baseXsdType is not None:
                        dataPoint['value'] = fact.xValue
                        # The insert with base XSD type but no language
                    elif fact.xmlLang is not None:
                        # assuming string type with language
                        dataPoint['language'] = fact.xmlLang
                        dataPoint['value'] = fact.value
                    else:
                        # Otherwise insert as plain liternal with no language or datatype
                        dataPoint['value'] = fact.value
                        
                    if fact.modelTupleFacts:
                        dataPoint['tuple'] = [XmlUtil.elementFragmentIdentifier(tupleFact)
                                              for tupleFact in fact.modelTupleFacts]

        
    def resourceId(self,i):
        return "<{accessionPrefix}resource/{i}>".format(accessionPrefix=self.thisAccessionPrefix,
                                                        i=i)
    
    def insertRelationshipSets(self):
        self.showStatus("insert relationship sets")
        aspectQnamesUsed = set()
        for i, relationshipSetKey in enumerate(self.relationshipSets):
            arcrole, linkrole, linkqname, arcqname = relationshipSetKey
            if linkqname:
                aspectQnamesUsed.add(linkqname)
            if arcqname:
                aspectQnamesUsed.add(arcqname)
        self.insertAspectProxies(aspectQnamesUsed)
        
        relationshipSets = self.report['relationshipSets']
        relSetIds = {}
        for i, relationshipSetKey in enumerate(self.relationshipSets):
            arcrole, linkrole, linkqname, arcqname = relationshipSetKey
            if arcrole not in ("XBRL-formulae", "Table-rendering", "XBRL-footnotes") and linkrole and linkqname and arcqname:
                # skip paths and qnames for now (add later for non-SEC)
                relSetId = "{}/{}".format(
                                   os.path.basename(arcrole),
                                   os.path.basename(linkrole))
                relSetIds[relationshipSetKey] = relSetId
                relationshipSets[relSetId] = relationshipSet = {
                    'arcrole': arcrole,
                    'linkrole': linkrole,
                    'arcname': self.aspectQnameProxyId(arcqname),
                    'linkname': self.aspectQnameProxyId(linkqname),
                    'report': self.reportURI,
                    'roots': [],
                    'relationships': []
                    }
        
        # do tree walk to build relationships with depth annotated, no targetRole navigation
        relE = [] # fromV, toV, label
        resources = set()
        aspectQnamesUsed = set()
        resourceIDs = {} # index by object
        
        def walkTree(rels, parentRelId, seq, depth, relationshipSetKey, relationshipSet, visited, relSetId, doVertices):
            for rel in rels:
                if rel not in visited:
                    visited.add(rel)
                    
                    if not doVertices:
                        _relProp = {'seq': seq,
                                    'depth': depth,
                                    'order': rel.orderDecimal,
                                    'priority': rel.priority,
                                    'relSetId': relSetId
                                    }
                    if isinstance(rel.fromModelObject, ModelConcept):
                        if doVertices:
                            aspectQnamesUsed.add(rel.fromModelObject.qname)
                            sourceUri = True
                        else:
                            sourceQname = rel.fromModelObject.qname
                            sourceUri = self.aspectQnameProxyId(sourceQname)
                            sourceId = qnamePrefix_Name(rel.fromModelObject.qname)
                    else:
                        sourceUri = None # tbd
                    toModelObject = rel.toModelObject
                    if isinstance(toModelObject, ModelConcept):
                        if doVertices:
                            aspectQnamesUsed.add(toModelObject.qname)
                            targetUri = True
                        else:
                            targetUri = self.aspectQnameProxyId(toModelObject.qname)
                            targetId = qnamePrefix_Name(toModelObject.qname)
                    elif isinstance(toModelObject, ModelResource):
                        if doVertices:
                            resources.add(toModelObject)
                            targetUri = 0 # just can't be None, but doesn't matter on doVertices pass
                        else:
                            if rel.preferredLabel:
                                _relProp['preferredLabel'] = rel.preferredLabel
                            if rel.arcrole in (XbrlConst.all, XbrlConst.notAll):
                                _relProp['cubeClosed'] = rel.closed
                            elif rel.arcrole in (XbrlConst.dimensionDomain, XbrlConst.domainMember):
                                _relProp['aspectValueUsable'] = rel.usable
                            elif rel.arcrole == XbrlConst.summationItem:
                                _relProp['weight'] = rel.weightDecimal
                            if relationshipSet.arcrole == "XBRL-dimensions":
                                _relProp['arcrole'] = rel.arcrole
                            if toModelObject.role:
                                _relProp['resourceRole'] = toModelObject.role
                            targetUri = modelObjectUri(toModelObject)
                            targetId = toModelObject.modelDocument.basename + '#' + XmlUtil.elementFragmentIdentifier(toModelObject)
                    else:
                        targetUri = None # tbd
                    if sourceUri is not None and targetUri is not None:
                        targetRelSetId = relSetId
                        targetRelSetKey = relationshipSetKey
                        if relationshipSet.arcrole == "XBRL-dimensions" and rel.targetRole:
                            targetRelSet = self.modelXbrl.relationshipSet(relationshipSet.arcrole, rel.targetRole)
                            for i, relSetKey in enumerate(self.relationshipSets):
                                arcrole, ELR, linkqname, arcqname = relSetKey
                                if arcrole == "XBRL-dimensions" and ELR == rel.targetRole:
                                    targetRelationshipSetId = relSetIds[relSetKey]
                                    targetRelSetKey = relSetKey
                                    break
                            if not doVertices:
                                _relProp['targetLinkrole'] = rel.targetRole
                                _relProp['targetRelSet'] = targetRelationshipSetId
                        else:
                            targetRelSetKey = relationshipSetKey
                            targetRelSet = relationshipSet
                        if doVertices:
                            relId = None
                        else:
                            _relProp['from'] = sourceUri
                            _relProp['fromQname'] = sourceQname
                            _relProp['to'] = targetUri
                            _arcrole = os.path.basename(rel.arcrole)
                            relId = "{}/{}/{}/{}".format(
                                            _arcrole,
                                            os.path.basename(rel.linkrole),
                                            sourceId,
                                            targetId)
                            _relProp['relId'] = relId
                            _relProp['relSetKey'] = relationshipSetKey

                            relE.append(_relProp)
                        seq += 1
                        seq = walkTree(targetRelSet.fromModelObject(toModelObject), relId, seq, depth+1, targetRelSetKey, targetRelSet, visited, targetRelSetId, doVertices)
                    visited.remove(rel)
            return seq
        

        for doVertices in range(1,-1,-1):  # pass 0 = vertices, pass 1 = edges
            for i, relationshipSetKey in enumerate(self.relationshipSets):
                arcrole, linkrole, linkqname, arcqname = relationshipSetKey
                if arcrole not in ("XBRL-formulae", "Table-rendering", "XBRL-footnotes") and linkrole and linkqname and arcqname:                
                    relSetId = relSetIds[relationshipSetKey]
                    relationshipSet = self.modelXbrl.relationshipSet(*relationshipSetKey)
                    seq = 1               
                    for rootConcept in relationshipSet.rootConcepts:
                        seq = walkTree(relationshipSet.fromModelObject(rootConcept), None, seq, 1, relationshipSetKey, relationshipSet, set(), relSetId, doVertices)
            if doVertices:
                if resources:
                    for resource in resources:
                        resourceUri = modelObjectUri(resource)
                        r = {'url': resourceUri,
                             'value': resource.stringValue
                            }
                        if resource.xmlLang:
                            r['language'] = resource.xmlLang
                        if resource.role:
                            r['role'] = resource.role
                        self.documents[modelObjectDocumentUri(resource)]['resources'][
                                        XmlUtil.elementFragmentIdentifier(resource)] = r
                    
                self.insertAspectProxies(aspectQnamesUsed)
            else:
                for j, rel in enumerate(relE):
                    relId = rel['relId']
                    relSetId = rel['relSetId']
                    relSet = relationshipSets[relSetId]
                    r = dict((k,v)
                             for k,v in rel.items()
                             if k not in ('relId', 'relPredicate', 'relSetId', 'relSetKey', 'fromQname'))
                    relSet['relationships'].append(r)
                    if rel.get('depth', 0) == 1:
                        relSet['roots'].append(r)
                    sourceQname = rel['fromQname']
                    if sourceQname in self.aspect_proxy:
                        self.aspect_proxy[sourceQname] \
                            .setdefault('relationships', {}) \
                            .setdefault(rel['relSetId'], []) \
                            .append(rel['to'])
                
                # TBD: do we want to link resources to the dts (by role, class, or otherwise?)
                    
        resourceIDs.clear() # dereferemce objects
        resources = None
        
    def insertValidationResults(self):
        logEntries = []
        for handler in logging.getLogger("arelle").handlers:
            if hasattr(handler, "dbHandlerLogEntries"):
                logEntries = handler.dbHandlerLogEntries()
                break
        
        messages = []
        messageRefs = [] # direct link to objects
        for i, logEntry in enumerate(logEntries):
            messageId = "message/{}".format(i+1)
            self.report['messages'][messageId] = m = {
                'code': logEntry['code'],
                'level': logEntry['level'],
                'value': logEntry['message']['text'],
                'report': self.reportURI,
                'messageId': messageId
                }
            # capture message ref's
            for ref in logEntry['refs']:
                modelObject = self.modelXbrl.modelObject(ref.get('objectId',''))
                # for now just find a concept
                aspectObj = None
                if isinstance(modelObject, ModelFact):
                    factId = XmlUtil.elementFragmentIdentifier(modelObject)
                    dataPoint = self.report['dataPoints'][factId]
                    dataPoint.setdefault('messages', []).append(messageId)
                elif isinstance(modelObject, ModelConcept):
                    # be sure there's a proxy
                    self.insertAspectProxies( (modelObject.qname,))  # need imediate use of proxy
                    self.aspectQnameProxy(modelObject.qname).setdefault('messages', []).append(messageId)
                elif isinstance(modelObject, ModelRelationship):
                    ''' TBD
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
                    '''
                else:
                    continue
                        
        if messages:
            self.showStatus("insert validation messages")
