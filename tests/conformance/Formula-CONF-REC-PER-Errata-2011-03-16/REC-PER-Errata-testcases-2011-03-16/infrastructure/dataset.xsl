<?xml version="1.0" encoding="UTF-8"?>
<!-- Copyright 2007 XBRL International. All Rights Reserved. -->
<xsl:stylesheet version="1.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:d="http://xbrl.org/2005/dataset">
  
  <xsl:template match="d:dataset">
    <html>
      <head>
        <title>
          <xsl:value-of select="@name" />
        </title>
      </head>
      <body>
        <table border="0">
          <tbody>
            <tr>
              <th colspan="3" align="left">
                Dataset: 
                <xsl:value-of select="@name" />
              </th>
            </tr>
            <tr>
              <td colspan="3">
                <xsl:value-of select="@description" />
              </td>
            </tr>
            <tr>
              <td colspan="3">
                Current Owner:
                <a>
                  <xsl:attribute name="href">
                    mailto:
                    <xsl:value-of select="@owner" />
                  </xsl:attribute>
                  <xsl:value-of select="@owner" />
                </a>
              </td>
            </tr>
            <tr>
              <td colspan="3">
                <hr style="height:3pt;color:black" />
              </td>
            </tr>
            <xsl:choose>
              <xsl:when test="string-length(@ignoreIf)>0">
                <tr>
                  <td colspan="3">
                    This example is ignored if
                    <i>
                      <xsl:value-of select="@ignoreIf" />
                    </i>
                    is required by the XBRL processor being tested.
                  </td>
                </tr>
              </xsl:when>
            </xsl:choose>
            <xsl:apply-templates select="d:variation" />
          </tbody>
        </table>
      </body>
    </html>
  </xsl:template>
  
  <xsl:template match="d:variation">
    <tr>
      <td colspan="1" />
      <td colspan="2">
        <table>
          <tbody>
            <tr>
              <th align="left">
                <xsl:value-of select="@name" />
              </th>
            </tr>
            <tr>
              <td>
                <xsl:value-of select="d:description" />
              </td>
            </tr>
          </tbody>
        </table>
      </td>
    </tr>
    <xsl:apply-templates select="d:data/*" />
  </xsl:template>
  <xsl:template
    match="d:xsd|d:linkbase|d:xml|d:instance|d:schema">
    <tr>
      <td />
      <td>
        <xsl:choose>
          <xsl:when test="name()='schema'">Schema</xsl:when>
          <xsl:when test="name()='xsd'">Schema</xsl:when>
          <xsl:when test="name()='linkbase'">Linkbase</xsl:when>
          <xsl:when test="name()='xml'">Instance</xsl:when>
          <xsl:when test="name()='instance'">Instance</xsl:when>
          <xsl:otherwise>*Other</xsl:otherwise>
        </xsl:choose>
        :
      </td>
      <td>
        <xsl:element name="a">
          <xsl:attribute name="href">
            <xsl:value-of select="." />
          </xsl:attribute>
          <xsl:value-of select="." />
        </xsl:element>
      </td>
    </tr>
  </xsl:template>
</xsl:stylesheet>
