"""
:mod:`arelle.FactIndex`
~~~~~~~~~~~~~~~~~~~

.. py:module:: arelle.FactIndex
   :copyright: Copyright 2014 Acsone S. A., All rights reserved.
   :license: Apache-2.
   :synopsis: fast and compact way to find facts based on a property
"""

from arelle import ModelValue

from sqlalchemy import create_engine, Table, \
    Column, Integer, String, \
    Sequence, MetaData, ForeignKey, \
    Boolean
from sqlalchemy.pool import StaticPool
from sqlalchemy.sql import select, and_

TYPED_VALUE = '#TYPED_VALUE#'
DEFAULT = 'default'
NONDEFAULT = 'nondefault'

class FactIndex(object):
    def __init__(self):
        self.engine = create_engine('sqlite://',
                    connect_args={'check_same_thread':False},
                    poolclass=StaticPool)
        self.metadata = MetaData()
        self.facts = Table('facts', self.metadata,
                           Column('id', Integer, Sequence('facts_seq'), primary_key = True),
                           Column('isNil', Boolean, nullable = False, unique = False, index = True),
                           Column('qName', String(256), nullable = False, unique = False, index = True),
                           Column('datatype', String(256), nullable = False, unique = False, index = True),
                           Column('periodType', String(48), nullable = False, unique = False, index = True),
                           Column('objectId', Integer, nullable = False, unique = True, index = True)
                           )
        self.dimensions = Table('dimensions', self.metadata,
                                    Column('id', Integer, Sequence('dimensions_seq'), primary_key = True),
                                    Column('qName', String(256), nullable = False, unique = False, index = True),
                                    Column('isDefault', Boolean, nullable = False, unique = False, index = True),
                                    Column('dimValue', String(256), nullable = True, unique = False, index = True),
                                    Column('factId', Integer, ForeignKey('facts.id', ondelete="CASCADE"))
                                )
        self.metadata.create_all(self.engine)
        self.connection = self.engine.connect()

    def close(self):
        self.connection.close()

    def insertFact(self, fact, modelXbrl):
        concept = fact.concept
        context = fact.context
        factIsNil = fact.isNil
        factQName = str(fact.qname)
        factDatatype = str(concept.typeQname)
        factPeriodType = str(concept.periodType)
        factObjectId = fact.objectIndex
        factsInsert = self.facts.insert().values(isNil = factIsNil,
                                                 qName = factQName,
                                                 datatype = factDatatype,
                                                 periodType = factPeriodType,
                                                 objectId = factObjectId)
        factsInsert.bind = self.engine
        result = self.connection.execute(factsInsert)
        newFactId = result.inserted_primary_key
        result.close()
        if fact.isItem and len(context.qnameDims)>0:
            allDimensions = context.qnameDims.keys()|modelXbrl.qnameDimensionDefaults.keys()
            for dim in allDimensions:
                dimValue = context.dimValue(dim)
                dimValueString = None
                if isinstance(dimValue, ModelValue.QName): # explicit dimension default value
                    dimValueString = str(dimValue)
                    dimValueIsDefault = True
                elif dimValue is not None: # not default
                    dimValueIsDefault = False
                    if dimValue.isExplicit:
                        dimValueString = str(dimValue.memberQname)
                else: # default typed dimension, no value
                    dimValueIsDefault = True
                if dimValueString is None:
                    dimensionsInsert = self.dimensions.insert().values(qName = str(dim),
                                                                       isDefault = dimValueIsDefault,
                                                                       factId = newFactId[0]
                                                                       )
                else:
                    dimensionsInsert = self.dimensions.insert().values(qName = str(dim),
                                                                       isDefault = dimValueIsDefault,
                                                                       dimValue = dimValueString,
                                                                       factId = newFactId[0]
                                                                       )
                dimensionsInsert.bind = self.engine
                result = self.connection.execute(dimensionsInsert)
                result.close()

    def deleteFact(self, fact):
        factObjectId = fact.objectIndex
        delStatement = self.facts.delete().where(self.facts.c.objectId == factObjectId)
        delStatement.bind = self.engine
        result = self.connection.execute(delStatement)
        numberOfDeletedRows = result.rowcount
        result.close()
        return numberOfDeletedRows

    def updateFact(self, fact):
        factObjectId = fact.objectIndex
        factIsNil = fact.isNil
        updateStatement = self.facts.update().where(self.facts.c.objectId == factObjectId).values(isNil = factIsNil)
        updateStatement.bind = self.engine
        result = self.connection.execute(updateStatement)
        numberOfUpdatedRows = result.rowcount
        result.close()
        return numberOfUpdatedRows

    def nonNilFacts(self, modelXbrl):
        selectStmt = select([self.facts.c.objectId]).where(self.facts.c.isNil == False)
        result = self.connection.execute(selectStmt)
        resultSet = set(modelXbrl.modelObjects[row[self.facts.c.objectId]] for row in result)
        result.close()
        return resultSet

    def nilFacts(self, modelXbrl):
        selectStmt = select([self.facts.c.objectId]).where(self.facts.c.isNil == True)
        result = self.connection.execute(selectStmt)
        resultSet = set(modelXbrl.modelObjects[row[self.facts.c.objectId]] for row in result)
        result.close()
        return resultSet

    def factsByQname(self, qName, modelXbrl, defaultValue=None):
        selectStmt = select([self.facts.c.objectId]).where(self.facts.c.qName == str(qName))
        result = self.connection.execute(selectStmt)
        resultSet = set(modelXbrl.modelObjects[row[self.facts.c.objectId]] for row in result)
        result.close()
        if (len(resultSet)>0):
            return resultSet
        else:
            return defaultValue

    def factsByQnameAll(self, modelXbrl):
        selectStmt = select([self.facts.c.qName, self.facts.c.objectId]).order_by(self.facts.c.qName)
        result = self.connection.execute(selectStmt)
        resultList = list()
        oldQName = ''
        currentFacts = list()
        for row in result:
            currentQName = row[self.facts.c.qName]
            if currentQName != oldQName:
                if len(currentFacts)>0:
                    resultList.append((oldQName, currentFacts))
                oldQName = currentQName
                currentFacts = {modelXbrl.modelObjects[row[self.facts.c.objectId]]}
            else:
                currentFacts.add(modelXbrl.modelObjects[row[self.facts.c.objectId]])
        if len(currentFacts)>0:
            resultList.append((oldQName, currentFacts))
        result.close()
        return resultList

    def factsByDatatype(self, typeQname, modelXbrl):
        selectStmt = select([self.facts.c.objectId]).where(self.facts.c.datatype == str(typeQname))
        result = self.connection.execute(selectStmt)
        resultSet = set(modelXbrl.modelObjects[row[self.facts.c.objectId]] for row in result)
        result.close()
        return resultSet

    def factsByPeriodType(self, periodType, modelXbrl):
        selectStmt = select([self.facts.c.objectId]).where(self.facts.c.periodType == str(periodType))
        result = self.connection.execute(selectStmt)
        resultSet = set(modelXbrl.modelObjects[row[self.facts.c.objectId]] for row in result)
        result.close()
        return resultSet

    def factsByDimMemQname(self, dimQname, modelXbrl, memQname=None):
        if memQname is None:
            selectStmt = select([self.facts.c.objectId]).select_from(self.facts.join(self.dimensions)).\
                where(self.dimensions.c.qName == str(dimQname))
        elif memQname == DEFAULT:
            selectStmt = select([self.facts.c.objectId]).select_from(self.facts.join(self.dimensions)).\
                where(and_(self.dimensions.c.qName == str(dimQname), self.dimensions.c.isDefault == True))
        elif memQname == NONDEFAULT:
            selectStmt = select([self.facts.c.objectId]).select_from(self.facts.join(self.dimensions)).\
                where(and_(self.dimensions.c.qName == str(dimQname), self.dimensions.c.isDefault == False))
        else:
            selectStmt = select([self.facts.c.objectId]).select_from(self.facts.join(self.dimensions)).\
                where(and_(self.dimensions.c.qName == str(dimQname), self.dimensions.c.dimValue == str(memQname)))
        result = self.connection.execute(selectStmt)
        resultSet = set(modelXbrl.modelObjects[row[self.facts.c.objectId]] for row in result)
        result.close()
        return resultSet

def testAll():
    class ModelConcept(object):
        def __init__(self, typeQname, periodType):
            self.typeQname = typeQname
            self.periodType = periodType
    
    class ModelContext(object):
        def __init__(self):
            self.qnameDims = set()
        def dimValue(self, dimQname):
            """Caution: copied from ModelInstanceObject!"""
            try:
                return self.qnameDims[dimQname]
            except KeyError:
                try:
                    return self.modelXbrl.qnameDimensionDefaults[dimQname]
                except KeyError:
                    return None

    class Fact(object):
        def __init__(self, concept, context, isNil, qname, objectId, isItem):
            self.concept = concept
            self.context = context
            self.isNil = isNil
            self.qname = qname
            self.objectIndex = objectId
            self.isItem = isItem

    class ModelXbrl(object):
        def __init__(self):
            self.modelObjects = dict()
            self.qnameDimensionDefaults = dict()

    class DimensionValue(object):
        def __init__(self, isExplicit, value):
            self.isExplicit = isExplicit
            self.memberQname = value 
        def __str__(self):
            return self.memberQname
    def assertEquals(expectedValue, actualValue):
        try:
            assert expectedValue == actualValue
        except AssertionError:
            print('Expected %s got %s' % (expectedValue, actualValue))
    modelXbrl = ModelXbrl()
    concept1d = ModelConcept('type1', 'duration')
    concept1i = ModelConcept('type1', 'instant')
    concept2d = ModelConcept('type2', 'duration')
    concept2i = ModelConcept('type2', 'instant')
    dimVal1 = DimensionValue(True, 'val1')
    dimVal2 = DimensionValue(True, 'val2')
    dimVal3 = DimensionValue(True, 'val3')
    dimVal4 = DimensionValue(True, 'val4')
    dimVal5 = DimensionValue(True, 'val5')
    dimVal6 = DimensionValue(True, 'val6')
    context1 = ModelContext()
    context1.qnameDims = {'dim1': dimVal1, 'dim2': dimVal2, 'dim3': dimVal3}
    context2 = ModelContext()
    context2.qnameDims = {'dim1': dimVal1, 'dim7': None}
    context3 = ModelContext()
    context3.qnameDims = {'dim4': dimVal4, 'dim5': dimVal5, 'dim6': dimVal6, 'dim7': None}

    fact1 = Fact(concept1d, context1, False, '{ns}name1', 1, True)
    fact2 = Fact(concept1i, context2, False, '{ns}name1', 2, True)
    fact3 = Fact(concept2d, context3, False, '{ns}name2', 3, True)
    fact4 = Fact(concept2i, context3, False, '{ns}name2', 4, True)
    fact5 = Fact(concept2i, context3, True, '{ns}name3', 5, True)
    fact6 = Fact(concept2d, context3, True, '{ns}name4', 6, False)
    modelXbrl.modelObjects[fact1.objectIndex] = fact1
    modelXbrl.modelObjects[fact2.objectIndex] = fact2
    modelXbrl.modelObjects[fact3.objectIndex] = fact3
    modelXbrl.modelObjects[fact4.objectIndex] = fact4
    modelXbrl.modelObjects[fact5.objectIndex] = fact5
    modelXbrl.modelObjects[fact6.objectIndex] = fact6

    factIndex = FactIndex()
    factIndex.insertFact(fact1, modelXbrl)
    factIndex.insertFact(fact2, modelXbrl)
    factIndex.insertFact(fact3, modelXbrl)
    factIndex.insertFact(fact4, modelXbrl)
    factIndex.insertFact(fact5, modelXbrl)
    factIndex.insertFact(fact6, modelXbrl)
    dataResult = factIndex.nonNilFacts(modelXbrl)
    assertEquals({fact1, fact2, fact3, fact4}, dataResult)
    dataResult = factIndex.nilFacts(modelXbrl)
    assertEquals({fact5, fact6}, dataResult)
    expectedResult = 'NiceJob'
    dataResult = factIndex.factsByQname('doesNotExist', modelXbrl, expectedResult)
    assertEquals(expectedResult, dataResult)
    dataResult = factIndex.factsByQname('{ns}name1', modelXbrl, None)
    assertEquals({fact1, fact2}, dataResult)
    dataResult = factIndex.factsByQname('{ns}name3', modelXbrl, None)
    assertEquals({fact5}, dataResult)
    dataResult = factIndex.factsByDatatype('doesNotExist', modelXbrl)
    assertEquals(set(), dataResult)
    dataResult = factIndex.factsByDatatype('type2', modelXbrl)
    assertEquals({fact3, fact4, fact5, fact6}, dataResult)
    dataResult = factIndex.factsByPeriodType('doesNotExist', modelXbrl)
    assertEquals(set(), dataResult)
    dataResult = factIndex.factsByPeriodType('instant', modelXbrl)
    assertEquals({fact2, fact4, fact5}, dataResult)
    dataResult = factIndex.factsByDimMemQname('doesNotExist', modelXbrl, None)
    assertEquals(set(), dataResult)
    dataResult = factIndex.factsByDimMemQname('dim1', modelXbrl, None)
    assertEquals({fact1, fact2}, dataResult)
    dataResult = factIndex.factsByDimMemQname('dim2', modelXbrl, 'val2')
    assertEquals({fact1}, dataResult)
    dataResult = factIndex.factsByDimMemQname('dim1', modelXbrl, 'val1')
    assertEquals({fact1, fact2}, dataResult)
    dataResult = factIndex.factsByDimMemQname('dim1', modelXbrl, NONDEFAULT)
    assertEquals({fact1, fact2}, dataResult)
    dataResult = factIndex.factsByDimMemQname('dim7', modelXbrl, DEFAULT)
    assertEquals({fact2, fact3, fact4, fact5}, dataResult) # fact6 is not an item!
    dataResult = factIndex.factsByQnameAll(modelXbrl)
    assertEquals([('{ns}name1', {fact1, fact2}), ('{ns}name2', {fact3, fact4}), ('{ns}name3', {fact5}), ('{ns}name4', {fact6})], dataResult);
    fact1.isNil = True
    numberOfUpdatedFacts = factIndex.updateFact(fact1)
    assertEquals(1, numberOfUpdatedFacts)
    dataResult = factIndex.nonNilFacts(modelXbrl)
    assertEquals({fact2, fact3, fact4}, dataResult)
    dataResult = factIndex.nilFacts(modelXbrl)
    assertEquals({fact1, fact5, fact6}, dataResult)
    numberOfDeletedFacts = factIndex.deleteFact(fact1)
    assertEquals(1, numberOfDeletedFacts)
    dataResult = factIndex.nonNilFacts(modelXbrl)
    assertEquals({fact2, fact3, fact4}, dataResult)
    dataResult = factIndex.factsByDimMemQname('dim1', modelXbrl, None)
    assertEquals({fact2}, dataResult)
    dataResult = factIndex.factsByDimMemQname('dim2', modelXbrl, None)
    assertEquals(set(), dataResult)
    factIndex.close()
if __name__ == '__main__':
    testAll()