<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet 
  version="1.0" 
  xmlns:case="http://xbrl.org/2011/conformance-rendering/transforms" 
  xmlns:ixt="http://www.xbrl.org/inlineXBRL/transformation/WGWD/YYYY-MM-DD"
  xmlns:reg="http://xbrl.org/2008/registry"
  xmlns:xs="http://www.w3.org/2001/XMLSchema"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:func="http://xbrl.org/2008/function"
  
  >
<xsl:output indent="yes"/>
<xsl:param name="result"/>
<xsl:template match="/">
	<testcase xmlns="http://xbrl.org/2008/conformance"
	  xmlns:reg="http://xbrl.org/2008/registry"
	  xmlns:cfcn="http://xbrl.org/2008/conformance/function"
	  xmlns:ixt-sec="http://www.sec.gov/inlineXBRL/transformation/2015-08-31" 
	  xmlns:xs="http://www.w3.org/2001/XMLSchema" 
	  xmlns:xhtml="http://www.w3.org/1999/xhtml"
	  xmlns:xlink="http://www.w3.org/1999/xlink"
	  xmlns:xqt-err="http://www.w3.org/2005/xqt-errors"
	  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
	  >

	  <owners>
	    <reg:owner id="herm">
	      <reg:name>Herm Fischer</reg:name>
	      <reg:affiliation>Mark V Systems Limited</reg:affiliation>
	      <reg:email>fischer@markv.com</reg:email>
	     <reg:assumedOwnership moment="2014-09-18T12:00:00" />
	    </reg:owner>
	  </owners>

	  <number>1</number>
	  
	  <name>Function tests for Transformation Registry 3</name>

	  <documentation>
	    <xhtml:p>XII formula-formatted test case for ixt transforms in version 3 registry</xhtml:p>
	  </documentation>	

      <xsl:for-each select="case:testcase/case:transform">
	      <xsl:variable name="transformName" select="@name"/>
	      <xsl:variable name="transformType" select="@type"/>
	      <xsl:variable name="transformNum" select="position()"/>
        
	      <xsl:for-each select="case:variation">
   	           <xsl:variable name="input" select="@input"/>
   	           <xsl:variable name="output" select="@output"/>
   	           <xsl:variable name="result" select="@result"/>
   	           <xsl:variable name="description" select="@description"/>
   	           <xsl:variable name="variationNum" select="position()"/>

			   <variation id="V-01">
		         <xsl:attribute name="id">
		            <xsl:value-of select="concat( 'V-', $transformNum, '-', $variationNum )"/>
		         </xsl:attribute>
			     <name>
	   	           <xsl:choose>
	   	           	  <xsl:when test="boolean($description)">
			            <xsl:value-of select="$description"/>
	   	           	  </xsl:when>
	   	           	  <xsl:otherwise>
	   	           	    <xsl:value-of  select="
			                concat( $transformName, '(&quot;', $input, '&quot;)' )
			            "/>
	   	           	  </xsl:otherwise>
	   	           </xsl:choose>
			     </name>
			     <inputs>
			       <cfcn:call>
			         <xsl:value-of select="
			            concat( $transformName, '(&quot;', $input, '&quot;)' )
			         "/>
			       </cfcn:call>
			     </inputs>
			     <outputs>
			       <xsl:choose>
			         <xsl:when test="$result = 'valid'">
				       <cfcn:test>
				         <xsl:value-of select="
				            concat( '$result eq &quot;', $output, '&quot;' )
				          "/>
				       </cfcn:test>
				     </xsl:when>
				     <xsl:otherwise>
				      <error>xqt-err:XPTY0004</error>
				     </xsl:otherwise>
			       </xsl:choose>
			     </outputs>
			    </variation>	        
	      </xsl:for-each>
      </xsl:for-each>
	  <revisions>
	    <revision by="Makefile">
         <xsl:attribute name="on">
            <xsl:value-of select="current-dateTime()"/>
         </xsl:attribute>
	      <xhtml:p>
	        Created the test case by xslt extraction from tests.xml.
	      </xhtml:p>
	    </revision>
	  </revisions>
   </testcase>
</xsl:template>

</xsl:stylesheet>
