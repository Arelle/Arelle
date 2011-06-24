target="../index.xml"
specificationsDocument="specifications.xml"
stylesheet="makeConformanceMap.xsl"
output="conformanceMap.xml"
echo "----------------------------------------------------------"
java -jar ../specifications/xbrlspec/saxon8.jar -o ${output} ${target} ${stylesheet} specificationsDocument=${specificationsDocument}
echo "----------------------------------------------------------"


