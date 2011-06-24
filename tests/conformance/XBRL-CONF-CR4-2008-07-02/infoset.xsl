<!--@Copyright: Microsoft Corporation 2002 -->
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
<!--<xsl:output method = "xml" encoding ="UTF-8" omit-xml-declaration = "yes"/>-->
<!--<xsl:preserve-space elements="*" />-->

<xsl:template match="/">
<document>
<children>
<xsl:apply-templates/>
</children>
</document>
</xsl:template>

  
<xsl:template match="*">
        <xsl:element name="element">
		<localName><xsl:value-of select="local-name()"/></localName>
		<namespaceName><xsl:value-of select="namespace-uri()"/></namespaceName>
                <children>
                   <xsl:apply-templates/>
		</children>
		<attributes>
                <xsl:apply-templates select = "@*"><xsl:sort select="name()"/></xsl:apply-templates>
		</attributes>
		<inScopeNamespaces>
		<xsl:for-each select = "namespace::*">
		<xsl:sort select="."/>      
		<xsl:call-template name="namespace"/>	
		</xsl:for-each>
		</inScopeNamespaces>
        </xsl:element>
</xsl:template>
<xsl:template match="@*">	
        <xsl:element name="attribute">
		<namespaceName><xsl:value-of select="namespace-uri()"/></namespaceName>
		<localName><xsl:value-of select="local-name()"/></localName>		
		<normalizedValue><xsl:value-of select = "."/></normalizedValue>
        </xsl:element>
</xsl:template>
<xsl:template name="namespace">
        <xsl:element name="namespace" >
		<namespaceName><xsl:value-of select = "."/></namespaceName>
        </xsl:element>
</xsl:template>
<xsl:template match="processing-instruction()" xml:space="preserve">
        <xsl:element name="processingInstruction">
		<target><xsl:value-of select = "name()"/></target>
		<content><xsl:value-of select = "."/></content>
        </xsl:element>
</xsl:template>

<xsl:template match="text()">
	<xsl:element name="text" xml:space="preserve">
  		<xsl:value-of select = "."/>
	</xsl:element>
</xsl:template> 
  

<xsl:template match="comment()" xml:space="preserve">
        <xsl:element name="comment" >
                <content><xsl:value-of select = "."/></content> 
        </xsl:element>
</xsl:template> 

</xsl:stylesheet>