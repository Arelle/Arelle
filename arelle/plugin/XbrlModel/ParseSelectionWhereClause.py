"""
See COPYRIGHT.md for copyright information.
"""

from pyparsing import (
    Word, alphas, alphanums, Suppress, QuotedString, Group, delimitedList,
    oneOf, Combine, Literal, Optional, pyparsing_common as ppc, Keyword, MatchFirst
    )

# Define basic elements
colon = Literal(":")
ncName = Word(alphas, alphanums + "_-")
qName = Combine(ncName + colon + ncName)  # e.g., xbrl:conceptObject

# Define operators with proper precedence (multi-word operators first)
inOperator = (Keyword("not in") | Keyword("in")).setParseAction(lambda t: t[0])
containsOperator = (Keyword("not contains") | Keyword("contains")).setParseAction(lambda t: t[0])
comparisonOperator = oneOf("== != > < >= <=")
operator = MatchFirst([inOperator, containsOperator, comparisonOperator])

# Special handling for "in" and "not in" values which should be lists
nonListValue = QuotedString('"', escChar='\\') | QuotedString("'", escChar='\\') | ppc.number | Word(alphanums + "_:.-")  # Support strings, numbers, and xs:decimal
listValue = Suppress("[") + delimitedList(nonListValue) + Suppress("]")

# Define a condition with special handling for different operator types
def conditionParseAction(str, unk, wheres):
    return wheres

condition = Group(
    ncName("property") +
    operator("operator") +
    (listValue | nonListValue)("value")
).setParseAction(conditionParseAction)

# Define the full parser
selWhereParser = qName("objectType") + Suppress("where") + delimitedList(condition, delim=oneOf("AND OR"))

def parseSelectionWhereClause(selWhereClause):
    try:
        parsed = selWhereParser.parseString(selWhereClause, parseAll=True)

        # Build the result structure
        return {
                "objectType": parsed.objectType,
                "where": [
                    {
                        "property": cond["property"],
                        "operator": cond["operator"],
                        "value": (
                            [v for v in cond["value"]] if cond["operator"] in ('in', 'not in') else
                            cond["value"][0]
                            )
                    }
                    for cond in parsed[1:]
                ]
            }

    except Exception as e:
        return f"Parsing failed: {str(e)}"

if __name__ == "__main__":
    # test cases
    test_cases = [
        'xbrl:conceptObject where periodType = "instant" AND dataType = \'xs:decimal\'',
        'xbrl:measure where value > 100 OR unit != "USD"',
        'xbrl:entity where schema in ["ifrs","us-gaap"]',
        'xbrl:fact where contextRef not in ["Q1","Q2"]',
        'xbrl:concept where label contains "profit"',
        'xbrl:element where documentation not contains "deprecated"'
    ]

    for test in test_cases:
        print(f"Input: {test}")
        print(f"Output: {parseSelectionWhereClause(test)}")
        print("\n")