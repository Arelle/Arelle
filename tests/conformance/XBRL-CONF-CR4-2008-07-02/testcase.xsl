<?xml version="1.0" encoding="UTF-8"?>
<!-- edited with XMLSPY v5 rel. 4 U (http://www.xmlspy.com) by Walter Hamscher (Standard Advantage) -->
<!-- XBRL 2.1 Tests -->
<!-- Copyright 2003 XBRL International. All Rights Reserved. -->
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:fo="http://www.w3.org/1999/XSL/Format" exclude-result-prefixes="fo">
	<xsl:template match="testcase">
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
								<xsl:value-of select="@owner"/></a>
							</td>
						</tr>
						<tr>
							<td colspan="3"><hr style="height:3pt;color:black" /></td>
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
	<xsl:template match="variation">
		<tr>
			<td colspan="1"/>
			<td colspan="2">
				<table>
					<tbody>
						<tr>
							<th align="left">
								<xsl:value-of select="@name"/>
							</th>
						</tr>
						<tr>
							<td>
								<xsl:value-of select="description"/>
							</td>
						</tr>
					</tbody>
				</table>
			</td>
		</tr>
		<xsl:apply-templates select="data/*"/>
		<tr>
			<td colspan="1"/>
			<td colspan="1">
				Result expected:
			</td>
			<td colspan="1">
				<xsl:value-of select="result/@expected"/>
			</td>
		</tr>
		<xsl:if test="string-length(result)>0">
			<tr>
				<td colspan="1"/>
				<td colspan="1">Result file:</td>
				<td colspan="1">
					<xsl:element name="a">
						<xsl:attribute name="href"><xsl:value-of select="../@outpath"/>/<xsl:value-of select="result"/></xsl:attribute>
						<xsl:value-of select="result"/>
					</xsl:element>
				</td>
			</tr>
		</xsl:if>
		<tr>
			<td colspan="3"><hr style="height:1pt;color:black" /></td>
		</tr>
	</xsl:template>
	<xsl:template match="xsd|linkbase|xml|instance|schema">
		<tr>
			<td/>
			<td>
				<xsl:if test="@readMeFirst = 'true'">*</xsl:if>
				<xsl:choose>
					<xsl:when test="name()='schema'">Schema</xsl:when>
					<xsl:when test="name()='xsd'">Schema</xsl:when>
					<xsl:when test="name()='linkbase'">Linkbase</xsl:when>
					<xsl:when test="name()='xml'">Instance</xsl:when>
					<xsl:when test="name()='instance'">Instance</xsl:when>
					<xsl:otherwise>*Other</xsl:otherwise>
				</xsl:choose>:</td>
			<td>
				<xsl:element name="a">
					<xsl:attribute name="href"><xsl:value-of select="."/></xsl:attribute>
					<xsl:value-of select="."/>
				</xsl:element>
			</td>
		</tr>
	</xsl:template>
	<xsl:template match="node()"/>
</xsl:stylesheet>
