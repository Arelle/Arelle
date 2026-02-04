'''
See COPYRIGHT.md for copyright information.

Processes TableObject and yields rows of facts

'''
import os
from collections import defaultdict
from arelle.oim.Load import (parseMetadataCellValues, csvCellValue, _isParamRef, _getParamRefName, csvPeriod,
                             openCsvReader,
                             CSV_FACTS_FILE, EMPTY_LIST, EMPTY_DICT, EMPTY_CELL, NONE_CELL, INVALID_REFERENCE_TARGET,
                             IdentifierPattern, RowIdentifierPattern)
from arelle.ModelValue import qname
from .XbrlConcept import XbrlConcept
from .XbrlCube import coreDimensionsByLocalname
from .XbrlDimension import XbrlDimension
from .XbrlReport import XbrlFact, XbrlTableTemplate

# Load CSV Table
columnProperties = {"comment", "decimals", "dimensions", "propertyGroups", "parameterURL", "propertiesFrom"}


def csvTableRowFacts(table, txmyMdl, error, warning, reportUrl): # yields facts by row in table
    prefixNamespaces = table.report._prefixNamespaces
    url = txmyMdl.modelManager.cntlr.webCache.normalizeUrl(table.url, reportUrl)
    if not txmyMdl.fileSource.exists(url):
        if not table.optional:
            error("xbrlce:missingRequiredCSVFile",
                  _("The url %(url)s MUST be an existing file for non-optional table %(table)s."),
                  table=table.name, url=table.url)
        return

    tableTemplate = txmyMdl.namedObjects.get(table.template)
    if tableTemplate is None or not isinstance(tableTemplate, XbrlTableTemplate):
        error("xbrlce:unknownTableTemplate",
              _("The table %(table) template, %(name)s MUST be the identifier of a table template present in the OIM Taxonomy Model."),
              table=table.name, name=table.template)
        return

    tableId = table.name.localName
    # tableIsTransposed = tableTemplate.get("transposed", False)
    tableDecimals = tableTemplate.decimals
    tableDimensions = tableTemplate.dimensions
    parseMetadataCellValues(tableDimensions)
    tableParameters = table.parameters
    rowIdColName = tableTemplate.rowIdColumn
    reportDimensions = tableTemplate.dimensions
    reportDecimals = tableTemplate.decimals
    tableUrl = table.url
    tableParameterColNames = set()
    hasHeaderError = False # set to true blocks handling file beyond header row

    # compile column dependencies
    factDimensions = {} # keys are column, values are dimensions object
    factDecimals = {} # keys are column
    propertyGroups = {}
    propertiesFrom = {}
    dimensionsColumns = set()
    commentColumns = set()
    extensionColumnProperties = defaultdict(dict)
    for colId, colProperties in tableTemplate.columns.items():
        isCommentColumn = colProperties.get("comment") == True
        if isCommentColumn:
            commentColumns.add(colId)
        else:
            factDimensions[colId] = colProperties.get("dimensions")
            factDecimals[colId] = colProperties.get("decimals")
        isFactColumn = "dimensions" in colProperties
        if "propertiesFrom" in colProperties:
            isFactColumn = True
            propertiesFrom[colId] = colProperties["propertiesFrom"]
        if not isFactColumn and not isCommentColumn:
            dimensionsColumns.add(colId) # neither comment nor fact column
        isPropertyGroupColumn = "propertyGroups" in colProperties
        if isPropertyGroupColumn:
            propertyGroups[colId] = colProperties["propertyGroups"]
        for extPropSQName, prop in colProperties.items():
            if extPropSQName not in columnProperties:
                extensionColumnProperties[colId][extPropSQName] = prop
    # check table parameters
    tableParameterReferenceNames = set()
    def checkParamRef(paramValue, factColName=None, dimName=None):
        if _isParamRef(paramValue):
            paramName = _getParamRefName(paramValue)
            tableParameterReferenceNames.add(paramName)
    unitDims = set()
    for factColName, colDims in factDimensions.items():
        if colDims is not None:
            factDims = set()
            for inheritedDims in (colDims, tableDimensions, reportDimensions):
                for dimName, dimValue in inheritedDims.items():
                    checkParamRef(dimValue, factColName, dimName)
                    factDims.add(dimName)
            parseMetadataCellValues(colDims)
            for _factDecimals in (factDecimals.get(factColName), tableDecimals, reportDecimals):
                if "decimals" not in factDims:
                    checkParamRef(_factDecimals, factColName, "decimals")

    if hasHeaderError:
        return
    rowIds = set()
    paramRefColNames = set()
    potentialInvalidReferenceTargets = {} # dimName: referenceTarget
    for rowIndex, row in enumerate(openCsvReader(url, CSV_FACTS_FILE, txmyMdl)):
        if rowIndex == 0:
            header = [csvCellValue(cell) for cell in row]
            emptyHeaderCols = set()
            colNameIndex = dict((name, colIndex) for colIndex, name in enumerate(header))
            idColIndex = colNameIndex.get(rowIdColName)
            for colIndex, colName in enumerate(header):
                if colName == "":
                    emptyHeaderCols.add(colIndex)
                elif not IdentifierPattern.match(colName):
                    hasHeaderError = True
                    error("xbrlce:invalidHeaderValue",
                          _("Table %(table)s CSV file header column %(column)s is not a valid identifier: %(identifier)s, url: %(url)s"),
                          table=tableId, column=colIndex+1, identifier=colName, url=tableUrl)
                elif colName not in factDimensions and colName not in commentColumns:
                    hasHeaderError = True
                    error("xbrlce:unknownColumn",
                          _("Table %(table)s CSV file header column %(column)s is not in table template definition: %(identifier)s, url: %(url)s"),
                          table=tableId, column=colIndex+1, identifier=colName, url=tableUrl)
                elif colNameIndex[colName] != colIndex:
                    error("xbrlce:repeatedColumnIdentifier",
                          _("Table %(table)s CSV file header columns %(column)s and %(column2)s repeat identifier: %(identifier)s, url: %(url)s"),
                          table=tableId, column=colIndex+1, column2=colNameIndex[colName]+1, identifier=colName, url=tableUrl)
                if colName in tableParameterReferenceNames and colName not in commentColumns:
                    paramRefColNames.add(colName)
            checkedDims = set()
            checkedParams = set()
            def dimChecks():
                for colName, colDims in factDimensions.items():
                    if colDims:
                        yield colDims, "column {} dimension".format(colName)
                # no way to check parameterGroup dimensions at header-row processing time
                for dims, source in ((tableDimensions, "table dimension"),
                                     (reportDimensions, "report dimension"),
                                     ):
                    yield dims, source
                for colName, dec in factDecimals.items():
                    yield {"decimals": dec}, "column {} decimals".format(colName)
                for dec, source in ((tableDecimals, "table decimals"),
                                    (reportDecimals, "report decimals")):
                    if source:
                        yield {"decimals": dec}, source
            for inheritedDims, dimSource in dimChecks():
                for dimName, dimValue in inheritedDims.items():
                    if dimName not in checkedDims:
                        dimValue = inheritedDims[dimName]
                        # resolve column-relative dimensions
                        if isinstance(dimValue, str):
                            if dimValue.startswith("$"):
                                dimValue = dimValue[1:]
                                if not dimValue.startswith("$"):
                                    dimValue, _sep, dimAttr = dimValue.partition("@")
                                    if _sep and dimAttr not in ("start", "end"):
                                        hasHeaderError = True
                                        error("xbrlce:invalidPeriodSpecifier",
                                              _("Table %(table)s %(source)s %(dimension)s period-specifier invalid: %(target)s, url: %(url)s"),
                                              table=tableId, source=dimSource, dimension=dimName, target=dimAttr, url=tableUrl)
                                    if dimValue not in checkedParams:
                                        checkedParams.add(dimValue)
                                        if dimValue in ("rowNumber", ) or (dimValue in header and dimValue not in commentColumns) or dimValue in tableParameters or dimValue in reportParameters:
                                            checkedDims.add(dimValue)
                                        else:
                                            potentialInvalidReferenceTargets[dimName] = dimValue
                            elif ":" in dimName and ":" in dimValue:
                                dimConcept = modelXbrl.qnameConcepts.get(qname(dimName, namespaces))
                                if dimConcept is not None and dimConcept.isExplicitDimension:
                                    memConcept = modelXbrl.qnameConcepts.get(qname(dimValue, namespaces))
                                    if memConcept is not None and modelXbrl.dimensionDefaultConcepts.get(dimConcept) == memConcept:
                                        error("xbrlce:invalidDimensionValue",
                                              _("Table %(table)s %(source)s %(dimension)s value must not be the default member %(member)s, url: %(url)s"),
                                              table=tableId, source=dimSource, dimension=dimName, member=dimValue, url=tableUrl)
            for commentCol in commentColumns:
                colNameIndex.pop(commentCol,None) # remove comment columns from col name index
            unreportedFactDimensionColumns = factDimensions.keys() - set(header)
            reportedDimensionsColumns = dimensionsColumns & set(header)
            if hasHeaderError:
                break # stop processing table
        else:
            rowId = None
            paramColsWithValue = set()
            paramColsUsed = set()
            emptyCols = set()
            emptyHeaderColsWithValue = []
            rowPropGroups = {} # colName, propGroupObject for property groups in this row
            rowPropGroupsUsed = set() # colNames used by propertiesFrom of fact col producing a fact
            hasRowError = False
            rowPropGrpParamRefs = set()
            for propGrpName, propGrpObjects in propertyGroups.items():
                propGrpColIndex = colNameIndex.get(propGrpName, 999999999)
                if propGrpColIndex < len(row):
                    propGrpColValue = csvCellValue(row[propGrpColIndex])
                    if propGrpColValue is NONE_CELL:
                        error("xbrlce:illegalUseOfNone",
                              _("Table %(table)s row %(row)s column %(column)s must not have #none, from %(source)s, url: %(url)s"),
                              table=tableId, row=rowIndex+1, column=colName, url=tableUrl, source=dimSource)
                        hasRowError = True
                    elif propGrpColValue in propGrpObjects:
                        rowPropGroups[propGrpName] = propGrpObjects[propGrpColValue]
                    else:
                        error("xbrlce:unknownPropertyGroup",
                              _("Table %(table)s unknown property group row %(row)s column %(column)s group %(propertyGroup)s, url: %(url)s"),
                              table=tableId, row=rowIndex+1, column=rowIdColName, url=tableUrl, propertyGroup=propGrpName)
                        hasRowError = True
            if hasRowError:
                continue
            rowFactObjs = [] # stream row at a time
            for colIndex, colValue in enumerate(row):
                if colIndex >= len(header):
                    if csvCellValue(colValue) != EMPTY_CELL:
                        emptyHeaderColsWithValue.append(colIndex)
                    continue
                cellPropGroup = {}
                propGroupDimSource = {}
                colName = header[colIndex]
                if colName == "":
                    if csvCellValue(colValue) != EMPTY_CELL:
                        emptyHeaderColsWithValue.append(colIndex)
                    continue
                if colName in commentColumns:
                    continue
                propFromColNames = propertiesFrom.get(colName,EMPTY_LIST)
                for propFromColName in propFromColNames:
                    if propFromColName in rowPropGroups:
                        for prop, val in rowPropGroups[propFromColName].items():
                            if ":" in prop:
                                # Extension property
                                continue
                            if isinstance(val, dict):
                                _valDict = cellPropGroup.setdefault(prop, {})
                                for dim, _val in val.items():
                                    _valDict[dim] = _val
                                    propGroupDimSource[dim] = propFromColName
                                    if _isParamRef(_val):
                                        rowPropGrpParamRefs.add(_getParamRefName(_val))
                            else:
                                cellPropGroup[prop] = val
                                propGroupDimSource[prop] = propFromColName
                                if _isParamRef(val):
                                    rowPropGrpParamRefs.add(_getParamRefName(val))
                if factDimensions[colName] is None:
                    if colName in paramRefColNames:
                        value = csvCellValue(row[colNameIndex[colName]])
                        if value:
                            paramColsWithValue.add(colName)
                        elif value is EMPTY_CELL or value is NONE_CELL:
                            emptyCols.add(colName)
                    if not cellPropGroup:
                        continue # not a fact column
                for rowPropGrpParamRef in rowPropGrpParamRefs:
                    value = None
                    if rowPropGrpParamRef in colNameIndex:
                        value = csvCellValue(row[colNameIndex[rowPropGrpParamRef]])
                    elif rowPropGrpParamRef in tableParameters:
                        value = tableParameters.get(rowPropGrpParamRef)
                    elif rowPropGrpParamRef in reportParameters:
                        value = reportParameters.get(rowPropGrpParamRef)
                    if value in (None, EMPTY_CELL, NONE_CELL):
                        emptyCols.add(rowPropGrpParamRef)
                # assemble row and fact Ids
                if idColIndex is not None and not rowId:
                    if idColIndex < len(row):
                        rowId = csvCellValue(row[idColIndex])
                    if not rowId:
                        error("xbrlce:missingRowIdentifier",
                              _("Table %(table)s missing row %(row)s column %(column)s row identifier, url: %(url)s"),
                              table=tableId, row=rowIndex+1, column=rowIdColName, url=tableUrl)
                    elif not RowIdentifierPattern.match(rowId):
                        error("xbrlce:invalidRowIdentifier",
                              _("Table %(table)s row %(row)s column %(column)s is not valid as a row identifier: %(identifier)s, url: %(url)s"),
                              table=tableId, row=rowIndex+1, column=rowIdColName, identifier=rowId, url=tableUrl)
                    elif rowId in rowIds:
                        error("xbrlce:repeatedRowIdentifier",
                              _("Table %(table)s row %(row)s column %(column)s is a duplicate: %(identifier)s, url: %(url)s"),
                              table=tableId, row=rowIndex+1, column=rowIdColName, identifier=rowId, url=tableUrl)
                    else:
                        rowIds.add(rowId)
                        paramColsUsed.add(rowIdColName)
                factId = "{}.r_{}.{}".format(tableId, rowId or rowIndex, colName) # pre-pend r_ to rowId col value or row number if no rowId col value
                fact = {}
                # if this is an id column
                cellValue = csvCellValue(colValue) # nil facts return None, #empty string is ""
                if cellValue is EMPTY_CELL: # no fact produced
                    continue
                if cellValue is NONE_CELL:
                    error("xbrlce:illegalUseOfNone",
                          _("Table %(table)s row %(row)s column %(column)s must not have #none, from %(source)s, url: %(url)s"),
                          table=tableId, row=rowIndex+1, column=colName, url=tableUrl, source=dimSource)
                    continue
                if cellPropGroup:
                    for propFromColName in propFromColNames:
                        rowPropGroupsUsed.add(propFromColName)
                if colName in extensionColumnProperties: # merge extension properties to fact
                    fact.update(extensionColumnProperties[colName])
                fact["value"] = cellValue
                fact["dimensions"] = colFactDims = {}
                noValueDimNames = set()
                factDimensionSourceCol = {} # track consumption of column value dynamically
                factDimensionPropGrpCol = {}
                for inheritedDims, dimSource in ((factDimensions[colName], "column dimension"),
                                                 (cellPropGroup.get("dimensions",EMPTY_DICT), "propertyGroup {}".format(propFromColNames)),
                                                 (tableDimensions, "table dimension"),
                                                 (reportDimensions, "report dimension")):
                    for dimName, dimValue in inheritedDims.items():
                        if dimSource.startswith("propertyGroup"):
                            factDimensionPropGrpCol[dimName] = propGroupDimSource[dimName]
                        if dimName not in colFactDims and dimName not in noValueDimNames:
                            dimValue = inheritedDims[dimName]
                            dimAttr = None
                            # resolve column-relative dimensions
                            if isinstance(dimValue, str) and dimValue.startswith("$"):
                                dimValue = dimValue[1:]
                                if not dimValue.startswith("$"):
                                    paramName, _sep, dimAttr = dimValue.partition("@")
                                    if paramName == "rowNumber":
                                        dimValue = str(rowIndex)
                                    elif paramName in colNameIndex:
                                        dimValue = csvCellValue(row[colNameIndex[paramName]])
                                        if dimValue is EMPTY_CELL or dimValue is NONE_CELL: # csv file empty cell or  none
                                            dimValue = NONE_CELL
                                        else:
                                            factDimensionSourceCol[dimName] = paramName
                                    elif paramName in tableParameters:
                                        dimValue = tableParameters[paramName]
                                        factDimensionSourceCol[dimName] = paramName
                                    elif paramName in reportParameters:
                                        dimValue = reportParameters[paramName]
                                        factDimensionSourceCol[dimName] = paramName
                                    elif paramName in unreportedFactDimensionColumns:
                                        dimValue = NONE_CELL
                                    else:
                                        dimValue = INVALID_REFERENCE_TARGET
                            # else if in parameters?
                            if dimName == "period" and dimValue is not INVALID_REFERENCE_TARGET:
                                _dimValue = csvPeriod(dimValue, dimAttr)
                                if _dimValue == "referenceTargetNotDuration":
                                    error("xbrlce:referenceTargetNotDuration",
                                          _("Table %(table)s row %(row)s column %(column)s has instant date with period reference \"%(date)s\", from %(source)s, url: %(url)s"),
                                          table=tableId, row=rowIndex+1, column=colName, date=dimValue, url=tableUrl, source=dimSource)
                                    dimValue = NONE_CELL
                                elif _dimValue is None: # bad format, raised value error
                                    error("xbrlce:invalidPeriodRepresentation",
                                          _("Table %(table)s row %(row)s column %(column)s has lexical syntax issue with date \"%(date)s\", from %(source)s, url: %(url)s"),
                                          table=tableId, row=rowIndex+1, column=colName, date=dimValue, url=tableUrl, source=dimSource)
                                    dimValue = NONE_CELL
                                else:
                                    dimValue = _dimValue
                            if dimValue is NONE_CELL:
                                noValueDimNames.add(dimName)
                            else:
                                colFactDims[dimName] = dimValue
                if factDecimals.get(colName) is not None:
                    dimValue = factDecimals[colName]
                    dimSource = "column decimals"
                elif "decimals" in cellPropGroup:
                    dimValue = cellPropGroup["decimals"]
                    dimSource = "propertyGroup " + propFromColName
                    if _isParamRef(dimValue):
                        factDimensionPropGrpCol["decimals"] = _getParamRefName(dimValue)
                    else:
                        factDimensionPropGrpCol["decimals"] = dimValue
                elif tableDecimals is not None:
                    dimValue = tableDecimals
                    dimSource = "table decimals"
                elif reportDecimals is not None:
                    dimValue = reportDecimals
                    dimSource = "report decimals"
                else:
                    dimValue = None
                    dimSource = "absent"
                if dimValue is not None:
                    validCsvCell = False
                    if isinstance(dimValue, str) and dimValue.startswith("$"):
                        paramName = dimValue[1:].partition("@")[0]
                        if paramName in colNameIndex:
                            dimSource += " from CSV column " + paramName
                            dimValue = csvCellValue(row[colNameIndex[paramName]])
                            validCsvCell = XmlValidate.integerPattern.match(dimValue or "") is not None # is None if is_XL
                            if dimValue is not NONE_CELL and dimValue != "" and dimValue != "#none":
                                factDimensionSourceCol["decimals"] = paramName
                        elif paramName in tableParameters:
                            dimSource += " from table parameter " + paramName
                            dimValue = tableParameters[paramName]
                            if dimValue != "" and dimValue != "#none" and XmlValidate.integerPattern.match(dimValue):
                                dimValue = int(dimValue)
                        elif paramName in reportParameters:
                            dimSource += " from report parameter " + paramName
                            dimValue = reportParameters[paramName]
                            if dimValue != "" and dimValue != "#none" and XmlValidate.integerPattern.match(dimValue):
                                dimValue = int(dimValue)
                        else:
                            dimValue = INVALID_REFERENCE_TARGET
                            validCsvCell = True # must wait to see if it's used later
                    if dimValue is INVALID_REFERENCE_TARGET:
                        fact["decimals"] = dimValue # allow referencing if not overridden by decimals suffix
                    elif dimValue is not NONE_CELL and dimValue != "" and dimValue != "#none":
                        if isinstance(dimValue, int) or validCsvCell:
                            fact["decimals"] = dimValue
                        else:
                            error("xbrlce:invalidDecimalsValue",
                                  _("Table %(table)s row %(row)s column %(column)s has invalid decimals \"%(decimals)s\", from %(source)s, url: %(url)s"),
                                  table=tableId, row=rowIndex+1, column=colName, decimals=dimValue, url=tableUrl, source=dimSource)
                factPositionObj = XbrlFact(xbrlMdlObjIndex=len(txmyMdl.xbrlObjects))
                txmyMdl.xbrlObjects.append(factPositionObj)
                factPositionObj.report = table.report
                factPositionObj.name = qname(factId, prefixNamespaces)
                factPositionObj.value = fact.get("value")
                factPositionObj.decimals = None
                factPositionObj.factDimensions = {}
                dimensionsUsed = set()
                cObj = None
                for dim, val in fact["dimensions"].items():
                    valIsQname = dim == "concept"
                    if ":" in dim:
                        dim = qname(dim, prefixNamespaces)
                        if dim is None:
                            error("xbrlce:invalidReferenceTarget",
                                  _("Table %(table)s %(dimension)s target not in table columns, parameters or report parameters"),
                                  table=tableId, dimension=dim)
                            continue
                        dimObj = txmyMdl.namedObjects.get(dim)
                        if isinstance(dimObj, XbrlDimension) and dimObj.isExplicitDimension:
                            valIsQname = True
                    elif dim in ("concept", "period", "entity"):
                        dimensionsUsed.add(dim)
                    if valIsQname:
                        val = qname(val, prefixNamespaces)
                        if val is None:
                            error("xbrlce:invalidReferenceTarget",
                                  _("Table %(table)s %(dimension)s value %(value)s target not in table columns, parameters or report parameters"),
                                  table=tableId, dimension=dim, value=val)
                            continue
                        if dim == "concept":
                            cObj = txmyMdl.namedObjects.get(val)
                    factPositionObj.factDimensions[coreDimensionsByLocalname.get(dim,dim)] = val
                if isinstance(cObj, XbrlConcept):
                    if "language" in fact["dimensions"] and cObj.isOimTextFactType(txmyMdl):
                        dimensionsUsed.add("language")

                    if cObj.isNumeric(txmyMdl):
                        factPositionObj.decimals = fact.get("decimals")

                rowFactObjs.append(factPositionObj)

                for dimName, dimSource in factDimensionSourceCol.items():
                    if dimName in dimensionsUsed:
                        paramColsUsed.add(dimSource)
                for dimName in dimensionsUsed:
                    if dimName in factDimensionPropGrpCol:
                        paramColsUsed.add(factDimensionPropGrpCol[dimName])

            yield rowIndex, rowFactObjs

            unmappedParamCols = (paramColsWithValue | rowPropGrpParamRefs | reportedDimensionsColumns) - paramColsUsed - emptyCols
            if unmappedParamCols:
                error("xbrlce:unmappedCellValue",
                      _("Table %(table)s row %(row)s unmapped parameter columns %(columns)s, url: %(url)s"),
                      table=tableId, row=rowIndex+1, columns=", ".join(sorted(unmappedParamCols)), url=tableUrl)
            unmappedPropGrps = rowPropGroups.keys() - rowPropGroupsUsed
            if unmappedPropGrps:
                error("xbrlce:unmappedCellValue",
                      _("Table %(table)s row %(row)s unmapped property group columns %(columns)s, url: %(url)s"),
                      table=tableId, row=rowIndex+1, columns=", ".join(sorted(unmappedPropGrps)), url=tableUrl)
            if emptyHeaderColsWithValue:
                error("xbrlce:unmappedCellValue",
                      _("Table %(table)s row %(row)s empty-header columns with unmapped values in columns %(columns)s, url: %(url)s"),
                      table=tableId, row=rowIndex+1, columns=", ".join(str(c) for c in emptyHeaderColsWithValue), url=tableUrl)

