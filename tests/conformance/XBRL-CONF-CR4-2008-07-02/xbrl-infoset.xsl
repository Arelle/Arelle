<!-- edit by Ron van Ardenne, J2R BV (www.batavia-xbrl.com) for XBRL SpecV2 Working Group of XBRL International -->

<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">

<!-- do NOT indent-->
<xsl:output method = "xml" encoding ="UTF-8" indent="no" omit-xml-declaration = "yes"/>

<!-- no white space -->
<xsl:strip-space elements="*"/>

<xsl:template match="/">
<document>
<children>
<xsl:apply-templates  select="@*|node()[not(self::comment()|self::text())]">

<!-- sort on name -->
<xsl:sort select="name()"/>

<!-- sort on attribute values -->
<xsl:sort select="@*"/>

<!-- sort on values -->
<xsl:sort />      
     
</xsl:apply-templates>
</children>
</document>
</xsl:template>

<!-- Templates for each node type follows.-->
  
<xsl:template match="*">
        <xsl:element name="element">
		<localName><xsl:value-of select="local-name()"/></localName>
		<namespaceName><xsl:value-of select="namespace-uri()"/></namespaceName>
            <children>
                <xsl:apply-templates select="*|node()[not(self::comment()|self::text())]">
			<!-- sort on name -->
			<xsl:sort select="namespace-uri()"/>
			<xsl:sort select="local-name()"/>

			<!-- sort on PTVI attribute values -->
			<xsl:sort select="@contextRef"/>
			<xsl:sort select="@precision"/>
			<xsl:sort select="@balance"/>
			<xsl:sort select="@periodType"/>
			<xsl:sort select="@unitRef"/>

			<!-- sort on PTVLI attribute values -->
			<xsl:sort select="@preferredLabel"/>
			<xsl:sort select="@arcRole"/>
			<xsl:sort select="@extRole"/>
			<xsl:sort select="@fromPath"/>
			<xsl:sort select="@labelLang"/>
			<xsl:sort select="@linkType"/>
			<xsl:sort select="@order"/>
			<xsl:sort select="@resRole"/>
			<xsl:sort select="@toPath"/>
			<xsl:sort select="@weight"/>

			<!-- sort on values -->
			<xsl:sort />      

		     </xsl:apply-templates>

		</children>
		<attributes>
                <xsl:apply-templates select = "@*">
				<xsl:sort select="name()"/>
		    </xsl:apply-templates>
		</attributes>
		</xsl:element>
</xsl:template>

<xsl:template match="@*">
        <xsl:element name="attribute">
		<namespaceName><xsl:value-of select="namespace-uri()"/></namespaceName>
		<localName><xsl:value-of select="local-name()"/></localName>
		<!-- ingnore schemalocation value-->
		<xsl:if test="local-name()!='schemaLocation'">
			<normalizedValue><xsl:value-of select = "."/></normalizedValue>
		</xsl:if>
        </xsl:element>
</xsl:template>

<xsl:template name="namespace">
        <xsl:element name="namespace" >
		<namespaceName><xsl:value-of select = "."/></namespaceName>
        </xsl:element>
</xsl:template>

<xsl:template match="processing-instruction()">
        <xsl:element name="processingInstruction">
		<target><xsl:value-of select = "name()"/></target>
		<content><xsl:value-of select = "."/></content>
        </xsl:element>
</xsl:template>

<xsl:template match="text()"/>
 
<xsl:template match="comment()"/>

</xsl:stylesheet>