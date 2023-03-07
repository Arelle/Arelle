# SEC ixt-sec Transformation Test Cases

## Introduction

This is a XBRL International style test suite to test SEC transformations and ensure they produce expected results or raise an error code.

The test cases are in the standard XBRL International transformation test case format and conforms to the tests.xsd schema provided by XBRL International with its transformation registry tests.

For display purposes, a simple XSLT 1.0 stylesheet is also included:
  tests.xsl

 * Two stylesheets, with accompanying bash wrapper scripts are provided:

     * extract.sh (extractVariations.xsl) creates an XML file containing all valid
   or all invalid test inputs with an xsi:type attribute indicating the input type.

     * extractTestcase.sh (extractTestcase.xsl) extracts all test inputs and
   expected outputs into an XBRL conformance suite test case.

  * run

## Testcase file format

The testcase file is a declarative representation that organizes the tests in a way that a test harness can run the tests.

The testcase element is the root element for a set of individual variations.

The testcase contains these elements:

* transform: A collection of tests for the transform @name with expected output type @outputType.
  * variation: A single test for the transform provided by parent element @name.
    * @input: Attribute with the string to be transformed.
    * @output: Attribute with the xml value of the transformation result, if valid, else empty string.
    * @result: Attribute with "valid" or "invalid", regarding validity of input to transformation.
    * @description: An optional attribute for this test variation

### Operation with Arelle


