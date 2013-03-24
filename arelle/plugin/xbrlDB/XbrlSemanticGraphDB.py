'''
XbrlSemanticGraphDB.py implements a graph database interface for Arelle, based
on a concrete realization of the Abstract Model PWD 2.0 layer.  This is a semantic 
representation of XBRL information. 

This module provides the execution context for saving a dts and instances in 
XBRL Rexter-interfaced graph.  It may be loaded by Arelle's RSS feed, or by individual
DTS and instances opened by interactive or command line/web service mode.

(c) Copyright 2013 Mark V Systems Limited, California US, All rights reserved.  
Mark V copyright applies to this software, which is licensed according to the terms of Arelle(r).

to do:

1) add AMTF cube regions (dimensions)
2) add resources (labels, etc)
3) check existence of (shared) documents and contained elements before adding
4) tuple structure declaration (particles in elements of data dictionary?)
5) tuple structure (instance facts)
6) add footnote resources to relationships (and test with EDInet footnote references)
7) test some filings with text blocks (shred them?)  (30mB - 50mB sized text blocks?)
8) add mappings to, or any missing relationships, of Charlie's financial model

'''

import os, io, re, time, json, socket
from math import isnan, isinf
from arelle.ModelDtsObject import ModelConcept, ModelResource
from arelle.ModelDocument import Type
from arelle.ModelValue import qname, datetime
from arelle.ValidateXbrlCalcs import roundValue
from arelle import XbrlConst, XmlUtil
import urllib.request
from urllib.error import HTTPError, URLError

TRACEGREMLINFILE = None
TRACEGREMLINFILE = r"c:\temp\rexstertrace.log"  # uncomment to trace SQL on connection (very big file!!!)

def insertIntoDB(modelXbrl, 
                 user=None, password=None, host=None, port=None, database=None,
                 rssItem=None):
    db = None
    try:
        xsgdb = XbrlSemanticGraphDatabaseConnection(modelXbrl, user, password, host, port, database)
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
        except HTTPError:
            return True # success, this is really a postgres socket, wants user name
        except URLError:
            return False # something is there but not postgres
        except socket.timeout:
            t = t + 2  # relax - try again with longer timeout
    return False
    
XBRLDBGRAPHS = {
                "accessions",    # filings (graph of documents)
                "documents",    # graph of namespace->names->types/elts, datapoints
                "data_dictionary",
                "types", 
                "instances"
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

class XPDBException(Exception):
    def __init__(self, code, message, **kwargs ):
        self.code = code
        self.message = message
        self.kwargs = kwargs
        self.args = ( self.__repr__(), )
    def __repr__(self):
        return _('[{0}] exception: {1}').format(self.code, self.message % self.kwargs)
            


class XbrlSemanticGraphDatabaseConnection():
    def __init__(self, modelXbrl, user, password, host, port, database):
        self.modelXbrl = modelXbrl
        self.disclosureSystem = modelXbrl.modelManager.disclosureSystem
        #self.conn = RexProConnection(host, int(port or '8182'), (database or 'emptygraph'),
        #                             user=user, password=password)
        connectionUrl = "http://{0}:{1}".format(host, port or '8182')
        self.url = connectionUrl + '/graphs/' + database
        # Create an OpenerDirector with support for Basic HTTP Authentication...
        auth_handler = urllib.request.HTTPBasicAuthHandler()
        auth_handler.add_password(realm='rexster',
                                  uri=connectionUrl,
                                  user=user,
                                  passwd=password)
        self.conn = urllib.request.build_opener(auth_handler)
        self.timeout = 20
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
        foundGraphs = self.load()
        # if no tables, initialize database
        if XBRLDBGRAPHS - foundGraphs:  # some are missing
            self.create()
            missingGraphs = XBRLDBGRAPHS - self.load()
            if missingGraphs:
                raise XPDBException("xsgDB:MissingGraphs",
                                    _("The following graphs are missing: %(missingGraphNames)s"),
                                    missingGraphNames=', '.join(t for t in sorted(missingGraphs))) 
            
    def execute(self, script, params=None, commit=False, close=True, fetch=True):
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
        return results
    
    def commit(self):
        pass # TBD  g.commit(), g.rollback() may be not working at least on tinkergraph
    
    def create(self):
        self.showStatus("Create graph nodes")
        results = self.execute("""
            g.clear()
            root = g.addVertex(['class':'semantic_root'])
            new_vertices.each{g.addEdge(root, g.addVertex(['class':it]), "model")}
            [root.outE.inV] << [root]
            """, 
            params={"new_vertices":list(XBRLDBGRAPHS)})["results"]
        for vList in results:
            for v in vList:
                setattr(self, "root_" + v['class'] + "_id", v['_id'])
            
    def load(self):
        self.showStatus("Load graph")
        results = self.execute("""
            found_vertices = []
            expected_vertices.each{ found_vertices << g.V('class', it) }
            found_vertices
            """, 
            params={"expected_vertices":list(XBRLDBGRAPHS)})["results"]
        for vList in results:
            for v in vList:
                setattr(self, "root_" + v['class'] + "_id", int(v['_id']))
        return set(v['class'] for vList in results for v in vList)
        
    def insertXbrl(self, rssItem):
        try:
            # must also have default dimensions loaded
            from arelle import ValidateXbrlDimensions
            ValidateXbrlDimensions.loadDimensionDefaults(self.modelXbrl)
            
            startedAt = time.time()
            # self.load()  this done in the verify step
            self.insertAccession(rssItem)
            self.insertDocuments()
            self.insertDataDictionary() # XML namespaces types aspects
            #self.insertRelationshipTypeSets()
            #self.insertResourceRoleSets()
            #self.insertAspectValues()
            #self.insertResources()
            self.modelXbrl.profileStat(_("XbrlPublicDB: DTS insertion"), time.time() - startedAt)
            startedAt = time.time()
            self.insertDataPoints()
            self.modelXbrl.profileStat(_("XbrlPublicDB: data points insertion"), time.time() - startedAt)
            startedAt = time.time()
            self.insertRelationshipSets()
            self.modelXbrl.profileStat(_("XbrlPublicDB: Relationships insertion"), time.time() - startedAt)
            self.showStatus("Committing entries")
            self.commit()
            self.modelXbrl.profileStat(_("XbrlPublicDB: insertion committed"), time.time() - startedAt)
            self.showStatus("DB insertion completed", clearAfter=5000)
        except Exception as ex:
            self.showStatus("DB insertion failed due to exception", clearAfter=5000)
            raise
        
    def insertAccession(self, rssItem):
        self.showStatus("insert accession")
        # accession graph -> document vertices
        new_accession = {'class':'accession',
                         'is_most_current': True}
        if self.modelXbrl.modelDocument.creationSoftwareComment:
            new_accession['creation_software'] = self.modelXbrl.modelDocument.creationSoftwareComment
        if rssItem is not None:  # sec accession
            # set self.
            accessionType = "SEC_accession"
            new_accession['accepted_timestamp'] = XmlUtil.dateunionValue(rssItem.acceptanceDatetime)
            new_accession['filing_date'] = XmlUtil.dateunionValue(rssItem.filingDate)
            new_accession['entity_id'] = rssItem.cikNumber
            new_accession['entity_name'] = rssItem.companyName
            new_accession['standard_industrial_classification'] = rssItem.assignedSic 
            new_accession['sec_html_url'] = rssItem.htmlUrl 
            new_accession['entry_url'] = rssItem.url
            new_accession['filing_accession_number'] = rssItem.accessionNumber
        else:
            self.accessionId = int(time.time())    # only available if entered from an SEC filing
            datetimeNow = datetime.datetime.now()
            intNow = int(time.time())
            accessionType = "independent_filing"
            new_accession['accepted_timestamp'] = XmlUtil.dateunionValue(datetimeNow)
            new_accession['filing_date'] = XmlUtil.dateunionValue(datetimeNow)
            new_accession['entry_url'] = self.modelXbrl.fileSource.url
            new_accession['filing_accession_number'] = str(intNow)
        for v in self.execute("""
            new_accession = g.addVertex(new_accession)
            g.addEdge(g.v(root_accessions_id), new_accession, 'independent_filing')
            new_accession
            """, 
            params={'root_accessions_id': self.root_accessions_id,
                    'new_accession': new_accession
                   })["results"]:
            self.accession_id = int(v['_id'])
        
    def insertDocuments(self):
        # accession->documents
        # 
        self.showStatus("insert documents")
        results = self.execute("""
            dts = g.addVertex(dts)
            g.addEdge(g.v(root_accession_id), dts, "dts")
            entry_doc = g.addVertex(entry_document)
            ref_docs = []
            g.addEdge(dts, entry_doc, "dts")
            g.addEdge(g.v(root_documents_id), entry_doc, "filed_document")
            g.addEdge(g.v(root_accession_id), entry_doc, "entry_document")
            referenced_documents.each{ref_docs << g.addVertex(it)}
            ref_docs.each{g.addEdge(entry_doc, it, "referenced_document")}
            results = ref_docs
            results << entry_doc
            results << dts
            results
            """, 
            params={'root_accession_id': self.accession_id,
                    'root_documents_id': self.root_documents_id,
                    'dts': {
                        'class': 'dts'},
                    'entry_document': {
                        'class': 'document',
                        'url': self.modelXbrl.modelDocument.uri,
                        'document_type': self.modelXbrl.modelDocument.gettype(),
                        },
                    'referenced_documents': [{
                        'class': 'document',
                        'url': modelDocument.uri,
                        'document_type': modelDocument.gettype()} 
                         for modelDocument in self.modelXbrl.urlDocs.values()
                         if modelDocument is not self.modelXbrl.modelDocument]
                    })["results"]
        self.document_ids = {}
        for v in results:
            if v['class'] == 'dts':
                self.dts_id = int(v['_id'])
            elif v['class'] == 'document':
                self.document_ids[v['url']] = int(v['_id'])
        
    def insertDataDictionary(self):
        # separate graph
        # document-> dataTypeSet -> dataType
        self.showStatus("insert DataDictionary")
        
        # do all schema dataTypeSet vertices
            
        self.type_id = {}
        self.aspect_id = {}
        self.roleType_id = {}
        self.arcroleType_id = {}
        for modelDocument in self.modelXbrl.urlDocs.values():
            if modelDocument.type == Type.SCHEMA:
                modelTypes = [modelType
                              for modelType in self.modelXbrl.qnameTypes.values()
                              if modelType.modelDocument is modelDocument]
                modelConcepts = [modelConcept
                                 for modelConcept in self.modelXbrl.qnameConcepts.values()
                                 if modelConcept.modelDocument is modelDocument]
                roleTypes = [modelRoleType
                             for modelRoleTypes in self.modelXbrl.roleTypes.values()
                             for modelRoleType in modelRoleTypes]
                arcroleTypes = [modelRoleType
                             for modelRoleTypes in self.modelXbrl.arcroleTypes.values()
                             for modelRoleType in modelRoleTypes]
                results = self.execute("""
                    results = []
                    docV = g.v(document_id)
                    dictV = g.addVertex(dict)
                    g.addEdge(docV, dictV, "data_dictionary")
                    types.each{results << g.addEdge(dictV, g.addVertex(it), "data_type")}
                    aspects.each{results << g.addEdge(dictV, g.addVertex(it), "aspect")}
                    roletypes.each{results << g.addEdge(dictV, g.addVertex(it), "role_type")}
                    arcroletypes.each{results << g.addEdge(dictV, g.addVertex(it), "arcrole_type")}
                    results << dictV
                    """, 
                    params={'document_id': self.document_ids[modelDocument.uri],
                    'dict': {
                        'class': 'data_dictionary',
                        'namespace': modelDocument.targetNamespace},
                    'types': [{
                        'class': 'data_type',
                        'name': modelType.name
                          } for modelType in modelTypes],
                    'aspects': [{
                        'class': 'aspect',
                        'name': modelConcept.name
                          } for modelConcept in modelConcepts],
                    'roletypes': [{
                        'class': 'role_type',
                        'uri': modelRoleType.roleURI,
                        'definition': modelRoleType.definition or ''
                          } for modelRoleType in roleTypes],
                    'arcroletypes': [{
                        'class': 'arcrole_type',
                        'uri': modelRoleType.arcroleURI,
                        'definition': modelRoleType.definition or ''
                          } for modelRoleType in arcroleTypes],
                    })["results"]
                iT = iC = iRT = iAT = 0
                for e in results: # results here are edges, and vertices
                    if e['_type'] == 'edge':
                        if e['_label'] == 'data_type':
                            self.type_id[modelTypes[iT].qname] = int(e['_inV'])
                            iT += 1
                        elif e['_label'] == 'aspect':
                            self.aspect_id[modelConcepts[iC].qname] = int(e['_inV'])
                            iC += 1
                        elif e['_label'] == 'role_type':
                            self.roleType_id[roleTypes[iRT].roleURI] = int(e['_inV'])
                            iRT += 1
                        elif e['_label'] == 'arcrole_type':
                            self.arcroleType_id[arcroleTypes[iAT].arcroleURI] = int(e['_inV'])
                            iAT += 1
                
        typeDerivationEdges = []
        for modelType in self.modelXbrl.qnameTypes.values():
            qnamesDerivedFrom = modelType.qnameDerivedFrom
            if not isinstance(qnamesDerivedFrom, (list,tuple)): # list if a union
                qnamesDerivedFrom = (qnamesDerivedFrom,)
            for qnameDerivedFrom in qnamesDerivedFrom:
                if modelType.qname in self.type_id and qnameDerivedFrom in self.type_id:
                    typeDerivationEdges.append({
                            'from_id': self.type_id[modelType.qname],
                            'to_id': self.type_id[qnameDerivedFrom],
                            'rel': "derived_from"})
        self.execute("""
            e.each{g.addEdge(g.v(it.from_id), g.v(it.to_id), it.rel)}
            """, 
            params={'e': typeDerivationEdges})
        aspectEdges = []
        for modelConcept in self.modelXbrl.qnameConcepts.values():
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
        self.execute("""
        e.each{g.addEdge(g.v(it.from_id), g.v(it.to_id), it.rel)}
        """, 
        params={'e': aspectEdges})
        
    def insertResources(self):
        self.showStatus("insert resources")
        table = self.getTable('resource', 'resource_id', 
                              ('role_uri_id', 'qname_id', 'document_id', 'document_line_number', 'document_column_number'), 
                              ('role_uri_id', 'qname_id', 'document_id', 'document_line_number', 'document_column_number'), 
                              tuple((self.uriId[resource.role],
                                     self.qnameId[resource.qname],
                                     self.documentIds[resource.modelDocument.uri],
                                     resource.sourceline,
                                     0)
                                    for arcrole in (XbrlConst.conceptLabel, XbrlConst.conceptReference)
                                    for rel in self.modelXbrl.relationshipSet(arcrole).modelRelationships
                                    for resource in (rel.fromModelObject, rel.toModelObject)
                                    if isinstance(resource, ModelResource)))
        self.resourceId = dict(((roleId, qnId, docId, line, offset), id)
                               for id, roleId, qnId, docId, line, offset in table)
    
        
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
        self.conceptAspectId = []
        if self.modelXbrl.modelDocument.type in (Type.INSTANCE, Type.INLINEXBRL):
            instanceDocument = self.modelXbrl.modelDocument
            dataPoints = []
            dataPointObjectIndices = []
            dataPointVertexIds = []
            entityIdentifiers = [] # index by (scheme, identifier)
            entityIdentifierVertexIds = []
            periods = []  # index by (instant,) or (start,end) dates
            periodVertexIds = []
            dimensions = [] # index by hash of dimension
            dimensionVertexIds = []
            units = []  # index by measures (qnames set) 
            unitVertexIds = []
            for fact in self.modelXbrl.factsInInstance:
                dataPointObjectIndices.append(fact.objectIndex)
                datapoint = {'class': 'data_point',
                             'name': str(fact.qname)}
                if fact.id is not None:
                    datapoint['id'] = fact.id
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
                        key = (dimVal.dimensionQname, dimVal.isExplicit,
                               dimVal.memberQname if dimVal.isExplicit else dimVal.typedMember.innerText)
                        if key not in dimensions:
                            dimensions.append(key)
                    if fact.isNumeric:
                        datapoint['effective_value'] = str(fact.effectiveValue)
                        u = str(fact.unit.measures)  # string for now
                        if u not in units:
                            units.append(u)
                        datapoint['unit']= fact.unitID
                    datapoint['value'] = str(fact.value),
                    if fact.isNumeric and fact.precision:
                        datapoint['precision'] = fact.precision
                    if fact.isNumeric and fact.decimals:
                        datapoint['decimals'] = fact.decimals
                    if fact.id:
                        datapoint['id'] = fact.id
                    if fact.precision:
                        datapoint['presision'] = fact.precision
                    if fact.decimals:
                        datapoint['decimals'] = fact.decimals
                dataPoints.append(datapoint)
            results = self.execute("""
                results = []
                docV = g.v(document_id)
                datapointsV = g.addVertex(datapoints_set)
                g.addEdge(docV, datapointsV, "data_points")
                datapoints.each{results << g.addEdge(datapointsV, g.addVertex(it), "data_point")}
                results << datapointsV
                """, 
                params={'document_id': self.document_ids[instanceDocument.uri],
                        'datapoints_set': {
                            'class': 'datapoints_set'},
                        'datapoints': dataPoints}
                )["results"]
            for e in results: # returns edges and vertices
                if e['_type'] == 'edge' and e['_label'] == 'data_point':
                    dataPointVertexIds.append(int(e['_inV']))
                    
            for e in self.execute("""
                results = []
                aspectV = g.v(aspect_id)
                entityIdentifiers.each{results << g.addEdge(g.addVertex(it), aspectV, 'entity_identifier_aspects')}
                results
                """, 
                params={'aspect_id': self.aspect_id[XbrlConst.qnXbrliIdentifier],
                        'entityIdentifiers': [{'scheme': e[0], 'identifier': e[1]} 
                                              for e in entityIdentifiers]}
                )["results"]:
                if e['_type'] == 'edge':
                    entityIdentifierVertexIds.append(int(e['_outV']))
                    
            p = []
            for period in periods:
                if period == 'forever':
                    p.append({'forever': 'forever'})
                elif len(period) == 1:
                    p.append({'instant': period[0]})
                else:
                    p.append({'start': period[0], 'end': period[1]})
            for e in self.execute("""
                results = []
                aspectV = g.v(aspect_id)
                periods.each{results << g.addEdge(g.addVertex(it), aspectV, 'period_aspects')}
                results
                """, 
                params={'aspect_id': self.aspect_id[XbrlConst.qnXbrliPeriod],
                        'periods': p}
                )["results"]:
                if e['_type'] == 'edge':
                    periodVertexIds.append(int(e['_outV']))
                    
            for e in self.execute("""
                results = []
                aspectV = g.v(aspect_id)
                units.each{results << g.addEdge(g.addVertex(it), aspectV, 'unit_aspects')}
                results
                """, 
                params={'aspect_id': self.aspect_id[XbrlConst.qnXbrliUnit],
                        'units': [{'measures': u} for u in units]}
                )["results"]:
                if e['_type'] == 'edge':
                    unitVertexIds.append(int(e['_outV']))
                    
            if dimensions:
                    
                dims = []
                for dimQn, isExplicit, value in dimensions:
                    if isExplicit:
                        dims.append({'name':dimQn.localName + '-' + value.localName})
                    else:
                        dims.append({'name':dimQn.localName + '-' + str(len(dims)+1),
                                     'typed_value': value})
                
                for e in self.execute("""
                    results = []
                    dimsV = g.addVertex(dim_aspect)
                    dims.each{results << g.addEdge(dimsV, g.addVertex(it), 'dimension_aspect')}
                    results
                    """, 
                    params={'dim_aspect': {'name': 'dimensions'},
                            'dims': dims}
                    )["results"]:
                    if e['_type'] == 'edge':
                        dimensionVertexIds.append(int(e['_outV']))

                # connect dimensions to dimension and member concepts   
                self.execute("""
                    dims.each{g.addEdge(g.v(it.aspect_id), g.v(it.dimension_id), 'dimension')}
                    mems.each{g.addEdge(g.v(it.aspect_id), g.v(it.member_id), 'member')}
                    []
                    """, 
                    params={'dims': [{
                                'aspect_id': aspect_id,
                                'dimension_id': self.aspect_id[dimQn]}
                                for i, aspect_id in enumerate(dimensionVertexIds) 
                                for dimQn,isExplicit,memQn in dimensions[i:i+1]],
                            'mems': [{
                                'aspect_id': aspect_id,
                                'member_id': self.aspect_id[memQn]}
                                for i, aspect_id in enumerate(dimensionVertexIds) 
                                for dimQn,isExplicit,memQn in dimensions[i:i+1]
                                if isExplicit]}
                    )["results"]    
                      
        # add aspect relationships
        edges = []
        for i, factObjectIndex in enumerate(dataPointObjectIndices):
            fact =  self.modelXbrl.modelObjects[factObjectIndex]
            dataPoint_id = dataPointVertexIds[i]
            # fact concept aspect
            edges.append({
                'from_id': dataPoint_id,
                'to_id': self.aspect_id[fact.qname],
                'rel': "fact_concept"})
            context = fact.context
            if context is not None:
                # entityIdentifier aspect
                edges.append({
                    'from_id': dataPoint_id,
                    'to_id': entityIdentifierVertexIds[entityIdentifiers.index(context.entityIdentifier)],
                    'rel': "fact_entityIdentifier"})
                # period aspect
                edges.append({
                    'from_id': dataPoint_id,
                    'to_id': periodVertexIds[periods.index(self.periodAspectValue(context))],
                    'rel': "fact_period"})
                # explicit dimension aspects
                '''
                for dimVal in context.qnameDims.items():
                    key = (dimVal.dimensionQname, dimVal.memberQname)
                    if key not in dimensions:
                        dimensions.append(key)
                    edges.append({
                        'from_id': dataPoint_id,
                        'to_id': dimensionVertexIds[dimensions.index(key)],
                        'rel': "fact_period"})
                '''
            if fact.isNumeric and fact.unit is not None:
                # unit aspect
                u = str(fact.unit.measures)  # string for now
                edges.append({
                    'from_id': dataPoint_id,
                    'to_id': unitVertexIds[units.index(u)],
                    'rel': "fact_unit"})

        results = self.execute("""
            e.each{g.addEdge(g.v(it.from_id), g.v(it.to_id), it.rel)}
            """, 
            params={'e': edges})["results"]
        
    def insertRelationshipSets(self):
        self.showStatus("insert relationship sets")
        relationshipSets = [(arcrole, ELR, linkqname, arcqname)
                            for arcrole, ELR, linkqname, arcqname in self.modelXbrl.baseSets.keys()
                            if ELR and linkqname and arcqname and not arcrole.startswith("XBRL-")]
        relationshipSetIDs = []
        results = self.execute("""
            results = []
            dtsV = g.v(dts_id)
            relSetsV = g.addVertex(relSets)
            g.addEdge(dtsV, relSetsV, "relationship_sets")
            relSet.each{results << g.addEdge(relSetsV, g.addVertex(it), "relationship_set")}
            results << relSetsV
            """, 
            params={
                'dts_id': self.dts_id,
                'relSets': {
                    'class': 'relationship_sets'},
                'relSet': [{
                    'class': 'relationship_set',
                    'arcrole': arcrole,
                    'linkrole': linkrole,
                    'linkname': str(linkqname),
                    'arcname': str(arcqname)
                    } for arcrole, linkrole, linkqname, arcqname in relationshipSets]
            })["results"]
        for e in results: # results here are edges, and vertices
            if e['_type'] == 'edge':
                if e['_label'] == 'relationship_set':
                    relationshipSetIDs.append(int(e['_inV']))
        
        # do tree walk to build relationships with depth annotated, no targetRole navigation
        relV = [] # parentID, seq, order
        vIDs = [] # in same order as relV
        relE = [] # fromV, toV, label
        
        def walkTree(rels, seq, depth, relationshipSet, visited, parentRelID, doVertices):
            for rel in rels:
                if rel not in visited:
                    visited.add(rel)
                    
                    if isinstance(rel.fromModelObject, ModelConcept):
                        sourceId = self.aspect_id[rel.fromModelObject.qname]
                    else:
                        sourceId = None # tbd
                    if isinstance(rel.toModelObject, ModelConcept):
                        targetId = self.aspect_id[rel.toModelObject.qname]
                    else:
                        targetId = None # tbd
                    if sourceId is not None and targetId is not None:
                        if doVertices:
                            relV.append({'seq':seq,'depth':depth})
                            thisRelId = 0
                        else:
                            thisRelId = vIDs[seq-1]
                            relE.append({'from_id': parentRelID, 
                                         'to_id': thisRelId,
                                         'label': 'root' if depth == 1 else 'child'})
                            relE.append({'from_id': thisRelId, 
                                         'to_id': sourceId,
                                         'label': 'source'})
                            relE.append({'from_id': thisRelId, 
                                         'to_id': targetId,
                                         'label': 'target'})
                        seq += 1
                        seq = walkTree(relationshipSet.fromModelObject(rel.toModelObject), seq, depth+1, relationshipSet, visited, thisRelId, doVertices)
                    visited.remove(rel)
            return seq
        
        for doVertices in range(1,-1,-1):  # pass 0 = vertices, pass 1 = edges
            for i, relationshipSetKey in enumerate(relationshipSets):
                arcrole, ELR, linkqname, arcqname = relationshipSetKey
                relationshipSetId = relationshipSetIDs[i]
                relationshipSet = self.modelXbrl.relationshipSet(arcrole, ELR, linkqname, arcqname)
                seq = 1               
                for rootConcept in relationshipSet.rootConcepts:
                    seq = walkTree(relationshipSet.fromModelObject(rootConcept), seq, 1, relationshipSet, set(), relationshipSetId, doVertices)
            if doVertices:
                for v in self.execute("""
                    results = []
                    relV.each{results << g.addVertex(it)}
                    results
                    """, 
                    params={'relV': relV}
                    )["results"]:
                    vIDs.append(int(v['_id']))
            else:
                self.execute("""
                    relE.each{g.addEdge(g.v(it.from_id), g.v(it.to_id), it.label)}
                    """, 
                    params={'relE': relE}
                    )["results"]

