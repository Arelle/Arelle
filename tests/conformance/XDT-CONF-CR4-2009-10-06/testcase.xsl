<?xml version="1.0" encoding="UTF-8"?>
<!-- edited with XMLSPY v5 rel. 4 U (http://www.xmlspy.com) by Walter Hamscher (Standard Advantage) -->
<!-- XBRL 2.1 Tests -->
<!-- Copyright 2003 XBRL International. All Rights Reserved. -->
<xsl:stylesheet version="1.0" xmlns:conf="http://xbrl.org/2005/conformance" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:fo="http://www.w3.org/1999/XSL/Format" exclude-result-prefixes="fo">
	<xsl:template match="conf:testcase">
		<html>
			<head>
				<title>
					<xsl:value-of select="@name"/>
				</title>
			</head>
			<body>
				<table border="0">
					<tbody>
						<tr>
							<th colspan="3" align="left">
								<xsl:value-of select="@name"/> Tests
							</th>
						</tr>
						<xsl:if test="@minimal='false'">
							<tr>
								<td colspan="3" align="left">Required for Full Conformance</td>
							</tr>
						</xsl:if>
						<tr>
							<td colspan="3">
								<xsl:value-of select="@description"/>
							</td>
						</tr>
						<tr>
							<td colspan="3">Current Owner:
								<a>
									<xsl:attribute name="href">mailto:<xsl:value-of select="@owner"/></xsl:attribute>
									<xsl:value-of select="@owner"/>
								</a>
							</td>
						</tr>
						<tr>
							<td colspan="3">
								<hr style="height:3pt;color:black"/>
							</td>
						</tr>
						<xsl:choose>
							<xsl:when test="string-length(@ignoreIf)>0">
								<tr>
									<td colspan="3">This test is ignored if <i>
											<xsl:value-of select="@ignoreIf"/>
										</i> is required by the XBRL processor being tested.</td>
								</tr>
							</xsl:when>
						</xsl:choose>
						<xsl:apply-templates select="node()"/>
					</tbody>
				</table>
			</body>
		</html>
	</xsl:template>
	<xsl:template match="conf:variation">
		<tr>
			<td colspan="1"/>
			<td colspan="2">
				<table>
					<tbody>
						<tr>
							<th align="left">
								<xsl:value-of select="@id"/> - <xsl:value-of select="@name"/>
							</th>
						</tr>
						<tr>
							<td>
								<xsl:if test="conf:description/@reference">
									Documentation reference: <xsl:value-of select="conf:description/@reference"/><br/>
								</xsl:if>
								<xsl:if test="conf:description/@referenceURI">
									Link to reference: <a><xsl:attribute name="href"><xsl:value-of select="conf:description/@referenceURI"/>
									</xsl:attribute><xsl:value-of select="conf:description/@referenceURI"/></a><br/>
								</xsl:if>
								<xsl:value-of select="conf:description"/>
							</td>
						</tr>
					</tbody>
				</table>
			</td>
		</tr>
		<xsl:apply-templates select="conf:data/*"/>
		<tr>
			<td colspan="1"/>
			<td colspan="1" valign="top">
				Result expected:
			</td>
			<td colspan="1">
				<xsl:choose>
					<xsl:when test="count(conf:result/conf:*) = 0">
						<font color="green">OK</font> - <b>No warnings found</b>
					</xsl:when>
					<xsl:otherwise>
						<xsl:apply-templates select="conf:result/*"/>
					</xsl:otherwise>
				</xsl:choose>
			</td>
		</tr>
		<xsl:if test="count(conf:result/conf:file)">
			<tr>
				<td colspan="1"/>
				<td colspan="1">Result file:</td>
				<td colspan="1">
					<xsl:element name="a">
						<xsl:attribute name="href"><xsl:value-of select="../@outpath"/>/<xsl:value-of select="normalize-space(conf:result/conf:file)"/></xsl:attribute>
						<xsl:value-of select="conf:result/conf:file"/>
					</xsl:element>
				</td>
			</tr>
		</xsl:if>
		<tr>
			<td colspan="3">
				<hr style="height:1pt;color:black"/>
			</td>
		</tr>
	</xsl:template>
	<xsl:template match="conf:xsd|conf:linkbase|conf:xml|conf:instance|conf:schema">
		<tr>
			<td/>
			<td>
				<xsl:choose>
					<xsl:when test="name()='schema'">Schema</xsl:when>
					<xsl:when test="name()='xsd'">Schema</xsl:when>
					<xsl:when test="name()='linkbase'">Linkbase</xsl:when>
					<xsl:when test="name()='xml'">Instance</xsl:when>
					<xsl:when test="name()='instance'">Instance</xsl:when>
					<xsl:otherwise>*Other</xsl:otherwise>
				</xsl:choose>:<xsl:if test="@readMeFirst = 'true'"><b>(S)--></b></xsl:if></td>
			<td>
				<xsl:element name="a">
					<xsl:attribute name="href"><xsl:value-of select="."/></xsl:attribute>
					<xsl:value-of select="."/>
				</xsl:element>
			</td>
		</tr>
	</xsl:template>
	<xsl:template match="conf:warning|conf:error|conf:inconsistency">		
		<xsl:if test="position() > 1"><br/></xsl:if>
		<xsl:choose>
			<xsl:when test="name()='warning'"><font color="yellow">WARNING</font> - </xsl:when>
			<xsl:when test="name()='error'"><font color="red">ERROR</font> - </xsl:when>
			<xsl:when test="name()='inconsistency'"><font color="green">INCONSISTENCY</font> - </xsl:when>
		</xsl:choose>
		<b><xsl:value-of select="."/></b>
	</xsl:template>
	<xsl:template match="node()"/>
</xsl:stylesheet>
