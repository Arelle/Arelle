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
from math import isnan, isinf
from arelle.ModelDtsObject import ModelConcept, ModelResource, ModelRelationship
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelDocument import Type
from arelle import XbrlConst, XmlUtil
import urllib.request
from urllib.error import HTTPError, URLError

TRACERDFFILE = None
#TRACERDFFILE = r"c:\temp\rdfDBtrace.log"  # uncomment to trace RDF on connection (very big file!!!)

RDFTURTLEFILE_HOSTNAME = "rdfTurtleFile"

def insertIntoDB(modelXbrl, 
                 user=None, password=None, host=None, port=None, database=None, timeout=None,
                 rssItem=None):
    rdfdb = None
    try:
        rdfdb = XbrlSemanticRdfDatabaseConnection(modelXbrl, user, password, host, port, database, timeout)
        rdfdb.verifyGraphs()
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
    if host == RDFTURTLEFILE_HOSTNAME:
        return True
    # determine if postgres port
    t = 2
    while t < timeout:
        try:
            conn = urllib.request.urlopen("http://{0}:{1}/{2}/status".format(host, port or '80', db))
            return True # success but doesn't need password
        except HTTPError:
            return True # success, this is really a postgres socket, wants user name
        except URLError:
            return False # something is there but not postgres
        except socket.timeout:
            t = t + 2  # relax - try again with longer timeout
    return False
    
HTTPHEADERS = {'User-agent':   'Arelle/1.0',
               'Accept':       'text/turtle',
               'Content-Type': 'text/turtle'}

XRDFDB_IRI = "http://xbrl.rdf"

XRDFDB_PREFIXES = """
@prefix : <{xrdfdbIri}#> .
""".format(xrdfdbIri=XRDFDB_IRI)

XRDFDB = "http://xbrl.org/2013/rdf/"

def rdfNum(num):
    if isinstance(num, (int,float)):
        if isinf(num) or isnan(num):
            return None  # not legal in SQL
        return str(num) + ' '  # space required to separate from following syntax such as .
    return None 

def rdfBool(boolean):
    return "true " if boolean else "false " # space required to separate from following syntax, such as . or ;

def rdfString(s): # compress long strings
    #if isinstance(s, _STR_UNICODE) and len(s) > 512:
    #    return ''.join(map(chr,zlib.compress(s.encode()))) # compress as utf-8 but return as string
    
    # quote " if in s
    if not isinstance(s, _STR_UNICODE):
        s = _STR_UNICODE(s)
    return '"' + s.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n') + '"'

def rdfUrlSuffix(s):
    return s.replace("\\","/").replace("://", "/").replace(":/", "/").replace(" ","%20")

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
        self.modelXbrl = modelXbrl
        self.disclosureSystem = modelXbrl.modelManager.disclosureSystem
        #self.conn = RexProConnection(host, int(port or '8182'), (database or 'emptygraph'),
        #                             user=user, password=password)
        self.isRdfTurtleFile = host == RDFTURTLEFILE_HOSTNAME
        if self.isRdfTurtleFile:
            self.turtleFile = database
        else:
            connectionUrl = "http://{0}:{1}".format(host, port or '80')
            self.url = connectionUrl + '/' + database + "/sparql"
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
            if not self.isRdfTurtleFile:
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
        
    def verifyGraphs(self):
        # if no tables, initialize database
        pass # not sure what to do here
            
    def execute(self, activity, turtle, commit=False, close=True, fetch=True):
        # turtle may be mixture of line strings and strings with \n-separated lines
        if isinstance(turtle, (list,tuple)):
            lines = '\n'.join(turtle)
        else:
            lines = turtle
        # strip extra indentation
        lines = lines.split('\n')
        if lines:
            # find first indented string and use as template to strip extra indentation
            for line1 in lines:
                spaces = line1.index(line1.strip())
                if spaces:
                    lines = [l[spaces:] if l[0:spaces].isspace() else l.strip()
                             for l in lines]
                    break
        turtle = XRDFDB_PREFIXES + '\n' + '\n'.join(lines)

        if TRACERDFFILE:
            with io.open(TRACERDFFILE, "a", encoding='utf-8') as fh:
                fh.write("\n\n>>> sent: \n{0}".format(turtle))
        if self.isRdfTurtleFile:
            with io.open(self.turtleFile, "a", encoding='utf-8') as fh:
                fh.write(turtle)
            return None
        request = urllib.request.Request(self.url,
                                         data=turtle.encode('utf-8'),
                                         headers=HTTPHEADERS)
        try:
            with self.conn.open(request, timeout=self.timeout) as fp:
                results = fp.read().decode('utf-8')
        except HTTPError as err:
            if err.code == 500: # results are not successful but returned nontheless
                results = err.fp.read().decode('utf-8')
            else:
                raise  # reraise any other errors
        if TRACERDFFILE:
            with io.open(TRACERDFFILE, "a", encoding='utf-8') as fh:
                fh.write("\n\n>>> received: \n{0}".format(str(results)))
        if not results.startswith('<?xml version="1.0"?><data '):
            parseExceptionIndex = results.find('org.openrdf.rio.RDFParseException:')
            if parseExceptionIndex >= 0:
                parseExceptionEndIndex = results.find('<', parseExceptionIndex)
                error = results[parseExceptionIndex : parseExceptionEndIndex]
            else:
                error = results
            raise XRDBException("xrdfDB:DatabaseError",
                                _("%(activity)s not successful: %(error)s"),
                                activity=activity, error=error) 
        return results
    
    def commit(self):
        pass # TBD  g.commit(), g.rollback() may be not working at least on tinkergraph
    
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
            # self.load()  this done in the verify step
            self.insertAccession(rssItem)
            self.insertDocuments()
            self.insertDataDictionary() # XML namespaces types aspects
            #self.insertRelationshipTypeSets()
            #self.insertResourceRoleSets()
            #self.insertAspectValues()
            self.modelXbrl.profileStat(_("XbrlPublicDB: DTS insertion"), time.time() - startedAt)
            startedAt = time.time()
            self.insertDataPoints()
            self.modelXbrl.profileStat(_("XbrlPublicDB: data points insertion"), time.time() - startedAt)
            startedAt = time.time()
            self.insertRelationshipSets()
            self.modelXbrl.profileStat(_("XbrlPublicDB: Relationships insertion"), time.time() - startedAt)
            self.insertValidationResults()
            self.modelXbrl.profileStat(_("XbrlPublicDB: Validation results insertion"), time.time() - startedAt)
            #startedAt = time.time()
            #self.insertValidCombinations()
            #self.modelXbrl.profileStat(_("XbrlPublicDB: Valid Combinations insertion"), time.time() - startedAt)
            self.showStatus("Committing entries")
            self.commit()
            self.modelXbrl.profileStat(_("XbrlPublicDB: insertion committed"), time.time() - startedAt)
            #finalVcount, finalEcount = self.getDBsize()
            #self.modelXbrl.modelManager.addToLog("added vertices: {0}, edges: {1}, total vertices: {2}, edges: {3}".format(
            #              finalVcount - initialVcount, finalEcount - initialEcount, finalVcount, finalEcount))
            self.showStatus("DB insertion completed", clearAfter=5000)
        except Exception as ex:
            self.showStatus("DB insertion failed due to exception", clearAfter=5000)
            raise
        
    def insertAccession(self, rssItem):
        self.showStatus("insert accession")
        # accession graph -> document vertices
        new_accession = {}
        if self.modelXbrl.modelDocument.creationSoftwareComment:
            new_accession[':creation_software'] = self.modelXbrl.modelDocument.creationSoftwareComment
        datetimeNow = datetime.datetime.now()
        datetimeNowStr = XmlUtil.dateunionValue(datetimeNow)
        if rssItem is not None:  # sec accession
            # set self.
            accessionType = "SEC_filing"
            # for an RSS Feed entry from SEC, use rss item's accession information
            new_accession[':accepted_timestamp'] = XmlUtil.dateunionValue(rssItem.acceptanceDatetime)
            new_accession[':filing_date'] = XmlUtil.dateunionValue(rssItem.filingDate)
            new_accession[':entity_id'] = rssItem.cikNumber
            new_accession[':entity_name'] = rssItem.companyName
            new_accession[':standard_industrial_classification'] = rssItem.assignedSic 
            new_accession[':sec_html_url'] = rssItem.htmlUrl 
            new_accession[':entry_url'] = rssItem.url
            new_accession[':filing_accession_number'] = filing_accession_number = rssItem.accessionNumber
        else:
            # not an RSS Feed item, make up our own accession ID (the time in seconds of epoch)
            self.accessionId = int(time.time())    # only available if entered from an SEC filing
            intNow = int(time.time())
            accessionType = "independent_filing"
            new_accession[':accepted_timestamp'] = datetimeNowStr
            new_accession[':filing_date'] = datetimeNowStr
            new_accession[':entry_url'] = self.modelXbrl.fileSource.url
            new_accession[':filing_accession_number'] = filing_accession_number = str(intNow)
        self.thisAccession = "<{xrdfdbIri}/accession/{filing_accession_number}>".format(
                                     xrdfdbIri=XRDFDB_IRI,
                                     filing_accession_number=filing_accession_number)
        self.thisAccessionPrefix = "{xrdfdbIri}/accession/{filing_accession_number}/".format(
                                     xrdfdbIri=XRDFDB_IRI,
                                     filing_accession_number=filing_accession_number)
        self.execute("Insert accession " + accessionType, """
            {thisAccession}
            {accessionProperties}.
            """.format(thisAccession=self.thisAccession,
                       accessionNumber=filing_accession_number, 
                       accessionProperties=';\n'.join("   {0} {1}".format(n, rdfString(v))
                                                      for n,v in new_accession.items())
                       )
                     )
            
        # relationshipSets are a dts property
        self.relationshipSets = [(arcrole, ELR, linkqname, arcqname)
                                 for arcrole, ELR, linkqname, arcqname in self.modelXbrl.baseSets.keys()
                                 if ELR and (arcrole.startswith("XBRL-") or (linkqname and arcqname))]
        
    def insertDocuments(self):
        # accession->documents
        # 
        self.showStatus("insert documents")
        documents = []
        entryUrlSuffix = rdfUrlSuffix(self.modelXbrl.modelDocument.uri)
        for modelDocument in self.modelXbrl.urlDocs.values():
            urlSuffix = rdfUrlSuffix(modelDocument.uri)
            thisDocument = "<{xrdfdbIri}/document/{urlSuffix}>".format(xrdfdbIri=XRDFDB_IRI,
                                                                       urlSuffix=urlSuffix)
            documents.append("""
                {thisDocument}
                    :url {url};
                    :document_type {document_type}.
                {thisAccession}
                    <{xrdfdbIri}#urlSuffix> {thisDocument}.
            """.format(xrdfdbIri=XRDFDB_IRI,
                       thisDocument=thisDocument,
                       thisAccession=self.thisAccession,
                       urlSuffix=urlSuffix,
                       url=rdfString(modelDocument.uri),
                       document_type = rdfString(modelDocument.gettype())))
            if modelDocument.uri == self.modelXbrl.modelDocument.uri: # entry document
                documents.append("""
                {thisAccession}
                    :entry_url {thisDocument}.
                """.format(thisAccession=self.thisAccession,
                           thisDocument=thisDocument,
                           urlSuffix=urlSuffix))
            else: # non-entry referenced document
                documents.append("""
                <{xrdfdbIri}/document/{entryUrlSuffix}>
                    :referenced_document {thisDocument}.
                """.format(xrdfdbIri=XRDFDB_IRI,
                           entryUrlSuffix=entryUrlSuffix,
                           thisDocument=thisDocument))
        self.execute("Insert documents", documents)
        
        # determine which documents already exist
        #self.document_isNew = dict( (url, isNew) for url,isNew in doc_isNew_list.items() )
                
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
        for relationshipSetKey in self.relationshipSets:
            relationshipSet = self.modelXbrl.relationshipSet(*relationshipSetKey)
            for rel in relationshipSet.modelRelationships:
                if isinstance(rel.fromModelObject, ModelConcept):
                    conceptsUsed.add(rel.fromModelObject)
                if isinstance(rel.toModelObject, ModelConcept):
                    conceptsUsed.add(rel.toModelObject)
        for qn in (XbrlConst.qnXbrliIdentifier, XbrlConst.qnXbrliPeriod, XbrlConst.qnXbrliUnit):
            conceptsUsed.add(self.modelXbrl.qnameConcepts[qn])
        return conceptsUsed

    def insertDataDictionary(self):
        # separate graph
        # document-> dataTypeSet -> dataType
        # do all schema dataTypeSet vertices
            
        self.type_id = {}
        self.aspect_id = {}
        self.aspect_proxy_id = {}
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
            document = ["@prefix thisAccession: <{thisAccession}>.\n"
                        "@prefix thisDocument: <{xrdfdbIri}/document/{uri}/>."
                        .format(xrdfdbIri=XRDFDB_IRI,
                                thisAccession=self.thisAccessionPrefix, 
                                uri=rdfUrlSuffix(modelDocument.uri))]
            thisDocumentRolePrefix = "{xrdfdbIri}/document/{uri}/role/".format(xrdfdbIri=XRDFDB_IRI,
                                                                               uri=rdfUrlSuffix(modelDocument.uri))
            thisDocumentArcrolePrefix = "{xrdfdbIri}/document/{uri}/arcrole/".format(xrdfdbIri=XRDFDB_IRI,
                                                                                     uri=rdfUrlSuffix(modelDocument.uri))
            
            # don't re-output existing documents
            if modelDocument.type == Type.SCHEMA:
                isNewDocument = True # self.document_isNew[modelDocument.uri]
                modelConcepts = [modelConcept
                                 for modelConcept in self.modelXbrl.qnameConcepts.values()
                                 if modelConcept.modelDocument is modelDocument and
                                    (isNewDocument or modelConcept in conceptsUsed)]
                if isNewDocument:
                    # adding document as new
                    for modelType in self.modelXbrl.qnameTypes.values():
                        if modelType.modelDocument is modelDocument:
                            document.append("""
                            @prefix thisType: <{xrdfdbIri}/document/{uri}/data_type/{nameSuffix}>.
                            thisDocument:
                                :data_type thisType: .
                            thisType:
                                :name {name}.
                            """.format(
                                 xrdfdbIri=XRDFDB_IRI, 
                                 uri=rdfUrlSuffix(modelDocument.uri),
                                 nameSuffix=rdfUrlSuffix(modelType.name),
                                 name=rdfString(modelType.name),
                                 ))
                            typesDerivedFrom = modelType.typeDerivedFrom
                            if not isinstance(typesDerivedFrom, (list,tuple)): # list if a union
                                typesDerivedFrom = (typesDerivedFrom,)
                            for typeDerivedFrom in typesDerivedFrom:
                                if typeDerivedFrom is not None:
                                    document.append("""
                                    thisType:
                                        :derived_from <{xrdfdbIri}/document/{uriDerivedFrom}/data_type/{nameDerivedFrom}>.
                                    """.format(
                                         xrdfdbIri=XRDFDB_IRI, 
                                         uriDerivedFrom=rdfUrlSuffix(typeDerivedFrom.modelDocument.uri),
                                         nameDerivedFrom=rdfUrlSuffix(typeDerivedFrom.name),
                                         ))
                    conceptAspects = []
                    for modelConcept in modelConcepts:
                        document.append("""
                        @prefix thisAspect: <{xrdfdbIri}/document/{uri}/aspect/{nameUri}>.
                        thisDocument:
                            :aspect thisAspect: .
                        thisAspect:
                            :name {name} .
                        """.format(
                             xrdfdbIri=XRDFDB_IRI, 
                             uri=rdfUrlSuffix(modelDocument.uri),
                             nameUri=rdfUrlSuffix(modelConcept.name),
                             name=rdfString(modelConcept.name),
                             ))
                        if modelConcept.isAbstract:
                            document.append("thisAspect: :isAbstract true .")
                        if modelConcept.periodType:
                            document.append("thisAspect: :periodType {periodType}.".format(
                                    periodType=rdfString(modelConcept.periodType)))
                        if modelConcept.balance:
                            document.append("thisAspect: :balance {balance}.".format(
                                    balance=rdfString(modelConcept.balance)))
                        # boolean properties
                        for propertyName in ('isItem', 'isTuple', 'isLinkPart', 'isNumeric', 'isMonetary', 
                                             'isExplicitDimension', 'isTypedDimension', 'isDomainMember', 'isHypercubeItem',
                                             'isShares', 'isTextBlock'):
                            propertyValue = getattr(modelConcept, propertyName, None)
                            if propertyValue:
                                document.append("thisAspect: :{propertyName} {propertyValue}.".format(
                                        propertyName=propertyName,
                                        propertyValue=rdfBool(propertyValue)))
                        type = modelConcept.type
                        if type is not None:
                            document.append("""
                            thisAspect: 
                                :data_type <{xrdfdbIri}/document/{uriDerivedFrom}/data_type/{nameDerivedFrom}>.
                            """.format(
                                 xrdfdbIri=XRDFDB_IRI, 
                                 uriDerivedFrom=rdfUrlSuffix(type.modelDocument.uri),
                                 nameDerivedFrom=rdfUrlSuffix(type.name),
                                 ))
                        substitutionGroup = modelConcept.substitutionGroup
                        if substitutionGroup is not None:
                            document.append("""
                            thisAspect: 
                                :substitutes_for <{xrdfdbIri}/document/{uriSubsFor}/data_type/{nameSubsFor}>.
                            """.format(
                                 xrdfdbIri=XRDFDB_IRI, 
                                 uriSubsFor=rdfUrlSuffix(substitutionGroup.modelDocument.uri),
                                 nameSubsFor=rdfUrlSuffix(substitutionGroup.name),
                                 ))
                    for modelRoleTypes in self.modelXbrl.roleTypes.values():
                        for modelRoleType in modelRoleTypes:
                            document.append("""
                            thisDocument: 
                                :role_type <{thisDocumentRolePrefix}{roleUriSuffix}>.
                            <{thisDocumentRolePrefix}{roleUriSuffix}>
                                :definition {definition}.
                            """.format(thisDocumentRolePrefix=thisDocumentRolePrefix,
                                       roleUriSuffix=rdfUrlSuffix(modelRoleType.roleURI),
                                       definition=rdfString(modelRoleType.definition or '')))
                    for modelArcroleTypes in self.modelXbrl.arcroleTypes.values():
                        for modelArcroleType in modelArcroleTypes:
                            document.append("""
                            thisDocument: 
                                :arcrole_type <{thisDocumentArcrolePrefix}{arcroleUriSuffix}>.
                            <{thisDocumentArcrolePrefix}{arcroleUriSuffix}>
                                :definition {definition};
                                :cyclesAllowed {cyclesAllowed}.
                            """.format(thisDocumentArcrolePrefix=thisDocumentArcrolePrefix,
                                       arcroleUriSuffix=rdfUrlSuffix(modelArcroleType.arcroleURI),
                                       definition=rdfString(modelArcroleType.definition or ''),
                                       cyclesAllowed=rdfString(modelArcroleType.cyclesAllowed)))
                    activity = "Insert data dictionary types, aspects, roles, and arcroles for " + modelDocument.uri
                    results = self.execute(activity, document)

        
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
                        if qname not in self.aspect_proxy_id and qname in self.modelXbrl.qnameConcepts]
        aspectProxies = []
        for qname in aspectQnames:
            concept = self.modelXbrl.qnameConcepts[qname]
            url = concept.modelDocument.uri
            prefix = concept.qname.prefix
            name = concept.qname.localName
            aspectProxy = "<{thisAccession}dts/aspect/{prefix}/{name}>".format(
                                   thisAccession=self.thisAccessionPrefix,
                                   prefix=rdfUrlSuffix(prefix),
                                   name=rdfUrlSuffix(name))
            self.aspect_proxy_id[qname] = aspectProxy
            aspectProxies.append("""
            @prefix thisAspect: <{xrdfdbIri}/document/{uri}/aspect/{name}>.
            thisAspect:
                :proxy {aspectProxy} .
            {aspectProxy}
                :aspect thisAspect: .
            """.format(
                 xrdfdbIri=XRDFDB_IRI, 
                 uri=rdfUrlSuffix(url),
                 name=rdfUrlSuffix(name),
                 aspectProxy=aspectProxy
                 ))
        if aspectProxies:
            self.execute("Insert aspect proxies", aspectProxies)
            
    
    def aspectId(self, qname):
        if hasattr(qname, "modelDocument"):
            return self.aspect_proxy_id.get(qname.qname)
        elif qname in self.modelXbrl.qnameConcepts:
            return self.aspect_proxy_id.get(qname)
        return None
        
    def periodAspectValue(self, context):
        if context.isForeverPeriod:
            return 'forever'
        if context.isInstantPeriod:
            return (str(context.instantDatetime),)
        return (str(context.startDatetime),str(context.endDatetime))

    def insertDataPoints(self):
        # separate graph
        # document-> dataTypeSet -> dataType
        self.showStatus("insert DataPoints")
        
        # do all schema element vertices
        dataPointObjectIndices = []
        # note these initial aspects Qnames used also must be in conceptsUsed above
        aspectQnamesUsed = {XbrlConst.qnXbrliIdentifier, XbrlConst.qnXbrliPeriod, XbrlConst.qnXbrliUnit}
        dimensions = [] # index by hash of dimension
        dimensionIds = {}  # index for dimension
        if self.modelXbrl.modelDocument.type in (Type.INSTANCE, Type.INLINEXBRL):
            dataPoints = ["@prefix thisAccession: <{accessionPrefix}>."
                          .format(accessionPrefix=self.thisAccessionPrefix)]
            entityIdentifiers = [] # index by (scheme, identifier)
            periods = []  # index by (instant,) or (start,end) dates
            units = []  # index by measures (qnames set) 
            for i, fact in enumerate(self.modelXbrl.factsInInstance):
                aspectQnamesUsed.add(fact.concept.qname)
                dataPointObjectIndices.append(fact.objectIndex)
                dataPoints.append("""
                @prefix thisDataPoint: <{accessionPrefix}data_point/{i}/>.
                thisDataPoint:
                    :source_line {sourceLine}.
                """.format(accessionPrefix=self.thisAccessionPrefix,
                           i=i,
                           sourceLine=rdfNum(fact.sourceline)))
                if fact.id is not None:
                    dataPoints.append("""
                    thisDataPoint:
                        :xml_id {xmlId}.
                    """.format(
                         xmlId=rdfString(fact.id)))
                if fact.context is not None:
                    dataPoints.append("""
                    thisDataPoint:
                        :context {contextId}.
                    """.format(
                         contextId=rdfString(fact.contextID)))
                    context = fact.context
                    p = self.periodAspectValue(context)
                    if p not in periods:
                        periods.append(p)
                    e = fact.context.entityIdentifier
                    if e not in entityIdentifiers:
                        entityIdentifiers.append(e)
                    for dimVal in context.qnameDims.values():
                        aspectQnamesUsed.add(dimVal.dimensionQname)
                        if dimVal.isExplicit:
                            aspectQnamesUsed.add(dimVal.memberQname)
                            key = (dimVal.dimensionQname, True, dimVal.memberQname)
                        else:
                            key = (dimVal.dimensionQname, False, dimVal.typedMember.innerText)
                        if key not in dimensionIds:
                            dimensionIds[key] = len(dimensions)
                            dimensions.append(key)
                    if fact.isNumeric:
                        dataPoints.append("""
                        thisDataPoint:
                            :effective_value {effectiveValue}.
                        """.format(
                             effectiveValue=rdfString(fact.effectiveValue)))
                        if fact.unit is not None:
                            u = str(fact.unit.measures)  # string for now
                            if u not in units:
                                units.append(u)
                            dataPoints.append("""
                            thisDataPoint:
                                :unit {unit}.
                            """.format(
                                 unit=rdfString(fact.unitID)))
                        if fact.precision:
                            dataPoints.append("""
                            thisDataPoint:
                                :precision {precision}.
                            """.format(
                                 precision=rdfString(fact.precision)))
                        if fact.decimals:
                            dataPoints.append("""
                            thisDataPoint:
                                :decimals {decimals}.
                            """.format(
                                 decimals=rdfString(fact.decimals)))
                    dataPoints.append("""
                    thisDataPoint:
                        :value {value}.
                    """.format(
                         value=rdfString(fact.value))) # compress if very long
            self.execute("Insert data points", dataPoints)
                    
            self.execute("Insert entity identifiers", 
                       ["""
                        @prefix thisEntity: <{accessionPrefix}entity_identifier/{i}>.
                        thisEntity:
                            :scheme {scheme};
                            :identifier {identifier}.
                        """.format(accessionPrefix=self.thisAccessionPrefix,
                                   i=i,
                                   scheme=rdfString(e[0]),
                                   identifier=rdfString(e[1]))
                        for i, e in enumerate(entityIdentifiers)])
                    
            p = []
            for i, period in enumerate(periods):
                p.append("@prefix thisPeriod: <{accessionPrefix}period/{i}>.".format(accessionPrefix=self.thisAccessionPrefix,
                                                                                     i=i))
                if period == 'forever':
                    p.append('thisPeriod: :forever "forever".') 
                elif len(period) == 1:
                    p.append('thisPeriod: :instant {instant}.'.format(
                                instant=rdfString(period[0])))
                else:
                    p.append("""
                        thisPeriod: 
                            :start_date {start_date};
                            :end_date {end_date}.
                        """.format(start_date=rdfString(period[0]),
                                   end_date=rdfString(period[1])))

            self.execute("Insert periods", p)
                    
            self.execute("Insert units", 
                       ["""
                        @prefix thisUnit: <{accessionPrefix}unit/{i}>.
                        thisUnit:
                            :measures {measures}.
                        """.format(accessionPrefix=self.thisAccessionPrefix,
                                   i=i,
                                   measures=rdfString(u))
                        for i, u in enumerate(units)])
                    

              
        self.showStatus("insert aspect proxies")
        self.insertAspectProxies(aspectQnamesUsed)

        if dimensions:
            self.showStatus("insert aspect value selection groups")
            aspValSels = []
            for i, dimensionKey in enumerate(dimensions):
                dimQn, isExplicit, value = dimensionKey
                aspValSels.append("@prefix thisDim: <{accessionPrefix}aspect_value_selection/{i}>."
                                  .format(accessionPrefix=self.thisAccessionPrefix,
                                          i=i))
                if isExplicit:
                    aspValSels.append("""
                        thisDim: 
                            :aspect {dim_aspect};
                            :value {mem_aspect};
                            :name {name}.
                        """.format(dim_aspect=self.aspectId(dimQn),
                                   mem_aspect=self.aspectId(value),
                                   name=rdfString(dimQn.localName + "-" + value.localName)))
                else:
                    aspValSels.append("""
                        thisDim: 
                            :aspect {dim_aspect};
                            :name {dim_name};
                            :typed_value {typed_value}.
                        """.format(dim_aspect=self.aspectId(dimQn),
                                   dim_name=rdfString(dimQn.localName + "-" + str(i)),
                                   typed_value=rdfString(value)))
            
            self.execute("Insert aspect value selection groups", 
                         aspValSels)
        
        # add aspect proxy relationships
        edges = []
        # fact - aspect relationships
        for i, factObjectIndex in enumerate(dataPointObjectIndices):
            fact =  self.modelXbrl.modelObjects[factObjectIndex]
            edges.append("@prefix thisDataPoint: <{accessionPrefix}data_point/{i}>.".format(accessionPrefix=self.thisAccessionPrefix,
                                                                                            i=i))
            edges.append("""
                thisDataPoint: 
                    :base_item {aspectProxy}.
                """.format(aspectProxy=self.aspectId(fact.qname)))
            context = fact.context
            if context is not None:
                # entityIdentifier aspect
                edges.append("""
                    thisDataPoint: 
                        :entity_identifier <{accessionPrefix}entity_identifier/{i}>.
                    """.format(accessionPrefix=self.thisAccessionPrefix,
                               i=entityIdentifiers.index(context.entityIdentifier)))
                # period aspect
                edges.append("""
                    thisDataPoint: 
                        :period <{accessionPrefix}period/{i}>.
                    """.format(accessionPrefix=self.thisAccessionPrefix,
                               i=periods.index(self.periodAspectValue(context))))
                # dimension aspectValueSelections
                for dimVal in context.qnameDims.values():
                    key = (dimVal.dimensionQname, dimVal.isExplicit,
                           dimVal.memberQname if dimVal.isExplicit else dimVal.typedMember.innerText)
                    edges.append("""
                        thisDataPoint: 
                            :aspect_value_selection <{accessionPrefix}aspect_value_selection/{i}>.
                        """.format(accessionPrefix=self.thisAccessionPrefix,
                                   i=dimensionIds[key]))
            if fact.isNumeric and fact.unit is not None:
                # unit aspect
                u = str(fact.unit.measures)  # string for now
                edges.append("""
                    thisDataPoint: 
                        :unit <{accessionPrefix}unit/{i}>.
                    """.format(accessionPrefix=self.thisAccessionPrefix,
                               i=units.index(u)))
            for tupleFact in fact.modelTupleFacts:
                # edge to tuple from item
                edges.append("""
                    thisDataPoint: 
                        :tuple <{accessionPrefix}data_point/{i}>.
                    """.format(accessionPrefix=self.thisAccessionPrefix,
                               i=dataPointObjectIndices.index(tupleFact.objectIndex)))

        self.showStatus("insert aspect relationship edges")
        self.execute("Insert aspect relationship edges", 
                     edges)
        
    def relationshipSetId(self,i):
        return "<{accessionPrefix}rel_set/{i}>".format(accessionPrefix=self.thisAccessionPrefix,
                                                       i=i)
    
    def resourceId(self,i):
        return "<{accessionPrefix}resource/{i}>".format(accessionPrefix=self.thisAccessionPrefix,
                                                        i=i)
    
    def insertRelationshipSets(self):
        self.showStatus("insert relationship sets")
        aspectQnamesUsed = set()
        for i, relationshipSet in enumerate(self.relationshipSets):
            arcrole, linkrole, linkqname, arcqname = relationshipSet
            aspectQnamesUsed.add(linkqname)
            aspectQnamesUsed.add(arcqname)
        self.insertAspectProxies(aspectQnamesUsed)
        
        relSets = []
        for i, relationshipSet in enumerate(self.relationshipSets):
            arcrole, linkrole, linkqname, arcqname = relationshipSet
            relSets.append("""
                @prefix thisRelSet: {relSet} .
                thisRelSet:
                    :arcrole {arcrole};
                    :linkrole {linkrole};
                    :linkdefinition {linkdefinition};
                """.format(relSet=self.relationshipSetId(i),
                           arcrole=rdfString(arcrole),
                           linkrole=rdfString(linkrole),
                           linkdefinition=rdfString(self.modelXbrl.roleTypeDefinition(linkrole) or '')))
            if arcrole not in ("XBRL-dimensions", "XBRL-formulae", "Table-rendering", "XBRL-footnotes"):
                relSets.append("""
                    :linkname {linkname};
                    :arcname {arcname};
                    """.format(linkname=self.aspectId(linkqname),
                               arcname=self.aspectId(arcqname)))
            relSets.append(".")
        self.execute("Insert relationship sets", relSets);
        
        # do tree walk to build relationships with depth annotated, no targetRole navigation
        relE = [] # fromV, toV, label
        resources = set()
        aspectQnamesUsed = set()
        resourceIDs = {} # index by object
        
        def walkTree(rels, seq, depth, relationshipSet, visited, relationshipSetId, doVertices):
            for rel in rels:
                if rel not in visited:
                    visited.add(rel)
                    
                    if not doVertices:
                        _relProp = {'seq':seq,
                                    'depth':depth,
                                    'order':rel.order,
                                    'priority':rel.priority,
                                    'rel_set':self.relationshipSetId(relationshipSetId)}
                    if isinstance(rel.fromModelObject, ModelConcept):
                        if doVertices:
                            aspectQnamesUsed.add(rel.fromModelObject.qname)
                            sourceId = True
                        else:
                            sourceId = self.aspectId(rel.fromModelObject)
                    else:
                        sourceId = None # tbd
                    toModelObject = rel.toModelObject
                    if isinstance(toModelObject, ModelConcept):
                        if doVertices:
                            aspectQnamesUsed.add(toModelObject.qname)
                            targetId = True
                        else:
                            targetId = self.aspectId(toModelObject)
                    elif isinstance(toModelObject, ModelResource):
                        if doVertices:
                            resources.add(toModelObject)
                            targetId = 0 # just can't be None, but doesn't matter on doVertices pass
                        else:
                            if rel.preferredLabel:
                                _relProp['preferred_label'] = rdfString(rel.preferredLabel)
                            if rel.arcrole in (XbrlConst.all, XbrlConst.notAll):
                                _relProp['cube_closed'] = rdfBool(rel.closed)
                            elif rel.arcrole in (XbrlConst.dimensionDomain, XbrlConst.domainMember):
                                _relProp['aspect_value_usable'] = rdfBool(rel.usable)
                            elif rel.arcrole == XbrlConst.summationItem:
                                _relProp['weight'] = rel.weight
                            if relationshipSet.arcrole == "XBRL-dimensions":
                                _relProp['arcrole'] = os.path.basename(rel.arcrole)
                            if toModelObject.role:
                                _relProp['resource_role'] = rdfString(toModelObject.role)
                            targetId = resourceIDs[toModelObject]
                    else:
                        targetId = None # tbd
                    if sourceId is not None and targetId is not None:
                        targetRelationshipSetId = relationshipSetId
                        if relationshipSet.arcrole == "XBRL-dimensions" and rel.targetRole:
                            targetRelSet = self.modelXbrl.relationshipSet(relationshipSet.arcrole, rel.targetRole)
                            for i, relationshipSetKey in enumerate(self.relationshipSets):
                                arcrole, ELR, linkqname, arcqname = relationshipSetKey
                                if arcrole == "XBRL-dimensions" and ELR == rel.targetRole:
                                    targetRelationshipSetId = i
                                    break
                            if not doVertices:
                                _relProp['target_linkrole'] = rel.targetRole
                                _relProp['target_rel_set'] = self.relationshipSetId(targetRelationshipSetId)
                        else:
                            targetRelSet = relationshipSet
                        if doVertices:
                            thisRelId = 0
                        else:
                            _relProp['from'] = sourceId
                            _relProp['to'] = targetId
                            relE.append(_relProp)
                        seq += 1
                        seq = walkTree(targetRelSet.fromModelObject(toModelObject), seq, depth+1, relationshipSet, visited, targetRelationshipSetId, doVertices)
                    visited.remove(rel)
            return seq
        
        for doVertices in range(1,-1,-1):  # pass 0 = vertices, pass 1 = edges
            for i, relationshipSetKey in enumerate(self.relationshipSets):
                arcrole, ELR, linkqname, arcqname = relationshipSetKey
                relationshipSet = self.modelXbrl.relationshipSet(arcrole, ELR, linkqname, arcqname)
                seq = 1               
                for rootConcept in relationshipSet.rootConcepts:
                    seq = walkTree(relationshipSet.fromModelObject(rootConcept), seq, 1, relationshipSet, set(), i, doVertices)
            if doVertices:
                if resources:
                    resourceDefs = []
                    for resource in resources:
                        resourceId = self.resourceId(len(resourceIDs) + 1)
                        resourceDefs.append(resourceId)
                        resourceIDs[resource] = resourceId
                        resourceDefs.append("   :value {0};".format(rdfString( resource.innerText )))  # compress if very long
                        if resource.role:
                            resourceDefs.append("   :role {0};".format(rdfString(resource.role)))
                        resourceDefs.append(".")
                    self.execute("Insert relationship set concept-to-resource relationships", 
                                 resourceDefs)
                    
                self.insertAspectProxies(aspectQnamesUsed)
            else:
                edges = ["@prefix thisRelSet: {relSet} .".format(relSet=self.relationshipSetId(i))]
                for j, rel in enumerate(relE):
                    edges.append("""
                        @prefix thisRel: <{accessionPrefix}rel_set/{i}/rel/{j}>.
                        thisRelSet:
                            :rel thisRel: .
                        {source}
                            :source_rel thisRel: .
                        {target}
                            :target_rel thisRel: .
                        thisRel:
                            :rel_set thisRelSet: ;
                            :source {source} ;
                            :target {target} ;
                        """.format(accessionPrefix=self.thisAccessionPrefix,
                                   i=i, j=j,
                                   source=rel['from'], 
                                   target=rel['to']))
                    if rel['depth'] == 1:
                        edges.append("    :isRoot true ;");
                    for k,v in rel.items():
                        if k not in ('from', 'to'):
                            edges.append("    :{0} {1};".format(k, v))
                    edges.append(".")
                self.execute("Insert relationship edges", edges)
                
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
            # capture message ref's
            msgRefIds = []
            for ref in logEntry['refs']:
                modelObject = self.modelXbrl.modelObject(ref.get('objectId',''))
                # for now just find a concept
                aspectObj = None
                if isinstance(modelObject, (ModelConcept, ModelFact)):
                    aspectObj = modelObject
                elif isinstance(modelObject, ModelRelationship):
                    if isinstance(modelObject.toModelObject, ModelConcept):
                        aspectObj = modelObject.toModelObject
                    elif isinstance(modelObject.fromModelObject, ModelConcept):
                        aspectObj = modelObject.fromModelObject
                if aspectObj is not None:
                    msgRefIds.append(self.aspectId(aspectObj))
                        
            messages.append("""
                <{accessionPrefix}message/{i}>        
                    :code {code};
                    :level {level};
                    :text {text};""".format(accessionPrefix=self.thisAccessionPrefix,
                                            i=i+1,
                                            code=rdfString(logEntry['code']),
                                            level=rdfString(logEntry['level']),
                                            text=rdfString( logEntry['message']['text'] )))
            for j, refId in enumerate(msgRefIds):
                messages.append("    :ref{0} {1};".format(j, refId))
            messages.append(".")
        if messages:
            self.showStatus("insert validation messages")
            self.execute("Insert validation messages", messages)
