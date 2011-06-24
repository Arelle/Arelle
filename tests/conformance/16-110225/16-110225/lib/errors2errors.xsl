<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:output method="html" doctype-public="-//W3C//DTD HTML 4.0 Transitional//EN" encoding="UTF-8" omit-xml-declaration="yes"/>
  <xsl:template match="/errs">
    <!-- width of 652 is hard wired into SEC web site -->
    <xsl:variable name="width">652</xsl:variable>
    <xsl:variable name="left">200</xsl:variable>
    <xsl:variable name="right">50</xsl:variable>
    <xsl:variable name="middle" select="number($width) - number($left) - number($right)"/>
    <!-- for some bizarre reason these properties are not inherited from body to table. -->
    <xsl:variable name="size">font-size: 9pt;</xsl:variable>
    <xsl:variable name="family">font-family: Verdana, Arial, Helvetica;</xsl:variable>
    <HTML lang="ENG">
      <HEAD>
        <TITLE>EDGAR XBRL Validation Errors</TITLE>
      </HEAD>
      <body style="topmargin: 0; leftmargin: 0; marginwidth: 0; marginheight: 0;">
        <h2>EDGAR XBRL Validation Errors</h2>
        <table width="{$width}" border="1" cellspacing="0" cellpadding="0" bgcolor="white" style="border-bottom: 0; {$family} {$size}">
          <tr align="center">
            <td width="{$left}">
              <strong>Message ID</strong>
            </td>
            <td width="{$middle}">
              <strong>Message</strong>
            </td>
            <td width="{$right}">
              <strong>Subsection</strong>
            </td>
          </tr>
        </table>
        <xsl:for-each select="err">
          <!-- anchors only work at top level, hence the strange structure of this page. -->
          <a name="{name}" id="{name}"/>
          <table width="{$width}" border="1" cellspacing="0" cellpadding="0" bgcolor="white" style="border-bottom: 0; {$family} {$size}">
            <tr align="left" valign="top">
              <td width="{$left}">
                <xsl:value-of select="name"/>
              </td>
              <td width="{$middle}">
                <xsl:copy-of select="text/node()"/>
              </td>
              <td width="{$right}" align="center">
                <xsl:value-of select="num"/>
              </td>
            </tr>
          </table>
        </xsl:for-each>
      </body>
    </HTML>
  </xsl:template>
</xsl:stylesheet>
