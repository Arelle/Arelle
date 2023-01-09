'''
XbrlSemanticGraphDB.py implements a graph database interface for Arelle, based
on a concrete realization of the Abstract Model PWD 2.0 layer.  This is a semantic
representation of XBRL information.

This module provides the execution context for saving a dts and instances in
XBRL Rexter-interfaced graph.  It may be loaded by Arelle's RSS feed, or by individual
DTS and instances opened by interactive or command line/web service mode.

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

'''

import os, io, time, json, socket, logging, zlib
from math import isnan, isinf
from arelle.ModelDtsObject import ModelConcept, ModelResource, ModelRelationship
from arelle.ModelInstanceObject import ModelFact, ModelInlineFact
from arelle.ModelDocument import Type
from arelle.ModelValue import qname, datetime
from arelle.ValidateXbrlCalcs import roundValue
from arelle import XbrlConst, XmlUtil
import urllib.request
from urllib.error import HTTPError, URLError

TRACEGREMLINFILE = None
#TRACEGREMLINFILE = r"c:\temp\rexstertrace.log"  # uncomment to trace SQL on connection (very big file!!!)

def insertIntoDB(modelXbrl,
                 user=None, password=None, host=None, port=None, database=None, timeout=None,
                 product=None, rssItem=None, **kwargs):
    db = None
    try:
        xsgdb = XbrlSemanticGraphDatabaseConnection(modelXbrl, user, password, host, port, database, timeout)
        xsgdb.verifyGraphs()
        xsgdb.insertXbrl(rssItem=rssItem)
        xsgdb.close()
    except Exception as ex:
        if xsgdb is not None:
            try:
                xsgdb.close(rollback=True)
            except Exception as ex2:
                pass
        raise # reraise original exception with original traceback

def isDBPort(host, port, timeout=10):
    # determine if postgres port
    t = 2
    while t < timeout:
        try:
            conn = urllib.request.urlopen("http://{0}:{1}/graphs".format(host, port or '8182'))
            return True # success but doesn't need password
        except HTTPError as err:
            return False # success, this is really a postgres socket, wants user name
        except URLError:
            return False # something is there but not postgres
        except socket.timeout:
            t = t + 2  # relax - try again with longer timeout
    return False

XBRLDBGRAPHS = {
                "filings",       # filings (graph of reports)
                "documents"      # graph of namespace->names->types/elts, datapoints
                                 # any future root vertices go here
                }

HTTPHEADERS = {'User-agent':   'Arelle/1.0',
               'Accept':       'application/json',
               'Content-Type': 'application/json'}

def pyBoolFromDbBool(str):
    return str in ("TRUE", "t")

def pyNoneFromDbNULL(str):
    return None

def dbNum(num):
    if isinstance(num, (int,float)):
        if isinf(num) or isnan(num):
            return None  # not legal in SQL
        return num
    return None

def dbString(s): # compress long strings
    if isinstance(s, str) and len(s) > 512:
        return ''.join(map(chr,zlib.compress(s.encode()))) # compress as utf-8 but return as string
    return s

class XPDBException(Exception):
    def __init__(self, code, message, **kwargs ):
        self.code = code
        self.message = message
        self.kwargs = kwargs
        self.args = ( self.__repr__(), )
    def __repr__(self):
        return _('[{0}] exception: {1}').format(self.code, self.message % self.kwargs)



class XbrlSemanticGraphDatabaseConnection():
    def __init__(self, modelXbrl, user, password, host, port, database, timeout, product):
        self.modelXbrl = modelXbrl
        self.disclosureSystem = modelXbrl.modelManager.disclosureSystem
        #self.conn = RexProConnection(host, int(port or '8182'), (database or 'emptygraph'),
        #                             user=user, password=password)
        connectionUrl = "http://{0}:{1}".format(host, port or '8182')
        self.url = connectionUrl + '/graphs/' + database
        # Create an OpenerDirector with support for Basic HTTP Authentication...
        auth_handler = urllib.request.HTTPBasicAuthHandler()
        if user:
            auth_handler.add_password(realm='rexster',
                                      uri=connectionUrl,
                                      user=user,
                                      passwd=password)
        self.conn = urllib.request.build_opener(auth_handler)
        self.timeout = timeout or 60
        self.verticePropTypes = {}

    def close(self, rollback=False):
        try:
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
        missingRoots = XBRLDBGRAPHS - self.loadGraphRootVertices()
        if missingRoots:  # some are missing
            raise XPDBException("xsgDB:MissingGraphs",
                                _("The following graph roots are missing: %(missingRootNames)s"),
                                missingRootNames=', '.join(t for t in sorted(missingRoots)))

    def execute(self, activity, script, params=None, commit=False, close=True, fetch=True):
        gremlin = {"script": script}
        if params:
            gremlin["params"] = params
        if TRACEGREMLINFILE:
            with io.open(TRACEGREMLINFILE, "a", encoding='utf-8') as fh:
                fh.write("\n\n>>> sent: \n{0}".format(str(gremlin)))
        request = urllib.request.Request(self.url + "/tp/gremlin",
                                         data=json.dumps(gremlin, ensure_ascii=False).encode('utf-8'),
                                         headers=HTTPHEADERS)
        try:
            with self.conn.open(request, timeout=self.timeout) as fp:
                results = json.loads(fp.read().decode('utf-8'))
        except HTTPError as err:
            if err.code == 500: # results are not successful but returned nontheless
                results = json.loads(err.fp.read().decode('utf-8'))
            else:
                raise  # reraise any other errors
        if TRACEGREMLINFILE:
            with io.open(TRACEGREMLINFILE, "a", encoding='utf-8') as fh:
                fh.write("\n\n>>> received: \n{0}".format(str(results)))
        if results.get('success', False) == False:
            raise XPDBException("xsgDB:DatabaseError",
                                _("%(activity)s not successful: %(error)s"),
                                activity=activity, error=results.get('error'))
        return results

    def commit(self):
        self.execute("Commit transaction", "g.commit()")

    def rollback(self):
        self.execute("Rollback transaction", "g.rollback()")

    def loadGraphRootVertices(self):
        self.showStatus("Load/Create graph root vertices")
        # try to create root index
        results = self.execute("Load/Create graph root vertices", """
            def r, v
            // vertex index
            try {  // not all gremlin servers support key index
                if (!("_rlkey" in g.getIndexedKeys(Vertex.class))) {
                    g.createKeyIndex("_rlkey", Vertex.class)
                    //g.createKeyIndex("_class", Vertex.class)
                    g.commit()
                }
            } catch (Exception e) {
            }
            // check if semantic_root vertex already exists
            rIt = g.V('_rlkey', 'semantic_root')  // iterator on semantic_root vertices
            // if none, add it
            if (rIt.hasNext()) {
                r = rIt.next()
            } else {
                r = g.addVertex(['_class':'semantic_root', '_rlkey':'semantic_root'])
            }
            root_vertices = []
            root_classes.each{
                // check if class "it"'s vertex already exists
                vIt = r.out(it)
                // if exists, use that vertex, if not, add it
                if (vIt.hasNext()) {
                    v = vIt.next()
                } else {
                    v = g.addVertex(['_class':it])
                    g.addEdge(r, v, it)
                }
                // return vertex (so plug-in can refer to it by its id
                root_vertices << v
            }
            root_vertices
            """,
            params={"root_classes":list(XBRLDBGRAPHS)})["results"]
        for v in results:
            setattr(self, "root_" + v['_class'] + "_id", int(v['_id']))
        return set(v['_class'] for v in results)

    def getDBsize(self):
        self.showStatus("Get database size (slow operation for now)")
        results = self.execute("Get database size", """
            [g.V.count(), g.E.count()]
            """)["results"]
        return (results[0], results[1])

    def insertXbrl(self, rssItem):
        try:
            # must also have default dimensions loaded
            from arelle import ValidateXbrlDimensions
            ValidateXbrlDimensions.loadDimensionDefaults(self.modelXbrl)

            #initialVcount, initialEcount = self.getDBsize() # don't include in timing, very slow
            startedAt = time.time()
            # self.load()  this done in the verify step
            self.insertFiling(rssItem)
            self.insertDocuments()
            self.insertDataDictionary() # XML namespaces types aspects
            #self.insertRelationshipTypeSets()
            #self.insertResourceRoleSets()
            #self.insertAspectValues()
            self.modelXbrl.profileStat(_("XbrlPublicDB: geport insertion"), time.time() - startedAt)
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
            self.rollback()
            raise

    def insertFiling(self, rssItem):
        self.showStatus("insert filing")
        # filing graph -> document vertices
        new_filing = {'_class':'filing',
                         'is_most_current': True}
        if self.modelXbrl.modelDocument.creationSoftwareComment:
            new_filing['creation_software'] = self.modelXbrl.modelDocument.creationSoftwareComment
        datetimeNow = datetime.datetime.now()
        datetimeNowStr = XmlUtil.dateunionValue(datetimeNow)
        if rssItem is not None:  # sec filing (accession)
            # set self.
            filingType = "SEC_filing"
            # for an RSS Feed entry from SEC, use rss item's filing information
            new_filing['accepted_timestamp'] = XmlUtil.dateunionValue(rssItem.acceptanceDatetime)
            new_filing['filing_date'] = XmlUtil.dateunionValue(rssItem.filingDate)
            new_filing['entity_id'] = rssItem.cikNumber
            new_filing['entity_name'] = rssItem.companyName
            new_filing['standard_industrial_classification'] = rssItem.assignedSic
            new_filing['sec_html_url'] = rssItem.htmlUrl
            new_filing['entry_url'] = rssItem.url
            new_filing['filing_number'] = filing_number = rssItem.accessionNumber
        else:
            # not an RSS Feed item, make up our own filing ID (the time in seconds of epoch)
            intNow = int(time.time())
            filingType = "independent_filing"
            new_filing['accepted_timestamp'] = datetimeNowStr
            new_filing['filing_date'] = datetimeNowStr
            new_filing['entry_url'] = self.modelXbrl.fileSource.url
            new_filing['filing_number'] = filing_number = str(intNow)
        for id in self.execute("Insert filing " + filingType, """
            r = g.v(root_filings_id)
            // check if filing already has a vertex
            vIt = r.out(new_filing.filing_number)
            // use prior vertex, or if none, create new vertex for it
            filing = (vIt.hasNext() ? vIt.next() : g.addVertex(new_filing) )
            // TBD: modify filing timestamp (last-updated-at, if it already existed)
            // check if vertex has edge to root_filings vertex
            vIn = filing.in
            // if no edge, add one
            vIn.hasNext() && vIn.next() == r ?: g.addEdge(r, filing, new_filing.filing_number)
            filing.id
            """,
            params={'root_filings_id': self.root_filings_id,
                    'new_filing': new_filing,
                    'filing_type': filingType,
                    'datetime_now': datetimeNowStr,
                   })["results"]:
            self.filing_id = int(id)

        # relationshipSets are a dts property
        self.relationshipSets = [(arcrole, ELR, linkqname, arcqname)
                                 for arcrole, ELR, linkqname, arcqname in self.modelXbrl.baseSets.keys()
                                 if ELR and (arcrole.startswith("XBRL-") or (linkqname and arcqname))]

    def insertDocuments(self):
        # filing->documents
        #
        self.showStatus("insert documents")
        documents = []
        for modelDocument in self.modelXbrl.urlDocs.values():
            doc = {'_class': 'document',
                   'url': modelDocument.uri,
                   'document_type': modelDocument.gettype()}
            documents.append(doc)
        results = self.execute("Insert documents", """
            results = []
            rDoc = g.v(root_documents_id)
            vFiling = g.v(filing_id)
            // add report if it doesn't exist
            vReportIt = vFiling.out('reports')
            vReport = (vReportIt.hasNext() ? vReportIt.next() : g.addVertex(report) )
            vReportIn = vReport.in('reports').has('id',vFiling.id)
            vReportIn.hasNext() ?: g.addEdge(vFiling, vReport, 'reports')

            urlV = [:]
            urlV_id = [:]
            isNew = [:]
            documents.each{
                vDocIt = rDoc.out(it.url)
                isNew[it.url] = !vDocIt.hasNext()
                vDoc = (vDocIt.hasNext() ? vDocIt.next() : g.addVertex(it))
                // link doc to root doc
                vDocIn = vDoc.in(it.url)
                vDocIn.hasNext() && vDocIn.next() == rDoc ?: g.addEdge(rDoc, vDoc, it.url)
                urlV[it.url] = vDoc
                urlV_id[it.url] = vDoc.id
            }

            // entry document edge to doc root and report
            documents.findAll{it.url == entry_url}.each{
                vEntryDoc = urlV[it.url]
                // link entry point entryDoc to report
                vDocIn = vReport.in('entry_point')
                vDocIn.hasNext() && vDocIn.next() == vReport ?: g.addEdge(vReport, vEntryDoc, 'entry_point')
                vDocIn = vEntryDoc.in('filed_document')
                vDocIn.hasNext() && vDocIn.next() == rDoc ?: g.addEdge(vReport, vEntryDoc, 'filed_document')
            }

            // referenced document edge to entry document
            documents.findAll{it.url != entry_url}.each{
                vRefDoc = urlV[it.url]
                // link refDoc to vEntryDoc
                vDocIn = vRefDoc.in('referenced_document')
                vDocIn.hasNext() && vDocIn.next() == vEntryDoc ?: g.addEdge(vEntryDoc, vRefDoc, 'referenced_document')
            }
            [vReport.id, urlV_id, isNew]
            """,
            params={'root_documents_id': self.root_documents_id,
                    'filing_id': self.filing_id,
                    'entry_url': self.modelXbrl.modelDocument.uri,
                    'report': {
                        '_class': 'report'},
                    'documents': documents
                    })["results"]
        report_id, doc_id_list, doc_isNew_list = results # unpack list
        self.report_id = int(report_id)
        self.document_ids = dict( (url, int(id)) for url, id in doc_id_list.items() )
        self.document_isNew = dict( (url, isNew) for url,isNew in doc_isNew_list.items() )

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

        if any((not self.document_isNew[modelDocument.uri])
               for modelDocument in self.modelXbrl.urlDocs.values()):
            conceptsUsed = self.conceptsUsed()

        for modelDocument in self.modelXbrl.urlDocs.values():
            self.showStatus("insert DataDictionary " + modelDocument.basename)

            # don't re-output existing documents
            if modelDocument.type == Type.SCHEMA:
                isNewDocument = self.document_isNew[modelDocument.uri]
                modelConcepts = [modelConcept
                                 for modelConcept in self.modelXbrl.qnameConcepts.values()
                                 if modelConcept.modelDocument is modelDocument and
                                    (isNewDocument or modelConcept in conceptsUsed)]
                if isNewDocument:
                    # adding document as new
                    modelTypes = [modelType
                                  for modelType in self.modelXbrl.qnameTypes.values()
                                  if modelType.modelDocument is modelDocument]
                    conceptAspects = []
                    for modelConcept in modelConcepts:
                        conceptAspect = {'_class': 'aspect',
                                         'name': modelConcept.name}
                        if modelConcept.isAbstract:
                            conceptAspect['isAbstract'] = True
                        if modelConcept.periodType:
                            conceptAspect['periodType'] = modelConcept.periodType
                        if modelConcept.balance:
                            conceptAspect['balance'] = modelConcept.balance
                        for propertyName in ('isItem', 'isTuple', 'isLinkPart', 'isNumeric', 'isMonetary',
                                             'isExplicitDimension', 'isTypedDimension', 'isDomainMember', 'isHypercubeItem',
                                             'isShares', 'isTextBlock'):
                            propertyValue = getattr(modelConcept, propertyName, None)
                            if propertyValue:
                                conceptAspect[propertyName] = propertyValue
                        conceptAspects.append(conceptAspect)
                    roleTypes = [modelRoleType
                                 for modelRoleTypes in self.modelXbrl.roleTypes.values()
                                 for modelRoleType in modelRoleTypes]
                    arcroleTypes = [modelRoleType
                                 for modelRoleTypes in self.modelXbrl.arcroleTypes.values()
                                 for modelRoleType in modelRoleTypes]
                    activity = "Insert data dictionary types, aspects, roles, and arcroles for " + modelDocument.uri
                    results = self.execute(activity, "//" + activity + """
                        reportV = g.v(report_id)
                        docV = g.v(document_id)
                        // add dictV if it doesn't exist
                        dictIt = docV.out('doc_data_dictionary')
                        dictV = (dictIt.hasNext() ? dictIt.next() : g.addVertex(dict) )
                        // add edge from reportV to dictV if not present
                        vReportIn = reportV.in('report_data_dictionary').has('id',reportV.id)
                        vReportIn.hasNext() ?: g.addEdge(reportV, dictV, 'report_data_dictionary')
                        // add edge from docV to dictV if not present
                        vDictIn = dictV.in('doc_data_dictionary').has('id',docV.id)
                        vDictIn.hasNext() ?: g.addEdge(docV, dictV, 'doc_data_dictionary')
                        type_ids = []
                        types.each{
                            typeV = g.addVertex(it)
                            type_ids << typeV.id
                            g.addEdge(dictV, typeV, 'data_type')
                        }
                        aspectsV = g.addVertex(['_class':'aspects'])
                        g.addEdge(dictV, aspectsV, 'aspects')
                        aspect_ids = []
                        aspects.each{
                            aspectV = g.addVertex(it)
                            aspect_ids << aspectV.id
                            g.addEdge(dictV, aspectV, 'aspect')
                            g.addEdge(aspectsV, aspectV, it.name.hashCode().toString() )
                        }
                        role_type_ids = []
                        roletypes.each{
                            roleTypeV = g.addVertex(it)
                            role_type_ids << roleTypeV.id
                            g.addEdge(docV, roleTypeV, 'role_type')
                        }
                        arcrole_type_ids = []
                        arcroletypes.each{
                            arcroleTypeV = g.addVertex(it)
                            arcrole_type_ids << arcroleTypeV.id
                            g.addEdge(docV, arcroleTypeV, 'arcrole_type')
                        }
                        [dictV.id, type_ids, aspect_ids, role_type_ids, arcrole_type_ids]
                        """,
                        params={
                        'report_id': self.report_id,
                        'document_id': self.document_ids[modelDocument.uri],
                        'dict': {
                            '_class': 'data_dictionary',
                            'namespace': modelDocument.targetNamespace},
                        'types': [{
                            '_class': 'data_type',
                            'name': modelType.name
                              } for modelType in modelTypes],
                        'aspects': conceptAspects,
                        'roletypes': [{
                            '_class': 'role_type',
                            'uri': modelRoleType.roleURI,
                            'definition': modelRoleType.definition or ''
                              } for modelRoleType in roleTypes],
                        'arcroletypes': [{
                            '_class': 'arcrole_type',
                            'uri': modelRoleType.arcroleURI,
                            'definition': modelRoleType.definition or '',
                            'cyclesAllowed': modelRoleType.cyclesAllowed
                              } for modelRoleType in arcroleTypes],
                        })["results"]
                    dict_id, type_ids, aspect_ids, role_type_ids, arcrole_type_ids = results
                    self.dict_id = int(dict_id)
                    for iT, type_id in enumerate(type_ids):
                        self.type_id[modelTypes[iT].qname] = int(type_id)
                    for iC, aspect_id in enumerate(aspect_ids):
                        self.aspect_id[modelConcepts[iC].qname] = int(aspect_id)
                    for iRT, roleType_id in enumerate(role_type_ids):
                        self.roleType_id[roleTypes[iRT].roleURI] = int(roleType_id)
                    for iAT, arcroleType_id in enumerate(arcrole_type_ids):
                        self.arcroleType_id[arcroleTypes[iAT].arcroleURI] = int(arcroleType_id)
                    '''
                    results = self.execute("Insert data dictionary types, and arcroles for " +
                                           modelDocument.uri, """
                        reportV = g.v(report_id)
                        docV = g.v(document_id)
                        // add dictV if it doesn't exist
                        dictIt = docV.out('doc_data_dictionary')
                        dictV = (dictIt.hasNext() ? dictIt.next() : g.addVertex(dict) )
                        // add edge from reportV to dictV if not present
                        vReportIn = reportV.in('report_data_dictionary').has('id',reportV.id)
                        vReportIn.hasNext() ?: g.addEdge(reportV, dictV, 'report_data_dictionary')
                        // add edge from docV to dictV if not present
                        vDictIn = dictV.in('doc_data_dictionary').has('id',docV.id)
                        vDictIn.hasNext() ?: g.addEdge(docV, dictV, 'doc_data_dictionary')
                        type_ids = []
                        types.each{
                            typeV = g.addVertex(it)
                            type_ids << typeV.id
                            g.addEdge(dictV, typeV, 'data_type')
                        }
                        arcrole_type_ids = []
                        arcroletypes.each{
                            arcroleTypeV = g.addVertex(it)
                            arcrole_type_ids << arcroleTypeV.id
                            g.addEdge(docV, arcroleTypeV, 'arcrole_type')
                        }
                        [dictV.id, type_ids, arcrole_type_ids]
                        """,
                        params={
                        'report_id': self.report_id,
                        'document_id': self.document_ids[modelDocument.uri],
                        'dict': {
                            '_class': 'data_dictionary',
                            'namespace': modelDocument.targetNamespace},
                        'types': [{
                            '_class': 'data_type',
                            'name': modelType.name
                              } for modelType in modelTypes],
                        'arcroletypes': [{
                            '_class': 'arcrole_type',
                            'uri': modelRoleType.arcroleURI,
                            'definition': modelRoleType.definition or '',
                            'cyclesAllowed': modelRoleType.cyclesAllowed
                              } for modelRoleType in arcroleTypes],
                        })["results"]
                    dict_id, type_ids, arcrole_type_ids = results
                    self.dict_id = int(dict_id)
                    for iT, type_id in enumerate(type_ids):
                        self.type_id[modelTypes[iT].qname] = int(type_id)
                    for iAT, arcroleType_id in enumerate(arcrole_type_ids):
                        self.arcroleType_id[arcroleTypes[iAT].arcroleURI] = int(arcroleType_id)

                    results = self.execute("Insert data dictionary roles for " +
                                           modelDocument.uri, """
                        reportV = g.v(report_id)
                        docV = g.v(document_id)
                        // add dictV if it doesn't exist
                        dictIt = docV.out('doc_data_dictionary')
                        dictV = (dictIt.hasNext() ? dictIt.next() : g.addVertex(dict) )
                        // add edge from reportV to dictV if not present
                        vReportIn = reportV.in('report_data_dictionary').has('id',reportV.id)
                        vReportIn.hasNext() ?: g.addEdge(reportV, dictV, 'report_data_dictionary')
                        // add edge from docV to dictV if not present
                        vDictIn = dictV.in('doc_data_dictionary').has('id',docV.id)
                        vDictIn.hasNext() ?: g.addEdge(docV, dictV, 'doc_data_dictionary')
                        role_type_ids = []
                        roletypes.each{
                            roleTypeV = g.addVertex(it)
                            role_type_ids << roleTypeV.id
                            g.addEdge(docV, roleTypeV, 'role_type')
                        }
                        role_type_ids
                        """,
                        params={
                        'report_id': self.report_id,
                        'document_id': self.document_ids[modelDocument.uri],
                        'dict': {
                            '_class': 'data_dictionary',
                            'namespace': modelDocument.targetNamespace},
                        'roletypes': [{
                            '_class': 'role_type',
                            'uri': modelRoleType.roleURI,
                            'definition': modelRoleType.definition or ''
                              } for modelRoleType in roleTypes],
                        })["results"]
                    role_type_ids = results
                    for iRT, roleType_id in enumerate(role_type_ids):
                        self.roleType_id[roleTypes[iRT].roleURI] = int(roleType_id)


                    results = self.execute("Insert data dictionary aspects for " +
                                           modelDocument.uri, """
                        reportV = g.v(report_id)
                        docV = g.v(document_id)
                        // add dictV if it doesn't exist
                        dictIt = docV.out('doc_data_dictionary')
                        dictV = (dictIt.hasNext() ? dictIt.next() : g.addVertex(dict) )
                        // add edge from reportV to dictV if not present
                        vReportIn = reportV.in('report_data_dictionary').has('id',reportV.id)
                        vReportIn.hasNext() ?: g.addEdge(reportV, dictV, 'report_data_dictionary')
                        // add edge from docV to dictV if not present
                        vDictIn = dictV.in('doc_data_dictionary').has('id',docV.id)
                        vDictIn.hasNext() ?: g.addEdge(docV, dictV, 'doc_data_dictionary')
                        aspectsV = g.addVertex(['_class':'aspects'])
                        g.addEdge(dictV, aspectsV, 'aspects')
                        aspect_ids = []
                        aspects.each{
                            aspectV = g.addVertex(it)
                            aspect_ids << aspectV.id
                            g.addEdge(dictV, aspectV, 'aspect')
                            g.addEdge(aspectsV, aspectV, it.name.hashCode().toString() )
                        }
                        aspect_ids
                        """,
                        params={
                        'report_id': self.report_id,
                        'document_id': self.document_ids[modelDocument.uri],
                        'dict': {
                            '_class': 'data_dictionary',
                            'namespace': modelDocument.targetNamespace},
                        'aspects': conceptAspects,
                        })["results"]
                    aspect_ids = results
                    for iC, aspect_id in enumerate(aspect_ids):
                        self.aspect_id[modelConcepts[iC].qname] = int(aspect_id)
                    '''
                else: # not new, just get aspect (concept) id's
                    results = self.execute("Access existing data dictionary types, aspects, roles, and arcroles for " +
                                           modelDocument.uri, """//Access existing data dictionary aspects
                        aspect_ids = []
                        g.v(document_id).out('doc_data_dictionary').out('aspects').each {
                            aspectsV = it // dereference vertex from pipeline
                            aspect_names.each{
                                aspect_name = it
                                aspectsV.out(aspect_name.hashCode().toString()).each{
                                    if (it.name == aspect_name)
                                        aspect_ids << it.id
                                }
                            }
                        }
                        aspect_ids
                        """,
                        params={'document_id': self.document_ids[modelDocument.uri],
                            'aspect_names': [modelConcept.name for modelConcept in modelConcepts],
                        })["results"]
                    for iC, aspect_id in enumerate(results):
                        self.aspect_id[modelConcepts[iC].qname] = int(aspect_id) if aspect_id is not None else None

        typeDerivationEdges = []
        for modelType in self.modelXbrl.qnameTypes.values():
            if self.document_isNew[modelType.modelDocument.uri]:
                qnamesDerivedFrom = modelType.qnameDerivedFrom
                if not isinstance(qnamesDerivedFrom, (list,tuple)): # list if a union
                    qnamesDerivedFrom = (qnamesDerivedFrom,)
                for qnameDerivedFrom in qnamesDerivedFrom:
                    if modelType.qname in self.type_id and qnameDerivedFrom in self.type_id:
                        typeDerivationEdges.append({
                                'from_id': self.type_id[modelType.qname],
                                'to_id': self.type_id[qnameDerivedFrom],
                                'rel': "derived_from"})
        ### was ### g.addEdge(g.v(it.from_id), g.v(it.to_id), it.rel)
        self.execute("Insert type derivation edges", """
            e.each{
                fromV = g.v(it.from_id)
                toV = g.v(it.to_id)
                vOutIt = fromV.out(it.rel).has('id',toV.id)
                vOutIt.hasNext() ?: g.addEdge(fromV, toV, it.rel)
            }
            """,
            params={'e': typeDerivationEdges})
        aspectEdges = []
        for modelConcept in self.modelXbrl.qnameConcepts.values():
            if self.document_isNew[modelConcept.modelDocument.uri]:
                if modelConcept.qname in self.aspect_id:
                    if modelConcept.typeQname in self.type_id:
                        aspectEdges.append({'from_id': self.aspect_id[modelConcept.qname],
                                            'to_id': self.type_id[modelConcept.typeQname],
                                            'rel': "data_type"})
                    if modelConcept.substitutesForQname in self.type_id:
                        aspectEdges.append({'from_id': self.aspect_id[modelConcept.qname],
                                            'to_id': self.type_id[modelConcept.substitutesForQname.typeQname],
                                            'rel': "substitutes_for"})
                    baseXbrliTypeQnames = modelConcept.baseXbrliTypeQname # may be union or single
                    if not isinstance(baseXbrliTypeQnames, (list,tuple)):
                        baseXbrliTypeQnames = (baseXbrliTypeQnames,) # was single base type
                    for baseXbrliTypeQname in baseXbrliTypeQnames:
                        if baseXbrliTypeQname in self.type_id:
                            aspectEdges.append({'from_id': self.aspect_id[modelConcept.qname],
                                                'to_id': self.type_id[baseXbrliTypeQname],
                                                'rel': "base_xbrli_type"})
        self.execute("Insert aspect edges for data type, substitutes for, and base xbrli type", """
            e.each{
                fromV = g.v(it.from_id)
                toV = g.v(it.to_id)
                vOutIt = fromV.out(it.rel).has('id',toV.id)
                vOutIt.hasNext() ?: g.addEdge(fromV, toV, it.rel)
            }
        """,
        params={'e': aspectEdges})

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
                        if qname not in self.aspect_proxy_id and qname in self.aspect_id]
        #print ("missing qnames: " + ", ".join(str(q) for q in aspectQnames if q not in self.aspect_id))
        results = self.execute("Insert aspect proxies", """
            reportV = g.v(report_id)
            aspectProxyV_ids = []
            aspect_ids.each{
                aspectV = g.v(it)
                aspectProxyV = g.addVertex(['_class':'aspect_proxy'])
                aspectProxyV_ids << aspectProxyV.id
                g.addEdge(aspectV, aspectProxyV, 'proxy')
                g.addEdge(reportV, aspectProxyV, 'report_aspect_proxy')
            }
            aspectProxyV_ids
            """,
            params={'report_id': self.report_id,
                    'aspect_ids': [self.aspect_id[qname] for qname in aspectQnames]}
            )["results"]
        for i, proxy_id in enumerate(results):
            self.aspect_proxy_id[aspectQnames[i]] = proxy_id

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
        if self.modelXbrl.modelDocument.type in (Type.INSTANCE, Type.INLINEXBRL):
            instanceDocument = self.modelXbrl.modelDocument
            dataPoints = []
            entityIdentifiers = [] # index by (scheme, identifier)
            periods = []  # index by (instant,) or (start,end) dates
            units = []  # index by measures (qnames set)
            for fact in self.modelXbrl.factsInInstance:
                aspectQnamesUsed.add(fact.concept.qname)
                dataPointObjectIndices.append(fact.objectIndex)
                datapoint = {'_class': 'data_point',
                             #'name': str(fact.qname), not needed, get from aspect (concept)
                             'source_line': fact.sourceline}
                datapoint['xml_id'] = XmlUtil.elementFragmentIdentifier(fact)
                if fact.context is not None:
                    datapoint['context'] = fact.contextID
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
                            key = (dimVal.dimensionQname, False, dimVal.typedMember.stringValue)
                        if key not in dimensions:
                            dimensions.append(key)
                    if fact.isNumeric:
                        datapoint['effective_value'] = str(fact.effectiveValue)
                        if fact.unit is not None:
                            u = str(fact.unit.measures)  # string for now
                            if u not in units:
                                units.append(u)
                            datapoint['unit']= fact.unitID
                        if fact.precision:
                            datapoint['precision'] = fact.precision
                        if fact.decimals:
                            datapoint['decimals'] = fact.decimals
                    datapoint['value'] = dbString( str(fact.value) ) # compress if very long
                dataPoints.append(datapoint)
            results = self.execute("Insert data points", """
                docV = g.v(document_id)
                dpIt = docV.out('data_points')
                datapointsV = (dpIt.hasNext() ? dpIt.next() : g.addVertex(datapoints_set) )
                dpE = docV.out('data_points').has('id', datapointsV.id)
                dpE.hasNext() ?: g.addEdge(docV, datapointsV, 'data_points')
                datapointV_ids = []
                datapoints.each{
                    dpV = g.addVertex(it)
                    datapointV_ids << dpV.id
                    g.addEdge(datapointsV, dpV, 'data_point')
                }
                [datapointsV.id, datapointV_ids]
                """,
                params={'document_id': self.document_ids[instanceDocument.uri],
                        'datapoints_set': {
                            '_class': 'datapoints_set'},
                        'datapoints': dataPoints}
                )["results"]
            datapointsV_id, datapointVids_list = results
            dataPointVertexIds = dict((dataPointObjectIndices[i], int(id))
                                      for i, id in enumerate(datapointVids_list))

            results = self.execute("Insert entity identifiers", """
                entIdentV_ids = []
                entityIdentifiers.each{
                    entIdentV = g.addVertex(it)
                    entIdentV_ids << entIdentV.id
                }
                entIdentV_ids
                """,
                params={'entityIdentifiers': [{'_class':'entity_identifier',
                                               'scheme': e[0],
                                               'identifier': e[1]}
                                              for e in entityIdentifiers]}
                )["results"]
            entityIdentifierVertexIds = [int(entIdent_id) for entIdent_id in results]

            p = []
            for period in periods:
                if period == 'forever':
                    p.append({'_class': 'period',
                              'forever': 'forever'})
                elif len(period) == 1:
                    p.append({'_class': 'period',
                              'instant': period[0]})
                else:
                    p.append({'_class': 'period',
                              'start_date': period[0],
                              'end_date': period[1]})
            results = self.execute("Insert periods", """
                periodV_ids = []
                periods.each{
                    periodV = g.addVertex(it)
                    periodV_ids << periodV.id
                }
                periodV_ids
                """,
                params={'periods': p}
                )["results"]
            periodVertexIds = [int(period_id) for period_id in results]

            results = self.execute("Insert units", """
                unitV_ids = []
                units.each{
                    unitV = g.addVertex(it)
                    unitV_ids << unitV.id
                }
                unitV_ids
                """,
                params={'units': [{'_class':'unit',
                                   'measures': u}
                                  for u in units]}
                )["results"]
            unitVertexIds = [int(unit_id) for unit_id in results]

            if dimensions:
                self.showStatus("insert aspect value selection groups")
                aspValSels = []
                for dimQn, isExplicit, value in dimensions:
                    if isExplicit:
                        aspValSels.append({'_class': 'aspect_value_selection',
                                           'name':dimQn.localName + '-' + value.localName})
                    else:
                        aspValSels.append({'_class': 'aspect_value_selection',
                                           'name': dimQn.localName + '-' + str(len(aspValSels)+1),
                             '             typed_value': value})

                results = self.execute("Insert aspect value selection groups", """
                    aspectValSelGroupV = g.addVertex(aspect_val_sel_group)
                    aspectValSelV_ids = []
                    aspect_val_sels.each{
                        aspectValSelV = g.addVertex(it)
                        aspectValSelV_ids << aspectValSelV.id
                        g.addEdge(aspectValSelGroupV, aspectValSelV, 'aspect_value_selection_group')
                    }
                    [aspectValSelGroupV.id, aspectValSelV_ids]
                    """,
                    params={'aspect_val_sel_group': {'_class': 'aspect_value_selection_group'},
                            'aspect_val_sels': aspValSels}
                    )["results"]
                aspValSelGrpV_id, aspValSelV_ids_list = results
                aspValSelVertexIds = [int(aspValSel_id) for aspValSel_id in aspValSelV_ids_list]

            else:
                aspValSelVertexIds = []
            dimValAspValSelVertexIds = dict((dimensions[i], aspValSel_id)
                                            for i, aspValSel_id in enumerate(aspValSelVertexIds))

        self.showStatus("insert aspect proxies")
        self.insertAspectProxies(aspectQnamesUsed)

        if dimensions:
            self.showStatus("insert dimension member edges")
            # connect aspectValueSelection to concept dimension and member concepts
            self.execute("Insert dimension member edges", """
                aspects.each{
                    g.addEdge(g.v(it.aspValSel_id), g.v(it.dimension_id), 'aspect')
                }
                aspect_values.each{
                    g.addEdge(g.v(it.aspValSel_id), g.v(it.member_id), 'aspect_value')
                }
                []
                """,
                params={'aspects': [{
                            'aspValSel_id': aspValSel_id,
                            'dimension_id': self.aspect_proxy_id[dimQn]}
                            for i, aspValSel_id in enumerate(aspValSelVertexIds)
                            for dimQn,isExplicit,memQn in dimensions[i:i+1]],
                        'aspect_values': [{
                            'aspValSel_id': aspValSel_id,
                            'member_id': self.aspect_proxy_id[memQn]}
                            for i, aspValSel_id in enumerate(aspValSelVertexIds)
                            for dimQn,isExplicit,memQn in dimensions[i:i+1]
                            if isExplicit]}
                )["results"]

        # add aspect proxy relationships
        edges = []
        if self.modelXbrl.modelDocument.type in (Type.INSTANCE, Type.INLINEXBRL):
            # aspect value - aspect relationships
            for aspectProxyId, rel, aspectValueVertexIds in (
                (self.aspect_proxy_id[XbrlConst.qnXbrliIdentifier], 'entity_identifier_aspects', entityIdentifierVertexIds),
                (self.aspect_proxy_id[XbrlConst.qnXbrliPeriod], 'period_aspects', periodVertexIds),
                (self.aspect_proxy_id[XbrlConst.qnXbrliUnit], 'unit_aspects', unitVertexIds) ):
                for aspectValueVertexId in aspectValueVertexIds:
                    edges.append({'from_id': aspectValueVertexId,
                                  'to_id': aspectProxyId,
                                  'rel': rel})
        # fact - aspect relationships
        for i, factObjectIndex in enumerate(dataPointObjectIndices):
            fact =  self.modelXbrl.modelObjects[factObjectIndex]
            dataPoint_id = dataPointVertexIds[factObjectIndex]
            # fact concept aspect
            edges.append({
                'from_id': dataPoint_id,
                'to_id': self.aspect_proxy_id[fact.qname],
                'rel': "base_item"})
            context = fact.context
            if context is not None:
                # entityIdentifier aspect
                edges.append({
                    'from_id': dataPoint_id,
                    'to_id': entityIdentifierVertexIds[entityIdentifiers.index(context.entityIdentifier)],
                    'rel': "entity_identifier"})
                # period aspect
                edges.append({
                    'from_id': dataPoint_id,
                    'to_id': periodVertexIds[periods.index(self.periodAspectValue(context))],
                    'rel': "period"})
                # dimension aspectValueSelections
                for dimVal in context.qnameDims.values():
                    key = (dimVal.dimensionQname, dimVal.isExplicit,
                           dimVal.memberQname if dimVal.isExplicit else dimVal.typedMember.stringValue)
                    edges.append({
                        'from_id': dataPoint_id,
                        'to_id': dimValAspValSelVertexIds[key],
                        'rel': "aspect_value_selection"})
            if fact.isNumeric and fact.unit is not None:
                # unit aspect
                u = str(fact.unit.measures)  # string for now
                edges.append({
                    'from_id': dataPoint_id,
                    'to_id': unitVertexIds[units.index(u)],
                    'rel': "_unit"})
            for tupleFact in fact.modelTupleFacts:
                # edge to tuple from item
                edges.append({
                    'from_id': dataPointVertexIds[tupleFact.objectIndex],
                    'to_id': dataPoint_id,
                    'rel': "tuple"})

        self.showStatus("insert aspect relationship edges")
        results = self.execute("Insert aspect relationship edges", """
            e.each{g.addEdge(g.v(it.from_id), g.v(it.to_id), it.rel)}
            []
            """,
            params={'e': edges})["results"]

    def insertRelationshipSets(self):
        self.showStatus("insert relationship sets")
        results = self.execute("Insert relationship sets", """
            reportV = g.v(report_id)
            relSetsV = g.addVertex(relSets)
            g.addEdge(reportV, relSetsV, 'relationship_sets')
            relSetV_ids = []
            relSet.each{
                relSetV = g.addVertex(it)
                relSetV_ids << relSetV.id
                g.addEdge(relSetsV, relSetV, 'relationship_set')}
            [relSetsV.id, relSetV_ids]
            """,
            params={
                'report_id': self.report_id,
                'relSets': {
                    '_class': 'relationship_sets'},
                'relSet': [{
                    '_class': 'relationship_set',
                    'arcrole': arcrole,
                    'linkrole': linkrole,
                    'linkdefinition': self.modelXbrl.roleTypeDefinition(linkrole) or '',
                    'linkname': str(linkqname),
                    'arcname': str(arcqname)
                    } for arcrole, linkrole, linkqname, arcqname in self.relationshipSets]
            })["results"]
        relSetsV_id, relSetV_ids_list = results
        relationshipSetIDs = [int(relSet_id) for relSet_id in relSetV_ids_list]

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
                                    '_order':rel.order,
                                    'priority':rel.priority,
                                    'rel_set':relationshipSetId}
                    if isinstance(rel.fromModelObject, ModelConcept):
                        if doVertices:
                            aspectQnamesUsed.add(rel.fromModelObject.qname)
                            sourceId = True
                        else:
                            sourceId = self.aspect_proxy_id[rel.fromModelObject.qname]
                    else:
                        sourceId = None # tbd
                    toModelObject = rel.toModelObject
                    if isinstance(toModelObject, ModelConcept):
                        if doVertices:
                            aspectQnamesUsed.add(toModelObject.qname)
                            targetId = True
                        else:
                            targetId = self.aspect_proxy_id[toModelObject.qname]
                    elif isinstance(toModelObject, ModelResource):
                        if doVertices:
                            resources.add(toModelObject)
                            targetId = 0 # just can't be None, but doesn't matter on doVertices pass
                        else:
                            if rel.preferredLabel:
                                _relProp['preferred_label'] = rel.preferredLabel
                            if rel.arcrole in (XbrlConst.all, XbrlConst.notAll):
                                _relProp['cube_closed'] = rel.closed
                            elif rel.arcrole in (XbrlConst.dimensionDomain, XbrlConst.domainMember):
                                _relProp['aspect_value_usable'] = rel.usable
                            elif rel.arcrole == XbrlConst.summationItem:
                                _relProp['weight'] = rel.weight
                            if relationshipSet.arcrole == "XBRL-dimensions":
                                _relProp['arcrole'] = os.path.basename(rel.arcrole)
                            if toModelObject.role:
                                _relProp['resource_role'] = toModelObject.role
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
                                    targetRelationshipSetId = relationshipSetIDs[i]
                                    break
                            if not doVertices:
                                _relProp['target_linkrole'] = rel.targetRole
                                _relProp['target_rel_set'] = targetRelationshipSetId
                        else:
                            targetRelSet = relationshipSet
                        if doVertices:
                            thisRelId = 0
                        else:
                            relE.append({'from_id': sourceId, 'to_id': targetId, 'label': 'rel', 'properties': _relProp})
                        seq += 1
                        seq = walkTree(targetRelSet.fromModelObject(toModelObject), seq, depth+1, relationshipSet, visited, targetRelationshipSetId, doVertices)
                    visited.remove(rel)
            return seq

        for doVertices in range(1,-1,-1):  # pass 0 = vertices, pass 1 = edges
            for i, relationshipSetKey in enumerate(self.relationshipSets):
                arcrole, ELR, linkqname, arcqname = relationshipSetKey
                relationshipSetId = relationshipSetIDs[i]
                relationshipSet = self.modelXbrl.relationshipSet(arcrole, ELR, linkqname, arcqname)
                seq = 1
                for rootConcept in relationshipSet.rootConcepts:
                    if not doVertices:
                        aspectId = self.aspect_proxy_id[rootConcept.qname]
                        relE.append({'from_id': relationshipSetId, 'to_id': aspectId, 'label': 'root'})
                    seq = walkTree(relationshipSet.fromModelObject(rootConcept), seq, 1, relationshipSet, set(), relationshipSetId, doVertices)
            if doVertices:
                if resources:
                    resourceV = []
                    resourceObjs = []
                    for resource in resources:
                        resourceParam = {'_class': resource.localName,
                                         'value': dbString( resource.stringValue )} # compress if very long
                        if resource.role:
                            resourceParam['role'] = resource.role
                        resourceV.append(resourceParam)
                        resourceObjs.append(resource) # need these in a list in same order as resoureV
                    for i, v_id in enumerate(self.execute("Insert relationship set concept-to-resource relationships", """
                        resourceV_ids = []
                        resourceV.each{resourceV_ids << g.addVertex(it).id}
                        resourceV_ids
                        """,
                        params={'resourceV': resourceV}
                        )["results"]):
                        resourceIDs[resourceObjs[i]] = int(v_id)

                self.insertAspectProxies(aspectQnamesUsed)
            else:
                self.execute("Insert relationship edges", """
                    relE.each{
                        if (it.properties) {
                            g.addEdge(g.v(it.from_id), g.v(it.to_id), it.label, it.properties)
                        } else {
                            g.addEdge(g.v(it.from_id), g.v(it.to_id), it.label)
                        }
                    }
                    []
                    """,
                    params={'relE': relE}
                    )["results"]

                # TBD: do we want to link resources to the report (by role, class, or otherwise?)

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
                aspectQname = None
                if isinstance(modelObject, (ModelConcept, ModelFact)):
                    aspectQname = modelObject.qname
                elif isinstance(modelObject, ModelRelationship):
                    if isinstance(modelObject.toModelObject, ModelConcept):
                        aspectQname = modelObject.toModelObject.qname
                    elif isinstance(modelObject.fromModelObject, ModelConcept):
                        aspectQname = modelObject.fromModelObject.qname
                if aspectQname is not None and aspectQname in self.aspect_proxy_id:
                    msgRefIds.append(self.aspect_proxy_id[aspectQname])


            messages.append({'_class': 'message',
                             'seq': i + 1,
                             'code': logEntry['code'],
                             'level': logEntry['level'],
                             'text': dbString( logEntry['message']['text'] ),
                             'refs': msgRefIds})
        if messages:
            self.showStatus("insert validation messages")
            results = self.execute("Insert validation messages", """
                filingV = g.v(filing_id)
                msgsV = g.addVertex(['_class':'messages'])
                g.addEdge(filingV, msgsV, 'validation_messages')
                msgV_ids = []
                messages.each{
                    msgV = g.addVertex(it.subMap(['_class','seq','code','level','text']))
                    msgV_ids << msgV.id
                    g.addEdge(msgsV, msgV, 'message')
                    it['refs'].each{
                        g.addEdge(msgV, g.v(it), 'message_ref')
                    }}
                msgV_ids
                """,
                params={
                    'filing_id': self.filing_id,
                    'messages': messages
                })["results"]
            relationshipSetIDs = [int(msg_id) for msg_id in results]
