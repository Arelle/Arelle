<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:output encoding="UTF-8" indent="yes" method="html"/>
  <xsl:variable name="comments">false</xsl:variable>
  <xsl:template match="*[local-name()='testcases']">
    <html>
      <head>
        <title>
          <xsl:value-of select="@name"/>
        </title>
      </head>
      <body>
        <table style="border:0; empty-cells:show;">
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
              <td colspan="2"> </td>
            </tr>
            <tr>
              <th>Name</th>
              <th>Variations</th>
              <th>Error Codes</th>
              <th>Remarks</th>
            </tr>
            <!-- now just generate one row per test set -->
            <xsl:apply-templates select="*"/>
          </tbody>
        </table>
      </body>
    </html>
  </xsl:template>
  <xsl:template match="*[local-name()='testcase']">
    <xsl:variable name="uri" select="@uri"/>
    <xsl:variable name="doc" select="document($uri)"/>
    <xsl:variable name="variations" select="count($doc/*[local-name()='testcase']/*[local-name()='variation'])"/>
    <xsl:variable name="names" select="$doc//*[local-name()='assert']/@name"/>
    <xsl:variable name="last" select="count($names)"/>
    <xsl:if test="count($doc/*[local-name()='testcase']) &gt; 0">
      <tr>
        <td nowrap="nowrap" valign="top">
          <xsl:element name="a">
            <xsl:attribute name="href">
              <xsl:value-of select="@uri"/>
            </xsl:attribute>
            <xsl:value-of select="$doc/*[local-name()='testcase']/*[local-name()='name']"/>
          </xsl:element>
        </td>
        <td align="center" valign="top">
          <xsl:value-of select="$variations"/>
        </td>
        <td nowrap="nowrap" valign="top">
          <xsl:for-each select="$names">
            <xsl:variable name="here" select="position()"/>
            <xsl:if test="$comments='true'">
              <xsl:comment>
                <xsl:value-of select="$here"/>
                <xsl:value-of select="."/>
              </xsl:comment>
            </xsl:if>
            <xsl:choose>
              <xsl:when test="$here=$last">
                <xsl:value-of select="$names[$here]"/>
              </xsl:when>
              <xsl:when test="string(.)=string($names[$here+1])"/>
              <xsl:otherwise>
                <xsl:value-of select="$names[$here]"/>
                <br/>
              </xsl:otherwise>
            </xsl:choose>
          </xsl:for-each>
        </td>
        <td valign="top">
          <xsl:apply-templates
            select="$doc/*[local-name()='testcase']/*[local-name()='description']//*[starts-with(.,'REMARK:')]"/>
        </td>
      </tr>
    </xsl:if>
  </xsl:template>
  <xsl:template match="*">
    <xsl:element name="{local-name()}">
      <xsl:apply-templates select="@*|node()"/>
    </xsl:element>
  </xsl:template>
  <xsl:template match="@*">
    <xsl:copy>
      <xsl:apply-templates select="@*|node()"/>
    </xsl:copy>
  </xsl:template>
  <xsl:template match="text()">
    <xsl:copy/>
  </xsl:template>
</xsl:stylesheet>
