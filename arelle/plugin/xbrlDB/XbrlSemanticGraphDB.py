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
    HF - don't believe this is either feasible or has a use case in a graph model
2) check existence of (shared) documents and contained elements before adding
3) tuple structure declaration (particles in elements of data dictionary?)
4) tuple structure (instance facts)
5) add footnote resources to relationships (and test with EDInet footnote references)
6) test some filings with text blocks (shred them?)  (30mB - 50mB sized text blocks?)
7) add mappings to, or any missing relationships, of Charlie's financial model

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
        self.timeout = 30
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
        if results['success'] == False:
            raise XPDBException("xsgDB:DatabaseError",
                                _("%(activity)s not successful: %(error)s"),
                                activity=activity, error=results.get('error')) 
        return results
    
    def commit(self):
        pass # TBD  g.commit(), g.rollback() may be not working at least on tinkergraph
    
    def loadGraphRootVertices(self):
        self.showStatus("Load/Create graph root vertices")
        results = self.execute("Load/Create graph root vertices", """
            // check if semantic_root vertex already exists
            rIt = g.V('class', 'semantic_root')  // iterator on semantic_root vertices
            // if none, add it
            r = (rIt.hasNext() ? rIt.next() : g.addVertex(['class':'semantic_root']))
            root_vertices = []
            root_classes.each{
                // check if class "it"'s vertex already exists
                vIt = g.V('class', it)
                // if exists, use that vetex, if not, add it
                v = (vIt.hasNext() ? vIt.next() : g.addVertex(['class':it]) )
                // check if class it's vertex has edge from semantic_root
                vIn = v.in('model')
                // if no edge then add edge
                vIn.hasNext() && vIn.next() == r ?: g.addEdge(r, v, 'model')
                // return vertex (so plug-in can refer to it by its id
                root_vertices << v
            }
            root_vertices
            """, 
            params={"root_classes":list(XBRLDBGRAPHS)})["results"]
        for v in results:
            setattr(self, "root_" + v['class'] + "_id", int(v['_id']))
        return set(v['class'] for v in results)
        
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
            #startedAt = time.time()
            #self.insertValidCombinations()
            #self.modelXbrl.profileStat(_("XbrlPublicDB: Valid Combinations insertion"), time.time() - startedAt)
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
        datetimeNow = datetime.datetime.now()
        datetimeNowStr = XmlUtil.dateunionValue(datetimeNow)
        if rssItem is not None:  # sec accession
            # set self.
            accessionType = "SEC_accession"
            # for an RSS Feed entry from SEC, use rss item's accession information
            new_accession['accepted_timestamp'] = XmlUtil.dateunionValue(rssItem.acceptanceDatetime)
            new_accession['filing_date'] = XmlUtil.dateunionValue(rssItem.filingDate)
            new_accession['entity_id'] = rssItem.cikNumber
            new_accession['entity_name'] = rssItem.companyName
            new_accession['standard_industrial_classification'] = rssItem.assignedSic 
            new_accession['sec_html_url'] = rssItem.htmlUrl 
            new_accession['entry_url'] = rssItem.url
            new_accession['filing_accession_number'] = filing_accession_number = rssItem.accessionNumber
        else:
            # not an RSS Feed item, make up our own accession ID (the time in seconds of epoch)
            self.accessionId = int(time.time())    # only available if entered from an SEC filing
            intNow = int(time.time())
            accessionType = "independent_filing"
            new_accession['accepted_timestamp'] = datetimeNowStr
            new_accession['filing_date'] = datetimeNowStr
            new_accession['entry_url'] = self.modelXbrl.fileSource.url
            new_accession['filing_accession_number'] = filing_accession_number = str(intNow)
        for id in self.execute("Insert accession " + accessionType, """
            r = g.v(root_accessions_id)
            // check if accession already has a vertex
            vIt = g.V('filing_accession_number', new_accession.filing_accession_number)
            // use prior vertex, or if none, create new vertex for it
            accession = (vIt.hasNext() ? vIt.next() : g.addVertex(new_accession) )
            // TBD: modify accession timestamp (last-updated-at, if it already existed)
            // check if vertex has edge to root_accessions vertex
            vIn = accession.in
            // if no edge, add one
            vIn.hasNext() && vIn.next() == r ?: g.addEdge(r, accession, accession_type)
            accession.id
            """, 
            params={'root_accessions_id': self.root_accessions_id,
                    'new_accession': new_accession,
                    'accession_type': accessionType,
                    'datetime_now': datetimeNowStr,
                   })["results"]:
            self.accession_id = int(id)
            
        # relationshipSets are a dts property
        self.relationshipSets = [(arcrole, ELR, linkqname, arcqname)
                                 for arcrole, ELR, linkqname, arcqname in self.modelXbrl.baseSets.keys()
                                 if ELR and linkqname and arcqname and not arcrole.startswith("XBRL-")]
        
    def insertDocuments(self):
        # accession->documents
        # 
        self.showStatus("insert documents")
        documents = []
        for modelDocument in self.modelXbrl.urlDocs.values():
            doc = {'class': 'document',
                   'url': modelDocument.uri,
                   'document_type': modelDocument.gettype(),
                   'is_entry': modelDocument is self.modelXbrl.modelDocument}
            if modelDocument.type == Type.SCHEMA:
                doc['aspect_vertices'] = {}
            documents.append(doc)
        results = self.execute("Insert documents", """
            results = []
            rDoc = g.v(root_documents_id)
            vAccession = g.v(root_accession_id)
            // add dts if it doesn't exist
            vDtsIt = vAccession.out('dts')
            vDts = (vDtsIt.hasNext() ? vDtsIt.next() : g.addVertex(dts) )
            vDtsIn = vDts.in('dts').has('id',vAccession.id)
            vDtsIn.hasNext() ?: g.addEdge(vAccession, vDts, 'dts')

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

            // entry document edge to dts
            documents.findAll{it.is_entry}.each{
                vEntryDoc = urlV[it.url]
                // link entryDoc to dts
                vDocIn = vEntryDoc.in('filed_document')
                vDocIn.hasNext() && vDocIn.next() == rDoc ?: g.addEdge(rDoc, vDoc, 'filed_document')
            }

            // referenced document edge to entry document
            documents.findAll{!it.is_entry}.each{
                vRefDoc = urlV[it.url]
                // link refDoc to vEntryDoc
                vDocIn = vRefDoc.in('referenced_document')
                vDocIn.hasNext() && vDocIn.next() == rDoc ?: g.addEdge(vEntryDoc, vDoc, 'referenced_document')
            }
            [vDts.id, urlV_id, isNew]
            """, 
            params={'root_accession_id': self.accession_id,
                    'root_documents_id': self.root_documents_id,
                    'dts': {
                        'class': 'dts'},
                    'documents': documents
                    })["results"]
        dts_id, doc_id_list, doc_isNew_list = results # unpack list
        self.dts_id = int(dts_id)
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
        return conceptsUsed

    def insertDataDictionary(self):
        # separate graph
        # document-> dataTypeSet -> dataType
        # do all schema dataTypeSet vertices
            
        self.type_id = {}
        self.aspect_id = {}
        self.roleType_id = {}
        self.arcroleType_id = {}
            
        if any((not self.document_isNew[modelDocument.uri])
               for modelDocument in self.modelXbrl.urlDocs.values()):
            conceptsUsed = self.conceptsUsed()
            
        for modelDocument in self.modelXbrl.urlDocs.values():
            self.showStatus("insert DataDictionary " + modelDocument.basename)
        
            # don't re-output existing documents
            if modelDocument.type == Type.SCHEMA:
                modelConcepts = [modelConcept
                                 for modelConcept in self.modelXbrl.qnameConcepts.values()
                                 if modelConcept.modelDocument is modelDocument]
                if self.document_isNew[modelDocument.uri]:
                    # adding document as new
                    modelTypes = [modelType
                                  for modelType in self.modelXbrl.qnameTypes.values()
                                  if modelType.modelDocument is modelDocument]
                    conceptAspects = []
                    for modelConcept in modelConcepts:
                        conceptAspect = {'class': 'aspect',
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
                    results = self.execute("Insert data dictionary types, aspects, roles, and arcroles for " + 
                                           modelDocument.uri, """
                        docV = g.v(document_id)
                        dictV = g.addVertex(dict)
                        // add dictV if it doesn't exist
                        dictIt = dictV.out('data_dictionary')
                        dictV = (dictIt.hasNext() ? dictIt.next() : g.addVertex(dict) )
                        // add edge from docV to dictV if not present
                        vDictIn = dictV.in('data_dictionary').has('id',docV.id)
                        vDictIn.hasNext() ?: g.addEdge(docV, dictV, 'data_dictionary')
                        type_ids = []
                        types.each{
                            typeV = g.addVertex(it)
                            type_ids << typeV.id
                            g.addEdge(docV, typeV, 'data_type')
                        }
                        aspect_ids = []
                        aspect_vertices_map = docV.getProperty('aspect_vertices')
                        aspects.each{
                            aspectV = g.addVertex(it)
                            aspect_ids << aspectV.id
                            g.addEdge(docV, aspectV, 'aspect')
                            aspect_vertices_map[it.name] = aspectV.id
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
                        params={'document_id': self.document_ids[modelDocument.uri],
                        'dict': {
                            'class': 'data_dictionary',
                            'namespace': modelDocument.targetNamespace},
                        'types': [{
                            'class': 'data_type',
                            'name': modelType.name
                              } for modelType in modelTypes],
                        'aspects': conceptAspects,
                        'roletypes': [{
                            'class': 'role_type',
                            'uri': modelRoleType.roleURI,
                            'definition': modelRoleType.definition or ''
                              } for modelRoleType in roleTypes],
                        'arcroletypes': [{
                            'class': 'arcrole_type',
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
                else: # not new, just get aspect (concept) id's 
                    results = self.execute("Access existing data dictionary types, aspects, roles, and arcroles for " + 
                                           modelDocument.uri, """
                        docV = g.v(document_id)
                        aspect_vertices_map = docV.getProperty('aspect_vertices')
                        aspect_ids = []
                        aspects.each{
                            //using out and has to find aspect is very sloooowww
                            //anAspectId = null // in case aspect is not in the database
                            //docV.out('aspect').has('name',it).each{anAspectId = it.id}
                            anAspectId = aspect_vertices_map[it]
                            aspect_ids << anAspectId // might have been multiple
                        }
                        aspect_ids
                        """, 
                        params={'document_id': self.document_ids[modelDocument.uri],
                            'aspects': [modelConcept.name for modelConcept in modelConcepts],
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
        dataPointObjectIndices = []
        if self.modelXbrl.modelDocument.type in (Type.INSTANCE, Type.INLINEXBRL):
            instanceDocument = self.modelXbrl.modelDocument
            dataPoints = []
            entityIdentifiers = [] # index by (scheme, identifier)
            periods = []  # index by (instant,) or (start,end) dates
            dimensions = [] # index by hash of dimension
            units = []  # index by measures (qnames set) 
            for fact in self.modelXbrl.factsInInstance:
                dataPointObjectIndices.append(fact.objectIndex)
                datapoint = {'class': 'data_point',
                             'name': str(fact.qname)}
                if fact.id is not None:
                    datapoint['xml_id'] = fact.id
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
                        if fact.unit is not None:
                            u = str(fact.unit.measures)  # string for now
                            if u not in units:
                                units.append(u)
                            datapoint['unit']= fact.unitID
                        if fact.precision:
                            datapoint['precision'] = fact.precision
                        if fact.decimals:
                            datapoint['decimals'] = fact.decimals
                    datapoint['value'] = str(fact.value),
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
                    g.addEdge(datapointsV, dpV, "data_point")
                }
                [datapointsV.id, datapointV_ids]
                """, 
                params={'document_id': self.document_ids[instanceDocument.uri],
                        'datapoints_set': {
                            'class': 'datapoints_set'},
                        'datapoints': dataPoints}
                )["results"]
            datapointsV_id, datapointVids_list = results
            dataPointVertexIds = [int(id) for id in datapointVids_list]
                    
            results = self.execute("Insert entity identifiers", """
                aspectV = g.v(aspect_id)
                entIdentV_ids = []
                entityIdentifiers.each{
                    entIdentV = g.addVertex(it)
                    entIdentV_ids << entIdentV.id
                    g.addEdge(entIdentV, aspectV, 'entity_identifier_aspects')
                }
                [aspectV.id, entIdentV_ids]
                """, 
                params={'aspect_id': self.aspect_id[XbrlConst.qnXbrliIdentifier],
                        'entityIdentifiers': [{'scheme': e[0], 'identifier': e[1]} 
                                              for e in entityIdentifiers]}
                )["results"]
            entIdentAspectV_id, entIdentV_ids_list = results
            entityIdentifierVertexIds = [int(entIdent_id) for entIdent_id in entIdentV_ids_list]
                    
            p = []
            for period in periods:
                if period == 'forever':
                    p.append({'forever': 'forever'})
                elif len(period) == 1:
                    p.append({'instant': period[0]})
                else:
                    p.append({'start': period[0], 'end': period[1]})
            results = self.execute("Insert periods", """
                aspectV = g.v(aspect_id)
                periodV_ids = []
                periods.each{
                    periodV = g.addVertex(it)
                    periodV_ids << periodV.id
                    g.addEdge(periodV, aspectV, 'period_aspects')
                }
                [aspectV.id, periodV_ids]
                """, 
                params={'aspect_id': self.aspect_id[XbrlConst.qnXbrliPeriod],
                        'periods': p}
                )["results"]
            periodAsepctV_id, periodV_ids_list = results
            periodVertexIds = [int(period_id) for period_id in periodV_ids_list]
                    
            results = self.execute("Insert units", """
                aspectV = g.v(aspect_id)
                unitV_ids = []
                units.each{
                    unitV = g.addVertex(it)
                    unitV_ids << unitV.id
                    g.addEdge(unitV, aspectV, 'unit_aspects')}
                [aspectV.id, unitV_ids]
                """, 
                params={'aspect_id': self.aspect_id[XbrlConst.qnXbrliUnit],
                        'units': [{'measures': u} for u in units]}
                )["results"]
            unitV_id, unitV_ids_list = results
            unitVertexIds = [int(unit_id) for unit_id in unitV_ids_list]
                    
            if dimensions:                    
                dims = []
                for dimQn, isExplicit, value in dimensions:
                    if isExplicit:
                        dims.append({'name':dimQn.localName + '-' + value.localName})
                    else:
                        dims.append({'name':dimQn.localName + '-' + str(len(dims)+1),
                                     'typed_value': value})
                
                results = self.execute("Insert dimension aspects", """
                    dimsV = g.addVertex(dim_aspect)
                    dimV_ids = []
                    dims.each{
                        dimV = g.addVertex(it)
                        dimV_ids << dimV.id
                        g.addEdge(dimsV, dimV, 'dimension_aspect')
                    }
                    [dimsV.id, dimV_ids]
                    """, 
                    params={'dim_aspect': {'name': 'dimensions'},
                            'dims': dims}
                    )["results"]
                dimsV_id, dimV_ids_list = results
                dimensionVertexIds = [int(dim_id) for dim_id in dimV_ids_list]

                # connect dimensions to dimension and member concepts   
                self.execute("Insert dimension member edges", """
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
            else:
                dimensionVertexIds = []

                      
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

        results = self.execute("Insert aspect relationship edges", """
            e.each{g.addEdge(g.v(it.from_id), g.v(it.to_id), it.rel)}
            []
            """, 
            params={'e': edges})["results"]
        
    def insertRelationshipSets(self):
        self.showStatus("insert relationship sets")
        results = self.execute("Insert relationship sets", """
            dtsV = g.v(dts_id)
            relSetsV = g.addVertex(relSets)
            g.addEdge(dtsV, relSetsV, 'relationship_sets')
            relSetV_ids = []
            relSet.each{
                relSetV = g.addVertex(it)
                relSetV_ids << relSetV.id
                g.addEdge(relSetsV, relSetV, 'relationship_set')}
            [relSetsV.id, relSetV_ids]
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
                    } for arcrole, linkrole, linkqname, arcqname in self.relationshipSets]
            })["results"]
        relSetsV_id, relSetV_ids_list = results
        relationshipSetIDs = [int(relSet_id) for relSet_id in relSetV_ids_list]
        
        # do tree walk to build relationships with depth annotated, no targetRole navigation
        relV = [] # parentID, seq, order
        vIDs = [] # in same order as relV
        relE = [] # fromV, toV, label
        resources = set()
        resourceIDs = {} # index by object
        
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
                    elif isinstance(rel.toModelObject, ModelResource):
                        if doVertices:
                            resources.add(rel.toModelObject)
                            targetId = 0 # just can't be None, but doesn't matter on doVertices pass
                        else:
                            targetId = resourceIDs[rel.toModelObject]
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
            for i, relationshipSetKey in enumerate(self.relationshipSets):
                arcrole, ELR, linkqname, arcqname = relationshipSetKey
                relationshipSetId = relationshipSetIDs[i]
                relationshipSet = self.modelXbrl.relationshipSet(arcrole, ELR, linkqname, arcqname)
                seq = 1               
                for rootConcept in relationshipSet.rootConcepts:
                    seq = walkTree(relationshipSet.fromModelObject(rootConcept), seq, 1, relationshipSet, set(), relationshipSetId, doVertices)
            if doVertices:
                for relV_id in self.execute("Insert relationship set resources", """
                    relV_ids = []
                    relV.each{relV_ids << g.addVertex(it).id}
                    relV_ids
                    """, 
                    params={'relV': relV}
                    )["results"]:
                    vIDs.append(int(relV_id))
                    
                if resources:
                    resourceV = []
                    resourceObjs = []
                    for resource in resources:
                        resourceParam = {'class': resource.localName,
                                         'value': resource.innerText}
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
                    
            else:
                self.execute("Insert relationship edges", """
                    relE.each{g.addEdge(g.v(it.from_id), g.v(it.to_id), it.label)}
                    []
                    """, 
                    params={'relE': relE}
                    )["results"]
                
                # TBD: do we want to link resources to the dts (by role, class, or otherwise?)
                    
        resourceIDs.clear() # dereferemce objects
        resources = None

