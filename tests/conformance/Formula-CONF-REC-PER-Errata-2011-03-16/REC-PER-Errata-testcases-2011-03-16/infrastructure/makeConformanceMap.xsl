<?xml version="1.0" encoding="UTF-8"?>
<!-- Copyright 2007 XBRL International. All Rights Reserved. -->
<!-- 
This stylesheet produces a simple map of conformance suite tests
to parts of the specifications being tested based upon their IDs.
 -->
<xsl:stylesheet version="2.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:case="http://xbrl.org/2008/conformance"
  xmlns:s="http://xbrl.org/conformance/2007/specifications"
  xmlns:m="http://xbrl.org/conformance/2007/map"
  xmlns:eg="http://xbrl.org/2005/example">

  <xsl:output indent="yes"/>

  <xsl:param name="specificationsDocument" select="'specifications.xml'"/>
  <xsl:variable name="specifications" select="document($specificationsDocument)/*/*"/>

  <xsl:template match="/">
    <xsl:variable name="tests" select="/documentation/testcases/testcase"/>
    <m:map>
      <xsl:for-each select="$tests">
        <xsl:variable name="testURL" select="concat(../@root,'/',./@uri)"/>
        <xsl:variable name="test" select="document($testURL,/.)/case:testcase"/>
        <xsl:variable name="test.references" select="$test/case:reference"/>
        <xsl:variable name="number" select="document($testURL,/.)/case:testcase/case:number"/>
        <xsl:for-each select="$test.references">
          <xsl:variable name="spec" select="@specification"/>
          <xsl:variable name="partID" select="@id"/>
          <xsl:variable name="specID" select="$specifications[@id=$spec]/@sid"/>
          <m:entry
            specId="{$specID}"
            partId="{$partID}"
            number="{$number}"
            testURL="{$testURL}"
          />
        </xsl:for-each>
        <xsl:variable name="variation.references" select="$test/case:variation/case:reference"/>
        <xsl:for-each select="$variation.references">
          <xsl:variable name="spec" select="@specification"/>
          <xsl:variable name="partID" select="@id"/>
          <xsl:variable name="specID" select="$specifications[@id=$spec]/@sid"/>
          <m:entry
            specId="{$specID}"
            partId="{$partID}"
            number="{$number}:{./../@id}"
            testURL="{$testURL}"
          />
        </xsl:for-each>
      </xsl:for-each>
    </m:map>
  </xsl:template>

</xsl:stylesheet>
