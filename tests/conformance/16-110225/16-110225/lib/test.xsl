<?xml version="1.0" encoding="UTF-8"?>
<!-- Copyright 2007 XBRL International. All Rights Reserved. -->
<xsl:stylesheet 
  version="1.0" 
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:case="http://edgar/2009/conformance" 
  >
  

  
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
          <xsl:copy-of select="." />
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
      <xsl:value-of select="case:description"/>
    </td>
    <td>
      <xsl:apply-templates select="case:reference"/>&#160;
    </td>
    <td>
      <xsl:apply-templates select="case:data"/>
    </td>
    <td>
      <xsl:apply-templates select="case:result"/>&#160;
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
    <xsl:call-template name="link">
      <xsl:with-param name="text" select="text()"/>
    </xsl:call-template>
    <xsl:apply-templates select="@readMeFirst"/>
  </li>
</xsl:template>

<xsl:template match="case:schema">
  <li>
    Schema
    <xsl:call-template name="link">
      <xsl:with-param name="text" select="text()"/>
    </xsl:call-template>
    <xsl:apply-templates select="@readMeFirst"/>
  </li>
</xsl:template>

<xsl:template match="case:linkbase">
  <li>
    Linkbase
    <xsl:call-template name="link">
      <xsl:with-param name="text" select="text()"/>
    </xsl:call-template>
    <xsl:apply-templates select="@readMeFirst"/>
    <xsl:apply-templates select="@id"/>
  </li>
</xsl:template>
  
  <xsl:template name="link">
    <xsl:param name="text"/>
    <a href="{$text}">
      <xsl:value-of select="$text"/>
      <xsl:if test="string-length($text) &gt; 32">
        <xsl:value-of select="concat(' !ERROR: ',string-length($text),' IS MORE THAN 32')"/>
      </xsl:if>
    </a>
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
  
  <xsl:template match="case:assert">
    <li>
      <table align="top">
        <tr><th colspan="2" align="left">Assertion</th></tr>
        <tr><td colspan="2" align="left">ID:  <xsl:value-of select="@severity"/>, <xsl:value-of select="@num"/>, <a href="../../../lib/xbrlerrors.htm#{@frd}-{substring(@num,2,4)}-{@name}"><xsl:value-of select="@name"/></a></td></tr>
        <xsl:if test="@frd"><tr><td>FRD:</td><td><xsl:value-of select="@frd"/></td></tr></xsl:if>        
        <tr><td>Count satisfied</td><td>
          <xsl:choose>
            <xsl:when test="@countSatisfied"><xsl:value-of select="@countSatisfied"/></xsl:when>
            <xsl:otherwise>0</xsl:otherwise>
          </xsl:choose>
        </td>
        </tr>
        <tr>
          <td>Count not satisfied</td>
          <td>
          <xsl:choose>
            <xsl:when test="@countNotSatisfied"><xsl:value-of select="@countNotSatisfied"/></xsl:when>
            <xsl:otherwise>1</xsl:otherwise>
          </xsl:choose>
          </td>
        </tr>
      </table>
    </li>
  </xsl:template>

<xsl:template match="@readMeFirst">
        <xsl:if test=".='true'">
ReadMeFirst</xsl:if>
</xsl:template>
<xsl:template match="@id">
        id=<xsl:value-of select="."/>
</xsl:template>

<xsl:template match="case:reference">
PCR <xsl:value-of select="@specification" />
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