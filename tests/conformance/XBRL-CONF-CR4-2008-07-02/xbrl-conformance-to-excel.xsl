<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" 
	xmlns:cm="http://www.xbrl.org/2003/conformance/management"
 	xmlns:o="urn:schemas-microsoft-com:office:office" 
 	xmlns:x="urn:schemas-microsoft-com:office:excel" 
 	xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet" 
 	xmlns:html="http://www.w3.org/TR/REC-html40"	
 	xmlns:xsl="http://www.w3.org/1999/XSL/Transform" 
>
	<xsl:output method="xml" version="1.0" encoding="UTF-8" indent="yes"/>
 	
 	<!-- ***************************************************************************** -->
 	<!-- Excel workbook prologue and epilogue. -->
 	<!-- ============================================================================= -->
 	<xsl:template match="/">
 		<xsl:processing-instruction name="mso-application">
 			<xsl:text>progid="Excel.Sheet"</xsl:text>
 		</xsl:processing-instruction> 
 		<ss:Workbook>
			<o:DocumentProperties>
				<o:Version>11.5703</o:Version>
			</o:DocumentProperties>
			<x:ExcelWorkbook>
				<x:ProtectStructure>False</x:ProtectStructure>
				<x:ProtectWindows>False</x:ProtectWindows>
			</x:ExcelWorkbook>
			<ss:Styles>
				<ss:Style ss:ID="Default" ss:Name="Normal">
					<ss:Alignment ss:Vertical="Bottom"/>
					<ss:Borders/>
					<ss:Font/>
					<ss:Interior/>
					<ss:NumberFormat/>
					<ss:Protection/>
				</ss:Style>
				<ss:Style ss:ID="s37" ss:Name="Heading">
					<ss:Borders/>
					<ss:Font x:Family="Swiss" ss:Bold="1"/>
					<ss:Interior/>
					<ss:NumberFormat/>
					<ss:Protection/>
				</ss:Style>
				<ss:Style ss:ID="s21" ss:Name="Sub-Group">
					<ss:Alignment ss:Horizontal="Left" ss:Vertical="Bottom" ss:Indent="1"/>
					<ss:Borders/>
					<ss:Font x:Family="Swiss"/>
					<ss:Interior/>
					<ss:NumberFormat/>
					<ss:Protection/>
				</ss:Style>
				<ss:Style ss:ID="s22" ss:Name="Test Variation">
					<ss:Alignment ss:Horizontal="Left" ss:Vertical="Bottom" ss:Indent="2"/>
					<ss:Borders/>
					<ss:Font x:Family="Swiss"/>
					<ss:Interior/>
					<ss:NumberFormat/>
					<ss:Protection/>
				</ss:Style>
				<ss:Style ss:ID="s27">
					<ss:Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
				</ss:Style>
				<ss:Style ss:ID="s31">
					<ss:Alignment ss:Vertical="Bottom"/>
					<ss:Font x:Family="Swiss"/>
				</ss:Style>
				<ss:Style ss:ID="s32" ss:Parent="s21">
					<ss:Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
					<ss:Font x:Family="Swiss"/>
				</ss:Style>
				<ss:Style ss:ID="s33" ss:Parent="s22">
					<ss:Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
					<ss:Font x:Family="Swiss"/>
				</ss:Style>
				<ss:Style ss:ID="s38" ss:Parent="s37">
					<ss:Alignment ss:Vertical="Bottom"/>
				</ss:Style>
				<ss:Style ss:ID="s39" ss:Parent="s37">
					<ss:Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
				</ss:Style>
				<ss:Style ss:ID="s43" ss:Parent="s37">
					<ss:Alignment ss:Vertical="Bottom"/>
					<ss:Font x:Family="Swiss" ss:Bold="1"/>
				</ss:Style>
			</ss:Styles>
			
			<!-- Count the number of voting contributors -->
			<xsl:variable name="voter-count" select="count(/cm:conformance/cm:contributors/cm:contributor[@voting='true'])"/>
			
			<!-- Construct a worksheet for each voting contributor -->
			<xsl:apply-templates select="/cm:conformance/cm:contributors/cm:contributor"/>
			
			<!-- Construct the summary worksheet prologue -->

			<ss:Worksheet ss:Name="Summary">
				<ss:Table x:FullColumns="1" x:FullRows="1">
					<ss:Column ss:AutoFitWidth="0" ss:Width="65"/>
					<ss:Column ss:AutoFitWidth="0" ss:Width="350"/>
					<ss:Column ss:AutoFitWidth="0" ss:Width="120"/>
					<ss:Column ss:AutoFitWidth="0" ss:Width="80"/>
					<ss:Column ss:AutoFitWidth="0">
						<xsl:attribute name="ss:Width"><xsl:value-of select="80"/></xsl:attribute>
						<xsl:attribute name="ss:Span"><xsl:value-of select="$voter-count + 1"/></xsl:attribute>
					</ss:Column>

					
					<!-- Construct a subsection for each testcase entry -->

					<xsl:apply-templates select="/cm:conformance/cm:testcases/cm:testcase" mode="summary">
						<xsl:with-param name="voter-count" select="$voter-count"/>
					</xsl:apply-templates>

					
				<!-- Construct the summary worksheet epilogue -->

				</ss:Table>
				<x:WorksheetOptions>
					<x:Selected/>
					<x:ProtectObjects>False</x:ProtectObjects>
					<x:ProtectScenarios>False</x:ProtectScenarios>
				</x:WorksheetOptions>
				<x:ConditionalFormatting>
					<x:Range>C<xsl:value-of select="5 + $voter-count"/></x:Range>
					<x:Condition>
						<x:Qualifier>Equal</x:Qualifier>
						<x:Value1>&quot;Rejected&quot;</x:Value1>
						<x:Format Style="color:red"/>
					</x:Condition>
				</x:ConditionalFormatting>
				<x:ConditionalFormatting>
					<x:Range>C4</x:Range>
					<x:Condition>
						<x:Qualifier>Equal</x:Qualifier>
						<x:Value1>&quot;Yes&quot;</x:Value1>
						<x:Format Style="color:#339966"/>
					</x:Condition>
					<x:Condition>
						<x:Qualifier>Equal</x:Qualifier>
						<x:Value1>&quot;No&quot;</x:Value1>
						<x:Format Style="color:red"/>
					</x:Condition>
				</x:ConditionalFormatting>
				<x:ConditionalFormatting>
					<x:Range>C5:C<xsl:value-of select="4 + $voter-count"/></x:Range>
					<x:Condition>
						<x:Qualifier>Equal</x:Qualifier>
						<x:Value1>&quot;Approved&quot;</x:Value1>
						<x:Format Style="color:#339966"/>
					</x:Condition>
					<x:Condition>
						<x:Qualifier>Equal</x:Qualifier>
						<x:Value1>&quot;Rejected&quot;</x:Value1>
						<x:Format Style="color:red"/>
					</x:Condition>
					<x:Condition>
						<x:Value1>AND(RC=&quot;Approved&quot;,(RC=&quot;Approved&quot;)&lt;&gt;(RC4=&quot;Yes&quot;))</x:Value1>
						<x:Format Style="color:red;font-weight:700;text-underline-style:single"/>
					</x:Condition>
				</x:ConditionalFormatting>
				
			</ss:Worksheet>
			
		</ss:Workbook>

 	</xsl:template>
 	
 	<!-- ***************************************************************************** -->
 	<!-- Excel detail worksheet generation -->
 	<!-- ============================================================================= -->
 	<xsl:template match="/cm:conformance/cm:contributors/cm:contributor[@voting='true']">
 	
	 	<ss:Worksheet>
	 		<xsl:attribute name="ss:Name"><xsl:value-of select="cm:identifier"/></xsl:attribute>
			<ss:Table x:FullColumns="1" x:FullRows="1">
				<ss:Column ss:StyleID="s38" ss:AutoFitWidth="0" ss:Width="65"/>
				<ss:Column ss:StyleID="s31" ss:AutoFitWidth="0" ss:Width="350"/>
				<ss:Column ss:StyleID="s31" ss:AutoFitWidth="0" ss:Width="50"/>
				<ss:Column ss:StyleID="s31" ss:AutoFitWidth="0" ss:Width="120"/>
				<ss:Column ss:StyleID="s27" ss:Width="80"/>
				<ss:Column ss:StyleID="s27" ss:Width="80"/>
				<ss:Column ss:AutoFitWidth="0" ss:Width="375"/>
				
				<!-- Contributor identification row -->
				<ss:Row>
					<ss:Cell ss:StyleID="s43">
						<ss:Data ss:Type="String">Contributor:</ss:Data>
					</ss:Cell>
					<ss:Cell>
						<ss:Data ss:Type="String"><xsl:value-of select="cm:identifier"/></ss:Data>
					</ss:Cell>
				</ss:Row>
				
				<!-- Contributor contact name row -->
				<ss:Row>
					<ss:Cell>
						<ss:Data ss:Type="String">Contact:</ss:Data>
					</ss:Cell>
					<ss:Cell>
						<ss:Data ss:Type="String"><xsl:value-of select="cm:contact/cm:name"/></ss:Data>
					</ss:Cell>
				</ss:Row>
				
				<!-- Contributor contact e-mail row -->
				<ss:Row>
					<ss:Cell>
						<ss:Data ss:Type="String">E-Mail:</ss:Data>
					</ss:Cell>
					<ss:Cell>
						<ss:Data ss:Type="String"><xsl:value-of select="cm:contact/cm:e-mail"/></ss:Data>
					</ss:Cell>
				</ss:Row>
				
				<!-- Construct a subsection for each testcase entry -->
				<xsl:apply-templates select="/cm:conformance/cm:testcases">
					<xsl:with-param name="voter-id" select="@id"/>
				</xsl:apply-templates>
				
			</ss:Table>
			<x:WorksheetOptions>
				<x:NoSummaryRowsBelowDetail/>
				<x:ProtectObjects>False</x:ProtectObjects>
				<x:ProtectScenarios>False</x:ProtectScenarios>
			</x:WorksheetOptions>
			<x:ConditionalFormatting>
				<x:Range>C5</x:Range>
				<x:Condition>
					<x:Qualifier>Equal</x:Qualifier>
					<x:Value1>&quot;Yes&quot;</x:Value1>
					<x:Format Style="color:#339966"/>
				</x:Condition>
				<x:Condition>
					<x:Qualifier>Equal</x:Qualifier>
					<x:Value1>&quot;No&quot;</x:Value1>
					<x:Format Style="color:red"/>
				</x:Condition>
			</x:ConditionalFormatting>
			<x:ConditionalFormatting>
				<x:Range>C6</x:Range>
				<x:Condition>
					<x:Qualifier>Equal</x:Qualifier>
					<x:Value1>&quot;Yes&quot;</x:Value1>
					<x:Format Style="color:#339966"/>
				</x:Condition>
				<x:Condition>
					<x:Qualifier>Equal</x:Qualifier>
					<x:Value1>&quot;No&quot;</x:Value1>
					<x:Format Style="color:red"/>
				</x:Condition>
				<x:Condition>
					<x:Value1>AND(RC=&quot;Yes&quot;,RC&lt;&gt;RC[-1])</x:Value1>
					<x:Format Style="color:red;font-weight:700;text-underline-style:single"/>
				</x:Condition>
			</x:ConditionalFormatting>		
			
		</ss:Worksheet>

 	</xsl:template>
 	
 	<!-- ***************************************************************************** -->
 	<!-- Excel detail worksheet subsection generation -->
 	<!-- ============================================================================= -->
 	<xsl:template match="/cm:conformance/cm:testcases">
 		<xsl:param name="voter-id"/>
 	
 		<!-- Get the id of the manager, if there is one -->
 		<xsl:variable name="id" select="cm:manager/@contributorRef"/>
 		
 		<!-- Look up the actual manager -->
 		<xsl:variable name="manager">
 			<xsl:if test="$id != ''">
 				<xsl:value-of select="/cm:conformance/cm:contributors/cm:contributor[@id = $id]/cm:identifier"/>
 			</xsl:if>
 		</xsl:variable>
 	
 		<!-- Construct a subsection for each testcase entry, inheriting the manager from this level -->
 		<xsl:apply-templates select="cm:testcase">
 			<xsl:with-param name="voter-id" select="$voter-id"/>
 			<xsl:with-param name="manager-default" select="$manager"/>
 		</xsl:apply-templates>
 	
 	</xsl:template>
 	
 	<!-- ============================================================================= -->
 	<xsl:template match="/cm:conformance/cm:testcases/cm:testcase">
 		<xsl:param name="voter-id"/>
 		<xsl:param name="manager-default"/>
 	
 		<!-- Get the id of the manager, if there is one -->
 		<xsl:variable name="id" select="cm:manager/@contributorRef"/>
 		
 		<!-- Look up the actual manager -->
 		<xsl:variable name="manager">
 			<xsl:choose>
				<xsl:when test="$id != ''">
	 				<xsl:value-of select="/cm:conformance/cm:contributors/cm:contributor[@id = $id]/cm:identifier"/>
				</xsl:when>
				<xsl:otherwise>
					<xsl:value-of select="$manager-default"/>
				</xsl:otherwise>
			</xsl:choose>
 		</xsl:variable>
 	
 		<!-- Separate subsections with a blank row -->
 		<ss:Row/>
 		
 		<!-- The row of column headings -->
		<ss:Row ss:StyleID="s37">
			<ss:Cell ss:StyleID="s38"/>
			<ss:Cell ss:StyleID="s38">
				<ss:Data ss:Type="String">Name</ss:Data>
			</ss:Cell>
			<ss:Cell ss:StyleID="s38">
				<ss:Data ss:Type="String">ID</ss:Data>
			</ss:Cell>
			<ss:Cell ss:StyleID="s43">
				<ss:Data ss:Type="String">Manager</ss:Data>
			</ss:Cell>
			<ss:Cell ss:StyleID="s38">
				<ss:Data ss:Type="String">Stable</ss:Data>
			</ss:Cell>
			<ss:Cell ss:StyleID="s39">
				<ss:Data ss:Type="String">Approved</ss:Data>
			</ss:Cell>
			<ss:Cell>
				<ss:Data ss:Type="String">Comments</ss:Data>
			</ss:Cell>
		</ss:Row>
		
		<!-- The testcase summary row -->
		<ss:Row>
			<ss:Cell ss:StyleID="s39">
				<ss:Data ss:Type="String">Test Case</ss:Data>
			</ss:Cell>
			<ss:Cell ss:StyleID="s32">
				<ss:Data ss:Type="String"><xsl:value-of select="@uri"/></ss:Data>
			</ss:Cell>
			<ss:Cell ss:StyleID="s32"/>
			<ss:Cell ss:StyleID="s32">
				<ss:Data ss:Type="String"><xsl:value-of select="$manager"/></ss:Data>
			</ss:Cell>
		</ss:Row>

 		<!-- Generate a row for each testcase variation -->
 		<xsl:apply-templates select="cm:variation">
 			<xsl:with-param name="voter-id" select="$voter-id"/>
 			<xsl:with-param name="manager-default" select="$manager"/>
 			<xsl:with-param name="uri" select="@uri"/>
 		</xsl:apply-templates>
 	
 	</xsl:template>	

 	<!-- ============================================================================= -->
 	<xsl:template match="/cm:conformance/cm:testcases/cm:testcase/cm:variation">
 		<xsl:param name="voter-id"/>
 		<xsl:param name="manager-default"/>
 		<xsl:param name="uri"/>
 	
 		<!-- Get the id of the manager, if there is one -->
 		<xsl:variable name="id" select="cm:manager/@contributorRef"/>
 		
 		<!-- Look up the actual manager -->
 		<xsl:variable name="manager">
 			<xsl:choose>
				<xsl:when test="$id != ''">
	 				<xsl:value-of select="/cm:conformance/cm:contributors/cm:contributor[@id = $id]/cm:identifier"/>
				</xsl:when>
				<xsl:otherwise>
					<xsl:value-of select="$manager-default"/>
				</xsl:otherwise>
			</xsl:choose>
 		</xsl:variable>
 		
 		<!-- This variable is used to establish the base URI of the source document -->
 		<xsl:variable name="base" select="/"/>
 		
 		<xsl:variable name="locator" select="@locator"/>
 	
	 	<!-- Generate the row for this variation -->
		<ss:Row>
			<ss:Cell ss:StyleID="s39">
				<ss:Data ss:Type="String">Variation</ss:Data>
			</ss:Cell>
			<ss:Cell ss:StyleID="s33">
				<ss:Data ss:Type="String"><xsl:for-each select="document($uri, $base)"><xsl:value-of select=".//variation[@id = $locator]/@name"/></xsl:for-each></ss:Data>
			</ss:Cell>
			<ss:Cell ss:StyleID="s33">
				<ss:Data ss:Type="String"><xsl:value-of select="$locator"/></ss:Data>
			</ss:Cell>
			<ss:Cell ss:StyleID="s33">
				<ss:Data ss:Type="String"><xsl:value-of select="$manager"/></ss:Data>
			</ss:Cell>
			<ss:Cell ss:StyleID="s33">
				<ss:Data ss:Type="String">
					<xsl:choose>
						<xsl:when test="@stable = 'false'">No</xsl:when>
						<xsl:when test="@stable = 'true'">Yes</xsl:when>
						<xsl:otherwise>Undefined</xsl:otherwise>
					</xsl:choose>
				</ss:Data>
			</ss:Cell>
			<ss:Cell ss:StyleID="s33">
				<ss:Data ss:Type="String">
					<xsl:choose>
						<xsl:when test="cm:status[@contributorRef = $voter-id]/@approved = 'false'">No</xsl:when>
						<xsl:when test="cm:status[@contributorRef = $voter-id]/@approved = 'true'">Yes</xsl:when>
						<xsl:otherwise>Undefined</xsl:otherwise>
					</xsl:choose>
				</ss:Data>
			</ss:Cell>
			<ss:Cell ss:StyleID="s27">
				<ss:Data ss:Type="String"><xsl:value-of select="cm:status[@contributorRef = $voter-id]"/></ss:Data>
			</ss:Cell>
		</ss:Row>
 	
 	</xsl:template>
 	
 	<!-- ***************************************************************************** -->
 	<!-- Excel summary worksheet subsection generation -->
 	<!-- ============================================================================= -->
 	<xsl:template match="/cm:conformance/cm:testcases/cm:testcase" mode="summary">
 		<xsl:param name="voter-count"/>
					
		<!-- The row of headings for the subsection -->
		<ss:Row ss:StyleID="s37">
			<ss:Cell ss:StyleID="s38"/>
			<ss:Cell ss:StyleID="s38">
				<ss:Data ss:Type="String">Name</ss:Data>
			</ss:Cell>
			<ss:Cell ss:StyleID="s38">
				<ss:Data ss:Type="String">ID</ss:Data>
			</ss:Cell>
			<ss:Cell ss:StyleID="s38">
				<ss:Data ss:Type="String">Stable</ss:Data>
			</ss:Cell>
			<!-- Construct a column heading for each voting contributor -->
			<xsl:for-each select="/cm:conformance/cm:contributors/cm:contributor[@voting='true']">
				<ss:Cell ss:StyleID="s38">
					<ss:Data ss:Type="String"><xsl:value-of select="cm:identifier"/></ss:Data>
				</ss:Cell>
			</xsl:for-each>
		</ss:Row>
		
		<!-- The testcase summary row -->
		<ss:Row>
			<ss:Cell ss:StyleID="s39">
				<ss:Data ss:Type="String">Test Case</ss:Data>
			</ss:Cell>
			<ss:Cell ss:StyleID="s32">
				<ss:Data ss:Type="String"><xsl:value-of select="@uri"/></ss:Data>
			</ss:Cell>
		</ss:Row>

 		<!-- Generate a row for each testcase variation -->
 		<xsl:apply-templates select="cm:variation" mode="summary">
 			<xsl:with-param name="voter-count" select="$voter-count"/>
 			<xsl:with-param name="uri" select="@uri"/>
 		</xsl:apply-templates>
 	
 		<!-- Separate subsections with a blank row -->
 		<ss:Row/>
 		
 	</xsl:template>
 	
 	<!-- ============================================================================= -->
 	<xsl:template match="/cm:conformance/cm:testcases/cm:testcase/cm:variation" mode="summary">
 		<xsl:param name="voter-count"/>
 		<xsl:param name="uri"/>
 		
 		<!-- Save the current node -->
 		<xsl:variable name="variation-node" select="."/>
 	
 		<!-- This variable is used to establish the base URI of the source document -->
 		<xsl:variable name="base" select="/"/>
 		
 		<xsl:variable name="locator" select="@locator"/>
 	
	 	<!-- Generate the row for this variation -->
		<ss:Row>
			<ss:Cell ss:StyleID="s39">
				<ss:Data ss:Type="String">Variation</ss:Data>
			</ss:Cell>
			<ss:Cell ss:StyleID="s33">
				<ss:Data ss:Type="String"><xsl:for-each select="document($uri, $base)"><xsl:value-of select=".//variation[@id = $locator]/@name"/></xsl:for-each></ss:Data>
			</ss:Cell>
			<ss:Cell ss:StyleID="s33">
				<ss:Data ss:Type="String"><xsl:value-of select="$locator"/></ss:Data>
			</ss:Cell>
			<ss:Cell ss:StyleID="s33">
				<ss:Data ss:Type="String">
					<xsl:choose>
						<xsl:when test="@stable = 'false'">No</xsl:when>
						<xsl:when test="@stable = 'true'">Yes</xsl:when>
						<xsl:otherwise>Undefined</xsl:otherwise>
					</xsl:choose>
				</ss:Data>
			</ss:Cell>
			
			<!-- Construct a cell for each voting contributor -->
			<xsl:for-each select="/cm:conformance/cm:contributors/cm:contributor[@voting='true']">
				<xsl:variable name="voter-id" select="@id"/>
				<ss:Cell ss:StyleID="s33">
					<ss:Data ss:Type="String">
						<xsl:choose>
							<xsl:when test="$variation-node/cm:status[@contributorRef = $voter-id]/@approved = 'false'">Rejected</xsl:when>
							<xsl:when test="$variation-node/cm:status[@contributorRef = $voter-id]/@approved = 'true'">Approved</xsl:when>
							<xsl:otherwise>Undefined</xsl:otherwise>
						</xsl:choose>
					</ss:Data>
				</ss:Cell>
			</xsl:for-each>
			
			<!-- Construct the computed summary cell -->
			<ss:Cell ss:StyleID="s33">
				<xsl:attribute name="ss:Formula">=IF(NOT(ISNA(MATCH(&quot;Rejected&quot;,RC[-<xsl:value-of select="$voter-count"/>]:RC[-1],0))),&quot;Rejected&quot;,&quot;&quot;)</xsl:attribute>
			</ss:Cell>			
			
		</ss:Row>
 	
 	</xsl:template>
 	
</xsl:stylesheet>
