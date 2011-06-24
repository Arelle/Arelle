<?xml version="1.0" encoding="UTF-8"?>
<!-- Copyright 2007 XBRL International. All Rights Reserved. -->
<xsl:stylesheet 
  version="1.0" 
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:case="http://xbrl.org/2008/conformance" 
  xmlns:s="http://xbrl.org/conformance/2008/specifications"
  xmlns:xh="http://www.w3.org/1999/xhtml"
  >
  
<xsl:variable name="specifications" select="document('specifications.xml')/*/*"/>
  
<xsl:template match="/">
<xsl:apply-templates select="case:testcase"/>
</xsl:template>  
  
<xsl:template match="case:testcase">
  <html>
    <head>
      <title>
        <xsl:value-of select="case:number" />
        :
        <xsl:value-of select="case:name" />
      </title>
    </head>
    <body>
        
      <h1>
        <xsl:value-of select="case:number" />
        :
        <xsl:value-of select="case:name" />
      </h1>
      
      <p>
        Created by: 
        <a href="mailto: {case:creator/case:email}">
          <xsl:value-of select="case:creator/case:name" />
        </a>
      </p>

      <xsl:for-each select="case:description">
        <p>
          <xsl:value-of select="." />
        </p>
      </xsl:for-each>
  
      <xsl:if test="count(case:reference) &gt; 0">
        <h3>References</h3>
        <ul>
          <xsl:apply-templates select="case:reference"/>
        </ul>
      </xsl:if>
      
      <h2>
        Variations
      </h2>
      
      <table border="solid">
        <thead>
          <tr>
            <th>Number</th>
            <th>Name</th>
            <th>Description</th>
            <th>References</th>
            <th>Data Inputs</th>
            <th>Result Outputs</th>
          </tr>
        </thead>
        <tbody>
          <xsl:apply-templates select="case:variation" />
        </tbody>
      </table>
    </body>
  </html>
</xsl:template>
    
<xsl:template match="case:variation">
  <tr>
        <td>
      <xsl:value-of select="@id"/>
    </td>
    <td>
      <xsl:value-of select="case:name"/>
    </td>
    <td>
      <xsl:apply-templates select="case:description"/>
    </td>
    <td>
      <xsl:apply-templates select="case:reference"/>
    </td>
    <td>
      <xsl:apply-templates select="case:data"/>
    </td>
    <td>
      <xsl:apply-templates select="case:result"/>
    </td>
  </tr>
</xsl:template>

<xsl:template match="case:data | case:result">
  <ul>
    <xsl:if test="@expected" >
      <xsl:apply-templates select="@expected" />
    </xsl:if>
    <xsl:apply-templates select="*"/>
  </ul>
</xsl:template>

<xsl:template match="case:instance">
  <li>
    Instance
    <a href="{text()}">
      <xsl:value-of select="text()"/>
    </a>
    <xsl:apply-templates select="@readMeFirst"/>
    <xsl:if test="@name">
        <br/>Name
        <xsl:apply-templates select="@name"/>
    </xsl:if>
  </li>
</xsl:template>

<xsl:template match="case:schema">
  <li>
    Schema
    <a href="{text()}">
      <xsl:value-of select="text()"/>
    </a>
    <xsl:apply-templates select="@readMeFirst"/>
  </li>
</xsl:template>

<xsl:template match="case:linkbase">
  <li>
    Linkbase
    <a href="{text()}">
      <xsl:value-of select="text()"/>
    </a>
    <xsl:apply-templates select="@readMeFirst"/>
    <xsl:apply-templates select="@id"/>
  </li>
</xsl:template>

<xsl:template match="case:parameter">
  <li>
    <table align="top">
    <tr><th colspan="2" align="left">Parameter</th></tr>
    <tr><td>Name</td><td><xsl:value-of select="@name"/></td></tr>
    <tr><td>Type</td><td><xsl:value-of select="@datatype"/></td></tr>
    <tr><td>Value</td><td><xsl:value-of select="@value"/></td></tr>
    </table>
  </li>
</xsl:template>

<xsl:template match="case:filter">
  <li>
    <table align="top">
    <tr><th colspan="2" align="left">Filter</th></tr>
    <tr><td>File</td><td><xsl:value-of select="@file"/></td></tr>
    <tr><td>Filter</td><td><xsl:value-of select="@filter"/></td></tr>
    </table>
  </li>
</xsl:template>

<xsl:template match="case:assertionTests">
  <li>
    <table align="top">
    <tr><th colspan="2" align="left">Assertion</th></tr>
    <tr><td colspan="2" align="left">ID: <xsl:value-of select="@assertionID"/></td></tr>
    <tr><td>Count satisfied</td><td><xsl:value-of select="@countSatisfied"/></td></tr>
    <tr><td>Count not satisfied</td><td><xsl:value-of select="@countNotSatisfied"/></td></tr>
    </table>
  </li>
</xsl:template>

<xsl:template match="case:filterTest">
  <li>
      Filter test: <xsl:value-of select="./text()"/>
  </li>
</xsl:template>

<xsl:template match="case:error">
  <li>
      Error code: <xsl:value-of select="./text()"/>
  </li>
</xsl:template>

<xsl:template match="case:messageTests">
  <li>
    <table align="top">
    <tr><th colspan="2" align="left">Message</th></tr>
    <tr><td colspan="2" align="left">ID: <xsl:value-of select="@assertionID"/></td></tr>

    <xsl:for-each select="case:satisfied">
    <tr><td nowrap="nowrap">Satisfied<xsl:if test="./@xml:lang">(<xsl:value-of select="./@xml:lang"/>)</xsl:if></td><td><xsl:value-of select="."/></td></tr>
    </xsl:for-each>
    <xsl:for-each select="case:notSatisfied">
    <tr><td nowrap="nowrap">NotSatisfied<xsl:if test="./@xml:lang">(<xsl:value-of select="./@xml:lang"/>)</xsl:if></td><td><xsl:value-of select="."/></td></tr>
    </xsl:for-each>
    </table>
  </li>
</xsl:template>

<xsl:template match="@readMeFirst">
        <xsl:if test=".='true'">
            <br/>ReadMeFirst
        </xsl:if>
</xsl:template>
<xsl:template match="@id">
        id=<xsl:value-of select="."/>
</xsl:template>

<xsl:template match="xh:*">
  <xsl:element name="{local-name()}">
    <xsl:copy-of select="@*"/>
      <xsl:apply-templates/>
  </xsl:element>
</xsl:template>

<xsl:template match="case:reference">
  <li>
    <xsl:variable name="reference" select="@specification" />
    <xsl:variable name="url">
      <xsl:choose>
        <xsl:when test="count($specifications[@id=$reference])>0">
          <xsl:value-of select="$specifications[@id=$reference]/@href"/>
        </xsl:when>
        <xsl:otherwise>
          <xsl:value-of select="$reference"/>
        </xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <a href="{$url}#{@id}">
      <xsl:value-of select="@specification" />:
      <xsl:value-of select="@id" />
    </a>
  </li>
</xsl:template>


</xsl:stylesheet>
<!-- Stylus Studio meta-information - (c) 2004-2007. Progress Software Corporation. All rights reserved.

<metaInformation>
        <scenarios>
                <scenario default="yes" name="Scenario1" userelativepaths="yes" externalpreview="no" url="..\tests\70000 Linkbase\70016-GenericLink-StaticAnalysis-Arc-Arcrole\70016 GenericLink Arc Arcrole StaticAnalysis.xml" htmlbaseurl="" outputurl=""
                          processortype="saxon8" useresolver="yes" profilemode="0" profiledepth="" profilelength="" urlprofilexml="" commandline="" additionalpath="" additionalclasspath="" postprocessortype="none" postprocesscommandline=""
                          postprocessadditionalpath="" postprocessgeneratedext="" validateoutput="no" validator="internal" customvalidator="">
                        <advancedProp name="sInitialMode" value=""/>
                        <advancedProp name="bXsltOneIsOkay" value="true"/>
                        <advancedProp name="bSchemaAware" value="true"/>
                        <advancedProp name="bXml11" value="false"/>
                        <advancedProp name="iValidation" value="0"/>
                        <advancedProp name="bExtensions" value="true"/>
                        <advancedProp name="iWhitespace" value="0"/>
                        <advancedProp name="sInitialTemplate" value=""/>
                        <advancedProp name="bTinyTree" value="true"/>
                        <advancedProp name="bWarnings" value="true"/>
                        <advancedProp name="bUseDTD" value="false"/>
                        <advancedProp name="iErrorHandling" value="fatal"/>
                </scenario>
        </scenarios>
        <MapperMetaTag>
                <MapperInfo srcSchemaPathIsRelative="yes" srcSchemaInterpretAsXML="no" destSchemaPath="" destSchemaRoot="" destSchemaPathIsRelative="yes" destSchemaInterpretAsXML="no"/>
                <MapperBlockPosition></MapperBlockPosition>
                <TemplateContext></TemplateContext>
                <MapperFilter side="source"></MapperFilter>
        </MapperMetaTag>
</metaInformation>
-->