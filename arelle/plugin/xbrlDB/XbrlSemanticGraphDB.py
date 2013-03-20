'''
XbrlSemanticGraphDB.py implements a graph database interface for Arelle, based
on a concrete realization of the Abstract Model PWD 2.0 layer.  This is a semantic 
representation of XBRL information. 

This module provides the execution context for saving a dts and instances in 
XBRL Rexter-interfaced graph.  It may be loaded by Arelle's RSS feed, or by individual
DTS and instances opened by interactive or command line/web service mode.

(c) Copyright 2013 Mark V Systems Limited, California US, All rights reserved.  
Mark V copyright applies to this software, which is licensed according to the terms of Arelle(r).


'''

import os, io, re, time, json, socket
from math import isnan, isinf
from arelle.ModelDtsObject import ModelConcept, ModelResource
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
        self.timeout = 10
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
            missingGraphs = XBRLDBGRAPHS - self.foundGraphs()
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
    
    def create(self):
        self.showStatus("Create graph nodes")
        for v in self.execute("""
            g.clear()
            root = g.addVertex(['name':'semantic_root'])
            new_vertices.each{g.addEdge(root, g.addVertex(['name':it]), "model")}
            [root] + [root.outE.inV]
            """, 
            params={"new_vertices":list(XBRLDBGRAPHS)})["results"]:
            setattr(self, "root_" + v[0]['name'] + "_id", v[0]['_id'])
            
    def load(self):
        self.showStatus("Load graph")
        found_vertices = self.execute("""
            def found_vertices = []
            expected_vertices.each{ found_vertices << g.V('name', it) }
            found_vertices
            """, 
            params={"expected_vertices":list(XBRLDBGRAPHS)})["results"]
        for v in found_vertices:
            setattr(self, "root_" + v[0]['name'] + "_id", int(v[0]['_id']))
        return set(v[0]['name'] for v in found_vertices)
        
    def columnTypeFunctions(self, table):
        if table not in self.tableColTypes:
            colTypes = self.execute("SELECT c.column_name, c.data_type "
                                    "FROM information_schema.columns c "
                                    "WHERE c.table_name = '%s' "
                                    "ORDER BY c.ordinal_position;" % table)
            self.tableColTypes[table] = dict((name, 
                                              # (type cast, conversion function)
                                              ('::' + typename if typename in # takes first word of full type
                                                    {"integer", "smallint", "int", "bigint",
                                                     "real", "numeric",
                                                     "int2", "int4", "int8", "float4", "float8",
                                                     "boolean", "date", "timestamp"}
                                               else "::double precision" if fulltype.startswith("double precision") 
                                               else '',
                                              int if typename in ("integer", "smallint", "int", "bigint") else
                                              float if typename in ("double precision", "real", "numeric") else
                                              pyBoolFromDbBool if typename == "boolean" else
                                              datetime if typename in ("date","timestamp") else  # ModelValue.datetime !!! not python class
                                              str))
                                             for name, fulltype in colTypes
                                             for typename in (fulltype.partition(' ')[0],))
        return self.tableColTypes[table]
    
    def getTable(self, table, idCol, newCols, matchCols, data, commit=False, comparisonOperator='='):
        """
        # note: comparison by = will never match NULL fields
        # use 'IS NOT DISTINCT FROM' to match nulls, but this is not indexed and verrrrry slooooow
        if not data or not newCols or not matchCols:
            # nothing can be done, just return
            return () # place breakpoint here to debug
        returningCols = []
        if idCol: # idCol is the first returned column if present
            returningCols.append(idCol)
        for matchCol in matchCols:
            returningCols.append(matchCol)
        colTypeFunctions = self.columnTypeFunctions(table)
        try:
            colTypeCast = tuple(colTypeFunctions[colName][0] for colName in newCols)
            colTypeFunction = tuple(colTypeFunctions[colName][1] for colName in returningCols)
        except KeyError as err:
            raise XPDBException("xpDB:MissingColumnDefinition",
                                _("Table %(table)s column definition missing: %(missingColumnName)s"),
                                table=table, missingColumnName=str(err)) 
        rowValues = []
        for row in data:
            colValues = []
            for col in row:
                if isinstance(col, bool):
                    colValues.append('TRUE' if col else 'FALSE')
                elif isinstance(col, (int,float)):
                    colValues.append(str(col))
                elif col is None:
                    colValues.append('NULL')
                else:
                    colValues.append("'" + str(col).replace("'","''").replace('%', '%%') + "'")
            if not rowValues:  # first row
                for i, cast in enumerate(colTypeCast):
                    if cast:
                        colValues[i] = colValues[i] + cast
            rowValues.append("(" + ", ".join(colValues) + ")")
        values = ", \n".join(rowValues)
        # insert new rows, return id and cols of new and existing rows
        # use IS NOT DISTINCT FROM instead of = to compare NULL usefully
        sql = '''
WITH row_values (%(newCols)s) AS (
  VALUES %(values)s
  ), insertions AS (
  INSERT INTO %(table)s (%(newCols)s)
  SELECT %(newCols)s
  FROM row_values v
  WHERE NOT EXISTS (SELECT 1 
                    FROM %(table)s x 
                    WHERE %(match)s)
  RETURNING %(returningCols)s
)
(  SELECT %(x_returningCols)s
   FROM %(table)s x JOIN row_values v ON (%(match)s)
) UNION ( 
   SELECT %(returningCols)s
   FROM insertions
);''' %     {"table": table,
             "idCol": idCol,
             "newCols": ', '.join(newCols),
             "returningCols": ', '.join(returningCols),
             "x_returningCols": ', '.join('x.{0}'.format(c) for c in returningCols),
             "match": ' AND '.join('x.{0} {1} v.{0}'.format(col, comparisonOperator) 
                                for col in matchCols),
             "values": values
             }
        if TRACEFILE:
            with io.open(TRACESQLFILE, "a", encoding='utf-8') as fh:
                fh.write("\n\n>>> accession {0} table {1} sql length {2} row count {3}\n"
                         .format(self.accessionId, table, len(sql), len(data)))
                fh.write(sql)
        tableRows = self.execute(sql,commit=commit, close=False)
        return tuple(tuple(None if colValue == "NULL" or colValue is None else
                           colTypeFunction[i](colValue)  # convert to int, datetime, etc
                           for i, colValue in enumerate(row))
                     for row in tableRows)
        """
        
    def insertXbrl(self, rssItem):
        try:
            # must also have default dimensions loaded
            from arelle import ValidateXbrlDimensions
            ValidateXbrlDimensions.loadDimensionDefaults(self.modelXbrl)
            
            startedAt = time.time()
            # self.load()  this done in the verify step
            self.insertAccession(rssItem)
            self.insertDocuments()
            self.insertUris()
            self.insertQnames()
            self.insertNamespaces()
            self.insertCustomArcroles()
            self.insertCustomRoles()
            self.insertElements()
            self.insertResources()
            self.insertNetworks()
            self.modelXbrl.profileStat(_("XbrlPublicDB: DTS insertion"), time.time() - startedAt)
            startedAt = time.time()
            self.insertFacts()
            self.modelXbrl.profileStat(_("XbrlPublicDB: instance insertion"), time.time() - startedAt)
            startedAt = time.time()
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
        new_accession = {'is_most_current': True}
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
            g.addEdge(g.v(root_accession_id), new_accession, 'independent_filing')
            new_accession
            """, 
            params={'root_accession_id': self.root_accession_id,
                    'new_accession': new_accession
                   })["results"]:
            self.accession_id = int(v['_id'])
        
    def insertUris(self):
        uris = (_DICT_SET(self.modelXbrl.namespaceDocs.keys()) |
                _DICT_SET(self.modelXbrl.arcroleTypes.keys()) |
                _DICT_SET(XbrlConst.standardArcroleCyclesAllowed.keys()) |
                _DICT_SET(self.modelXbrl.roleTypes.keys()) |
                XbrlConst.standardRoles)
        self.showStatus("insert uris")
        table = self.getTable('uri', 'uri_id', 
                              ('uri',), 
                              ('uri',), 
                              tuple((uri,) 
                                    for uri in uris))
        self.uriId = dict((uri, id)
                          for id, uri in table)
                     
    def insertQnames(self):
        qnames = (_DICT_SET(self.modelXbrl.qnameConcepts.keys()) |
                  _DICT_SET(self.modelXbrl.qnameAttributes.keys()) |
                  _DICT_SET(self.modelXbrl.qnameTypes.keys()) |
                  set(measure
                      for unit in self.modelXbrl.units.values()
                      for measures in unit.measures
                      for measure in measures))
        self.showStatus("insert qnames")
        table = self.getTable('qname', 'qname_id', 
                              ('namespace', 'local_name'), 
                              ('namespace', 'local_name'), 
                              tuple((qn.namespaceURI, qn.localName) 
                                    for qn in qnames))
        self.qnameId = dict((qname(ns, ln), id)
                            for id, ns, ln in table)
                     
    def insertNamespaces(self):
        # separate graph
        # document-> targetNamespace
        # document-> roleDefs
        self.showStatus("insert namespaces")
        table = self.getTable('namespace', 'namespace_id', 
                              ('uri', 'is_base', 'taxonomy_version_id'), 
                              ('uri',), 
                              tuple((uri, True, 0) 
                                    for uri in self.disclosureSystem.baseTaxonomyNamespaces))
        self.namespaceId = dict((uri, id)
                                for id, uri in table)
        
    def insertDocuments(self):
        # accession->documents
        # 
        self.showStatus("insert documents")
        for v in self.execute("""
            entry_doc = g.addVertex(entry_document)
            docs = [entrydoc]
            g.addEdge(g.v(root_document_id), entry_doc), 
            referenced_documents.each{g.addEdge(entry_doc, docs << g.addVertex(it), "independent_filing")}
            docs
            """, 
            params={'root_accession_id': self.root_accessions_id,
                    'root_document_id': self.root_documents_id,
                    'entry_document': {
                        'url': self.modelXbrl.modelDocument.url,
                        'document_type': self.modelXbrl.modelDocument.getType(),
                        },
                    'referenced_documents': [{
                        'url': modelDocument.url,
                        'document_type': modelDocument.getType()} 
                         for modelDocument in self.modelXbrl.urlDocs.values()
                         if modelDocument is not self.modelXbrl.modelDocument]
                    })["results"]:
            pass

        
        
        table = self.getTable('document', 'document_id', 
                              ('document_uri',), 
                              ('document_uri',), 
                              tuple((docUri,) 
                                    for docUri in self.modelXbrl.urlDocs.keys()))
        self.documentIds = dict((uri, id)
                                for id, uri in table)
        
    def insertCustomArcroles(self):
        # vertices from accession and from documents
        
        self.showStatus("insert arcrole types")
        arcroleTypesByIds = dict(((self.documentIds[arcroleType.modelDocument.uri],
                                   self.uriId[arcroleType.arcroleURI]), # key on docId, uriId
                                  arcroleType) # value is roleType object
                                 for arcroleTypes in self.modelXbrl.arcroleTypes.values()
                                 for arcroleType in arcroleTypes)
        table = self.getTable('custom_arcrole_type', 'custom_arcrole_type_id', 
                              ('document_id', 'uri_id', 'definition', 'cycles_allowed'), 
                              ('document_id', 'uri_id'), 
                              tuple((arcroleTypeIDs[0], # doc Id
                                     arcroleTypeIDs[1], # uri Id
                                     arcroleType.definition, 
                                     {'any':1, 'undirected':2, 'none':3}[arcroleType.cyclesAllowed])
                                    for arcroleTypeIDs, arcroleType in arcroleTypesByIds.items()))
        table = self.getTable('custom_arcrole_used_on', 'custom_arcrole_used_on_id', 
                              ('custom_arcrole_type_id', 'qname_id'), 
                              ('custom_arcrole_type_id', 'qname_id'), 
                              tuple((id, self.qnameId[usedOn])
                                    for id, docid, uriid in table
                                    for usedOn in arcroleTypesByIds[(docid,uriid)].usedOns))
        
    def insertCustomRoles(self):
        # vertices from accession and from documents

        self.showStatus("insert role types")
        roleTypesByIds = dict(((self.documentIds[roleType.modelDocument.uri],
                                self.uriId[roleType.roleURI]), # key on docId, uriId
                               roleType) # value is roleType object
                              for roleTypes in self.modelXbrl.roleTypes.values()
                              for roleType in roleTypes)
        table = self.getTable('custom_role_type', 'custom_role_type_id', 
                              ('document_id', 'uri_id', 'definition'), 
                              ('document_id', 'uri_id'), 
                              tuple((roleTypeIDs[0], # doc Id
                                     roleTypeIDs[1], # uri Id
                                     roleType.definition) 
                                    for roleTypeIDs, roleType in roleTypesByIds.items()))
        table = self.getTable('custom_role_used_on', 'custom_role_used_on_id', 
                              ('custom_role_type_id', 'qname_id'), 
                              ('custom_role_type_id', 'qname_id'), 
                              tuple((id, self.qnameId[usedOn])
                                    for id, docid, uriid in table
                                    for usedOn in roleTypesByIds[(docid,uriid)].usedOns))
        
    def insertElements(self):
        # all DTS objects: particles, types, elements, attrs
        self.showStatus("insert elements")
        table = self.getTable('element', 'element_id', 
                              ('qname_id', 'datatype_qname_id', 'xbrl_base_datatype_qname_id', 'balance_id',
                               'period_type_id', 'substitution_group_qname_id', 'abstract', 'nillable',
                               'document_id', 'is_numeric', 'is_monetary'), 
                              ('qname_id',), 
                              tuple((self.qnameId[concept.qname],
                                     self.qnameId.get(concept.typeQname), # may be None
                                     self.qnameId.get(concept.baseXbrliTypeQname), # may be None
                                     {'debit':1, 'credit':2, None:None}[concept.balance],
                                     {'instant':1, 'duration':2, 'forever':3, None:0}[concept.periodType],
                                     self.qnameId.get(concept.substitutionGroupQname), # may be None
                                     concept.isAbstract, 
                                     concept.isNillable,
                                     self.documentIds[concept.modelDocument.uri],
                                     concept.isNumeric,
                                     concept.isMonetary)
                                    for concept in self.modelXbrl.qnameConcepts.values()))
        self.elementId = dict((qnameId, id)  # indexed by qnameId, not by qname value
                              for id, qnameId in table)
        
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
    
    def insertNetworks(self):
        self.showStatus("insert networks")
        table = self.getTable('network', 'network_id', 
                              ('accession_id', 'extended_link_qname_id', 'extended_link_role_uri_id', 
                               'arc_qname_id', 'arcrole_uri_id', 'description'), 
                              ('accession_id', 'extended_link_qname_id', 'extended_link_role_uri_id', 
                               'arc_qname_id', 'arcrole_uri_id'), 
                              tuple((self.accessionId,
                                     self.qnameId[linkqname],
                                     self.uriId[ELR],
                                     self.qnameId[arcqname],
                                     self.uriId[arcrole],
                                     None if ELR in XbrlConst.standardRoles else
                                     self.modelXbrl.roleTypes[ELR][0].definition)
                                    for arcrole, ELR, linkqname, arcqname in self.modelXbrl.baseSets.keys()
                                    if ELR and linkqname and arcqname and not arcrole.startswith("XBRL-")))
        self.networkId = dict(((accId, linkQnId, linkRoleId, arcQnId, arcRoleId), id)
                              for id, accId, linkQnId, linkRoleId, arcQnId, arcRoleId in table)
        # do tree walk to build relationships with depth annotated, no targetRole navigation
        dbRels = []
        
        def walkTree(rels, seq, depth, relationshipSet, visited, dbRels, networkId):
            for rel in rels:
                if rel not in visited:
                    visited.add(rel)
                    dbRels.append((rel, seq, depth, networkId))
                    seq += 1
                    seq = walkTree(relationshipSet.fromModelObject(rel.toModelObject), seq, depth+1, relationshipSet, visited, dbRels, networkId)
                    visited.remove(rel)
            return seq
        
        for arcrole, ELR, linkqname, arcqname in self.modelXbrl.baseSets.keys():
            if ELR and linkqname and arcqname and not arcrole.startswith("XBRL-"):
                networkId = self.networkId[(self.accessionId,
                                            self.qnameId[linkqname],
                                            self.uriId[ELR],
                                            self.qnameId[arcqname],
                                            self.uriId[arcrole])]
                relationshipSet = self.modelXbrl.relationshipSet(arcrole, ELR, linkqname, arcqname)
                seq = 1               
                for rootConcept in relationshipSet.rootConcepts:
                    seq = walkTree(relationshipSet.fromModelObject(rootConcept), seq, 1, relationshipSet, set(), dbRels, networkId)

        def conceptId(concept):
            if isinstance(concept, ModelConcept):
                self.elementId.get(self.qnameId.get(concept.qname))
            else:
                return None            
        def resourceId(resource):
            if isinstance(resource, ModelResource):
                return self.resourceId.get((self.uriId[resource.role],
                                            self.qnameId[resource.qname],
                                            self.documentIds[resource.modelDocument.uri],
                                            resource.sourceline, 0))
            else:
                return 0            
        
        table = self.getTable('relationship', 'relationship_id', 
                              ('network_id', 'from_element_id', 'to_element_id', 'reln_order', 
                               'from_resource_id', 'to_resource_id', 'calculation_weight', 
                               'tree_sequence', 'tree_depth', 'preferred_label_role_uri_id'), 
                              ('network_id', 'tree_sequence'), 
                              tuple((networkId,
                                     conceptId(rel.fromModelObject.qname), # may be None
                                     conceptId(rel.toModelObject.qname), # may be None
                                     dbNum(rel.order),
                                     resourceId(rel.fromModelObject.qname), # may be None
                                     resourceId(rel.toModelObject.qname), # may be None
                                     dbNum(rel.weight), # none if no weight
                                     sequence,
                                     depth,
                                     self.qnameId.get(rel.preferredLabel))
                                    for rel, sequence, depth, networkId in dbRels))

    def insertFacts(self):
        # all belong to instance document
        accsId = self.accessionId
        self.showStatus("insert facts")
        # units
        table = self.getTable('unit', 'unit_id', 
                              ('accession_id', 'unit_xml_id'), 
                              ('accession_id', 'unit_xml_id'), 
                              tuple((accsId,
                                     unitId)
                                    for unitId in self.modelXbrl.units.keys()))
        self.unitId = dict(((_accsId, xmlId), id)
                           for id, _accsId, xmlId in table)
        # measures
        table = self.getTable('unit_measure', 'unit_measure_id', 
                              ('unit_id', 'qname_id', 'location_id'), 
                              ('qname_id', 'location_id'), 
                              tuple((self.unitId[(accsId,unit.id)],
                                     self.qnameId[measure],
                                     1 if (not unit.measures[1]) else (i + 1))
                                    for unit in self.modelXbrl.units.values()
                                    for i in range(2)
                                    for measure in unit.measures[i]))
        #table = self.getTable('enumeration_measure_location', 'enumeration_measure_location_id', 
        #                      ('description',), 
        #                      ('description',),
        #                      (('measure',), ('numerator',), ('denominator',)))
        # context
        table = self.getTable('context', 'context_id', 
                              ('accession_id', 'period_start', 'period_end', 'period_instant', 'specifies_dimensions', 'context_xml_id', 'entity_scheme', 'entity_identifier'), 
                              ('accession_id', 'context_xml_id'), 
                              tuple((accsId,
                                     cntx.startDatetime if cntx.isStartEndPeriod else None,
                                     cntx.endDatetime if cntx.isStartEndPeriod else None,
                                     cntx.instantDatetime if cntx.isInstantPeriod else None,
                                     bool(cntx.qnameDims),
                                     cntx.id,
                                     cntx.entityIdentifier[0],
                                     cntx.entityIdentifier[1])
                                    for cntx in self.modelXbrl.contexts.values()))
        self.cntxId = dict(((_accsId, xmlId), id)
                           for id, _accsId, xmlId in table)
        # context_dimension
        values = []
        for cntx in self.modelXbrl.contexts.values():
            for dim in cntx.qnameDims.values():
                values.append((self.cntxId[(accsId,cntx.id)],
                               self.qnameId[dim.dimensionQname],
                               self.qnameId.get(dim.memberQname), # may be None
                               self.qnameId.get(dim.typedMember.qname) if dim.isTyped else None,
                               False, # not default
                               dim.contextElement == "segment",
                               dim.typedMember.innerText if dim.isTyped else None))
            for dimQname, memQname in self.modelXbrl.qnameDimensionDefaults.items():
                if dimQname not in cntx.qnameDims:
                    values.append((self.cntxId[(accsId,cntx.id)],
                                   self.qnameId[dimQname],
                                   self.qnameId[memQname],
                                   None,
                                   True, # is default
                                   True, # ambiguous and irrelevant for the XDT model
                                   None))
        table = self.getTable('context_dimension', 'context_dimension_id', 
                              ('context_id', 'dimension_qname_id', 'member_qname_id', 'typed_qname_id', 'is_default', 'is_segment', 'typed_text_content'), 
                              ('dimension_qname_id',), 
                              values)
        # facts
        table = self.getTable('fact', 'fact_id', 
                              ('accession_id', 'context_id', 'unit_id', 'element_id', 'effective_value', 'fact_value', 
                               'xml_id', 'precision_value', 'decimals_value', 
                               'is_precision_infinity', 'is_decimals_infinity', ), 
                              ('accession_id', 'context_id', 'unit_id', 'element_id', 'fact_value'), 
                              tuple((accsId,
                                     self.cntxId.get((accsId,fact.contextID)),
                                     self.unitId.get((accsId,fact.unitID)),
                                     self.elementId.get(self.qnameId.get(fact.qname)),
                                     roundValue(fact.value, fact.precision, fact.decimals) if fact.isNumeric else None,
                                     fact.value,
                                     fact.id,
                                     fact.xAttributes['precision'].xValue if ('precision' in fact.xAttributes and isinstance(fact.xAttributes['precision'].xValue,int)) else None,
                                     fact.xAttributes['decimals'].xValue if ('decimals' in fact.xAttributes and isinstance(fact.xAttributes['decimals'].xValue,int)) else None,
                                     'precision' in fact.xAttributes and fact.xAttributes['precision'].xValue == 'INF',
                                     'decimals' in fact.xAttributes and fact.xAttributes['decimals'].xValue == 'INF',
                                     )
                                    for fact in self.modelXbrl.facts))
        # hashes
