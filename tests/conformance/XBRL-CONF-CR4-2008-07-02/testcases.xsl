<!-- edited with XMLSPY v5 rel. 4 U (http://www.xmlspy.com) by Walter Hamscher (Standard Advantage) -->
<!-- XBRL 2.1 Tests -->
<!-- Copyright 2003 XBRL International. All Rights Reserved. -->
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:fo="http://www.w3.org/1999/XSL/Format" exclude-result-prefixes="fo">
	<xsl:template match="testcases">
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
							<td colspan="3">
								<xsl:value-of select="@name"/>
							</td>
							<td colspan="3">
								<xsl:value-of select="@date"/>
							</td>
						</tr>
						<tr>
							<td colspan="2">

							</td>
						</tr>
						<tr>
							<th>Full</th><th>#</th><th>Name</th><th>Owner</th><th>Description</th>
						</tr>
						<!-- now just generate one row per test set -->
						<xsl:apply-templates select="node()"/>
					</tbody>
				</table>
			</body>
		</html>
	</xsl:template>
	<xsl:template match="testcase">
		<xsl:variable name="uri" select="@uri"/>
		<tr>
			<td>
				<xsl:if test="document($uri)/testcase/@minimal='false'">*</xsl:if>
			</td>
			<td align="right">
				<xsl:variable name="variations" select="count(document($uri)/testcase/variation)"/>
				<xsl:value-of select="$variations"/>
			</td>
			<td>
				<xsl:element name="a">
					<xsl:attribute name="href"><xsl:value-of select="@uri"/></xsl:attribute>
					<xsl:value-of select="document($uri)/testcase/@name"/>
				</xsl:element>
			</td>
			<td>
				<xsl:element name="a">
					<xsl:variable name="owner" select="document($uri)/testcase/@owner"/>
					<xsl:attribute name="href">mailto:<xsl:value-of select="$owner"/></xsl:attribute>
					<xsl:value-of select="$owner"/>
				</xsl:element>
			</td>
			<td>
				<xsl:variable name="description" select="document($uri)/testcase/@description"/>
				<xsl:value-of select="$description"/>
			</td>
		</tr>
	</xsl:template>
	<xsl:template match="node()"/>
</xsl:stylesheet>
