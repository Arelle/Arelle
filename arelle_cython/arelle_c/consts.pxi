from arelle_c.xerces_uniDefs cimport chNull, chHTab, chLF, chVTab, chFF, chCR, chAmpersand, chAsterisk, chAt, chBackSlash, chBang, 	chCaret, chCloseAngle, chCloseCurly, chCloseParen, chCloseSquare, chColon, chComma, chDash, chDollarSign, chDoubleQuote, chEqual, 	chForwardSlash, chGrave, chNEL, chOpenAngle, chOpenCurly, chOpenParen, chOpenSquare, chPercent, chPeriod, chPipe, chPlus, 	chPound, chQuestion, chSingleQuote, chSpace, chSemiColon, chTilde, chUnderscore, chSwappedUnicodeMarker, chUnicodeMarker, 	chDigit_0, chDigit_1, chDigit_2, chDigit_3, chDigit_4, chDigit_5, chDigit_6, chDigit_7, chDigit_8, chDigit_9, 	chLatin_A, chLatin_B, chLatin_C, chLatin_D, chLatin_E, chLatin_F, chLatin_G, chLatin_H, chLatin_I, chLatin_J, chLatin_K, 	chLatin_L, chLatin_M, chLatin_N, chLatin_O, chLatin_P, chLatin_Q, chLatin_R, chLatin_S, chLatin_T, chLatin_U, chLatin_V, 	chLatin_W, chLatin_X, chLatin_Y, chLatin_Z, 	chLatin_a, chLatin_b, chLatin_c, chLatin_d, chLatin_e, chLatin_f, chLatin_g, chLatin_h, chLatin_i, chLatin_j, chLatin_k, 	chLatin_l, chLatin_m, chLatin_n, chLatin_o, chLatin_p, chLatin_q, chLatin_r, chLatin_s, chLatin_t, chLatin_u, chLatin_v, 	chLatin_w, chLatin_x, chLatin_y, chLatin_z, chYenSign, chWonSign, chLineSeparator, chParagraphSeparator
from arelle_c.xerces_util cimport XMLCh, XMLSize_t
from arelle_c.xerces_ctypes cimport int64_t, XMLFileLoc
from decimal import Decimal
from regex import compile as re_compile

# generate XMLCh constant strings and hashes
#    x"..." gets replaced with array of XMLCh character constants
#    h"..." gets replaced by python 64 bit hash code (c++ long long)

ctypedef int64_t  hash_t
cdef XMLCh[29] nsDtr
nsDtr[:] = [chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_w, chLatin_w, chLatin_w, chPeriod, chLatin_x, chLatin_b, chLatin_r, chLatin_l, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_2, chDigit_0, chDigit_0, chDigit_9, chForwardSlash, chLatin_d, chLatin_t, chLatin_r, chNull]
cdef XMLCh[37] nsDtrNumeric
nsDtrNumeric[:] = [chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_w, chLatin_w, chLatin_w, chPeriod, chLatin_x, chLatin_b, chLatin_r, chLatin_l, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chLatin_d, chLatin_t, chLatin_r, chForwardSlash, chLatin_t, chLatin_y, chLatin_p, chLatin_e, chForwardSlash, chLatin_n, chLatin_u, chLatin_m, chLatin_e, chLatin_r, chLatin_i, chLatin_c, chNull]
cdef XMLCh[45] nsDtrYMD
nsDtrYMD[:] = [chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_w, chLatin_w, chLatin_w, chPeriod, chLatin_x, chLatin_b, chLatin_r, chLatin_l, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chLatin_d, chLatin_t, chLatin_r, chForwardSlash, chLatin_t, chLatin_y, chLatin_p, chLatin_e, chForwardSlash, chLatin_W, chLatin_G, chLatin_W, chLatin_D, chForwardSlash, chLatin_Y, chLatin_Y, chLatin_Y, chLatin_Y, chDash, chLatin_M, chLatin_M, chDash, chLatin_D, chLatin_D, chNull]
cdef XMLCh[45] nsEnum2014
nsEnum2014[:] = [chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_x, chLatin_b, chLatin_r, chLatin_l, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_2, chDigit_0, chDigit_1, chDigit_4, chForwardSlash, chLatin_e, chLatin_x, chLatin_t, chLatin_e, chLatin_n, chLatin_s, chLatin_i, chLatin_b, chLatin_l, chLatin_e, chDash, chLatin_e, chLatin_n, chLatin_u, chLatin_m, chLatin_e, chLatin_r, chLatin_a, chLatin_t, chLatin_i, chLatin_o, chLatin_n, chLatin_s, chNull]
cdef XMLCh[59] nsEnum2016
nsEnum2016[:] = [chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_x, chLatin_b, chLatin_r, chLatin_l, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chLatin_P, chLatin_W, chLatin_D, chForwardSlash, chDigit_2, chDigit_0, chDigit_1, chDigit_6, chDash, chDigit_1, chDigit_0, chDash, chDigit_1, chDigit_2, chForwardSlash, chLatin_e, chLatin_x, chLatin_t, chLatin_e, chLatin_n, chLatin_s, chLatin_i, chLatin_b, chLatin_l, chLatin_e, chDash, chLatin_e, chLatin_n, chLatin_u, chLatin_m, chLatin_e, chLatin_r, chLatin_a, chLatin_t, chLatin_i, chLatin_o, chLatin_n, chLatin_s, chDash, chDigit_1, chPeriod, chDigit_1, chNull]
cdef XMLCh[60] nsEnum1YMD
nsEnum1YMD[:] = [chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_x, chLatin_b, chLatin_r, chLatin_l, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chLatin_W, chLatin_G, chLatin_W, chLatin_D, chForwardSlash, chLatin_Y, chLatin_Y, chLatin_Y, chLatin_Y, chDash, chLatin_M, chLatin_M, chDash, chLatin_D, chLatin_D, chForwardSlash, chLatin_e, chLatin_x, chLatin_t, chLatin_e, chLatin_n, chLatin_s, chLatin_i, chLatin_b, chLatin_l, chLatin_e, chDash, chLatin_e, chLatin_n, chLatin_u, chLatin_m, chLatin_e, chLatin_r, chLatin_a, chLatin_t, chLatin_i, chLatin_o, chLatin_n, chLatin_s, chDash, chDigit_1, chPeriod, chDigit_1, chNull]
cdef XMLCh[60] nsEnum2YMD
nsEnum2YMD[:] = [chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_x, chLatin_b, chLatin_r, chLatin_l, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chLatin_W, chLatin_G, chLatin_W, chLatin_D, chForwardSlash, chLatin_Y, chLatin_Y, chLatin_Y, chLatin_Y, chDash, chLatin_M, chLatin_M, chDash, chLatin_D, chLatin_D, chForwardSlash, chLatin_e, chLatin_x, chLatin_t, chLatin_e, chLatin_n, chLatin_s, chLatin_i, chLatin_b, chLatin_l, chLatin_e, chDash, chLatin_e, chLatin_n, chLatin_u, chLatin_m, chLatin_e, chLatin_r, chLatin_a, chLatin_t, chLatin_i, chLatin_o, chLatin_n, chLatin_s, chDash, chDigit_2, chPeriod, chDigit_0, chNull]
cdef XMLCh[36] nsIxbrl
nsIxbrl[:] = [chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_w, chLatin_w, chLatin_w, chPeriod, chLatin_x, chLatin_b, chLatin_r, chLatin_l, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_2, chDigit_0, chDigit_0, chDigit_8, chForwardSlash, chLatin_i, chLatin_n, chLatin_l, chLatin_i, chLatin_n, chLatin_e, chLatin_X, chLatin_B, chLatin_R, chLatin_L, chNull]
cdef XMLCh[36] nsIxbrl11
nsIxbrl11[:] = [chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_w, chLatin_w, chLatin_w, chPeriod, chLatin_x, chLatin_b, chLatin_r, chLatin_l, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_2, chDigit_0, chDigit_1, chDigit_3, chForwardSlash, chLatin_i, chLatin_n, chLatin_l, chLatin_i, chLatin_n, chLatin_e, chLatin_X, chLatin_B, chLatin_R, chLatin_L, chNull]
cdef XMLCh[34] nsLink
nsLink[:] = [chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_w, chLatin_w, chLatin_w, chPeriod, chLatin_x, chLatin_b, chLatin_r, chLatin_l, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_2, chDigit_0, chDigit_0, chDigit_3, chForwardSlash, chLatin_l, chLatin_i, chLatin_n, chLatin_k, chLatin_b, chLatin_a, chLatin_s, chLatin_e, chNull]
cdef XMLCh[1] nsNoNamespace
nsNoNamespace[:] = [chNull]
cdef XMLCh[1] nsNoPrefix
nsNoPrefix[:] = [chNull]
cdef XMLCh[30] nsRegistry
nsRegistry[:] = [chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_x, chLatin_b, chLatin_r, chLatin_l, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_2, chDigit_0, chDigit_0, chDigit_8, chForwardSlash, chLatin_r, chLatin_e, chLatin_g, chLatin_i, chLatin_s, chLatin_t, chLatin_r, chLatin_y, chNull]
cdef XMLCh[37] nsVer
nsVer[:] = [chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_x, chLatin_b, chLatin_r, chLatin_l, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_2, chDigit_0, chDigit_1, chDigit_3, chForwardSlash, chLatin_v, chLatin_e, chLatin_r, chLatin_s, chLatin_i, chLatin_o, chLatin_n, chLatin_i, chLatin_n, chLatin_g, chDash, chLatin_b, chLatin_a, chLatin_s, chLatin_e, chNull]
cdef XMLCh[28] nsXbrldi
nsXbrldi[:] = [chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_x, chLatin_b, chLatin_r, chLatin_l, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_2, chDigit_0, chDigit_0, chDigit_6, chForwardSlash, chLatin_x, chLatin_b, chLatin_r, chLatin_l, chLatin_d, chLatin_i, chNull]
cdef XMLCh[28] nsXbrldt
nsXbrldt[:] = [chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_x, chLatin_b, chLatin_r, chLatin_l, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_2, chDigit_0, chDigit_0, chDigit_5, chForwardSlash, chLatin_x, chLatin_b, chLatin_r, chLatin_l, chLatin_d, chLatin_t, chNull]
cdef XMLCh[34] nsXbrli
nsXbrli[:] = [chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_w, chLatin_w, chLatin_w, chPeriod, chLatin_x, chLatin_b, chLatin_r, chLatin_l, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_2, chDigit_0, chDigit_0, chDigit_3, chForwardSlash, chLatin_i, chLatin_n, chLatin_s, chLatin_t, chLatin_a, chLatin_n, chLatin_c, chLatin_e, chNull]
cdef XMLCh[29] nsXhtml
nsXhtml[:] = [chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_w, chLatin_w, chLatin_w, chPeriod, chLatin_w, chDigit_3, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_1, chDigit_9, chDigit_9, chDigit_9, chForwardSlash, chLatin_x, chLatin_h, chLatin_t, chLatin_m, chLatin_l, chNull]
cdef XMLCh[31] nsXl
nsXl[:] = [chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_w, chLatin_w, chLatin_w, chPeriod, chLatin_x, chLatin_b, chLatin_r, chLatin_l, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_2, chDigit_0, chDigit_0, chDigit_3, chForwardSlash, chLatin_X, chLatin_L, chLatin_i, chLatin_n, chLatin_k, chNull]
cdef XMLCh[29] nsXlink
nsXlink[:] = [chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_w, chLatin_w, chLatin_w, chPeriod, chLatin_w, chDigit_3, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_1, chDigit_9, chDigit_9, chDigit_9, chForwardSlash, chLatin_x, chLatin_l, chLatin_i, chLatin_n, chLatin_k, chNull]
cdef XMLCh[37] nsXml
nsXml[:] = [chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_w, chLatin_w, chLatin_w, chPeriod, chLatin_w, chDigit_3, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chLatin_X, chLatin_M, chLatin_L, chForwardSlash, chDigit_1, chDigit_9, chDigit_9, chDigit_8, chForwardSlash, chLatin_n, chLatin_a, chLatin_m, chLatin_e, chLatin_s, chLatin_p, chLatin_a, chLatin_c, chLatin_e, chNull]
cdef XMLCh[30] nsXmlns
nsXmlns[:] = [chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_w, chLatin_w, chLatin_w, chPeriod, chLatin_w, chDigit_3, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_2, chDigit_0, chDigit_0, chDigit_0, chForwardSlash, chLatin_x, chLatin_m, chLatin_l, chLatin_n, chLatin_s, chForwardSlash, chNull]
cdef XMLCh[33] nsXsd
nsXsd[:] = [chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_w, chLatin_w, chLatin_w, chPeriod, chLatin_w, chDigit_3, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_2, chDigit_0, chDigit_0, chDigit_1, chForwardSlash, chLatin_X, chLatin_M, chLatin_L, chLatin_S, chLatin_c, chLatin_h, chLatin_e, chLatin_m, chLatin_a, chNull]
cdef XMLSize_t lenNsXsd = stringLen(nsXsd)
cdef XMLCh[33] nsXsSyntheticAnnotation
nsXsSyntheticAnnotation[:] = [chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_a, chLatin_r, chLatin_e, chLatin_l, chLatin_l, chLatin_e, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_2, chDigit_0, chDigit_1, chDigit_8, chForwardSlash, chLatin_X, chLatin_s, chLatin_S, chLatin_y, chLatin_n, chLatin_A, chLatin_n, chLatin_o, chLatin_t, chNull]
cdef XMLCh[42] nsXsi
nsXsi[:] = [chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_w, chLatin_w, chLatin_w, chPeriod, chLatin_w, chDigit_3, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_2, chDigit_0, chDigit_0, chDigit_1, chForwardSlash, chLatin_X, chLatin_M, chLatin_L, chLatin_S, chLatin_c, chLatin_h, chLatin_e, chLatin_m, chLatin_a, chDash, chLatin_i, chLatin_n, chLatin_s, chLatin_t, chLatin_a, chLatin_n, chLatin_c, chLatin_e, chNull]

cdef XMLCh[3] prefixXsd
prefixXsd[:] = [chLatin_x, chLatin_s, chNull]

cdef XMLCh[8] lnActuate
lnActuate[:] = [chLatin_a, chLatin_c, chLatin_t, chLatin_u, chLatin_a, chLatin_t, chLatin_e, chNull]
cdef XMLCh[11] lnAnnotation
lnAnnotation[:] = [chLatin_a, chLatin_n, chLatin_n, chLatin_o, chLatin_t, chLatin_a, chLatin_t, chLatin_i, chLatin_o, chLatin_n, chNull]
cdef XMLCh[8] lnAppinfo
lnAppinfo[:] = [chLatin_a, chLatin_p, chLatin_p, chLatin_i, chLatin_n, chLatin_f, chLatin_o, chNull]
cdef XMLCh[4] lnArc
lnArc[:] = [chLatin_a, chLatin_r, chLatin_c, chNull]
cdef XMLCh[8] lnArcrole
lnArcrole[:] = [chLatin_a, chLatin_r, chLatin_c, chLatin_r, chLatin_o, chLatin_l, chLatin_e, chNull]
cdef XMLCh[11] lnArcroleRef
lnArcroleRef[:] = [chLatin_a, chLatin_r, chLatin_c, chLatin_r, chLatin_o, chLatin_l, chLatin_e, chLatin_R, chLatin_e, chLatin_f, chNull]
cdef XMLCh[12] lnArcroleType
lnArcroleType[:] = [chLatin_a, chLatin_r, chLatin_c, chLatin_r, chLatin_o, chLatin_l, chLatin_e, chLatin_T, chLatin_y, chLatin_p, chLatin_e, chNull]
cdef XMLCh[11] lnArcroleURI
lnArcroleURI[:] = [chLatin_a, chLatin_r, chLatin_c, chLatin_r, chLatin_o, chLatin_l, chLatin_e, chLatin_U, chLatin_R, chLatin_I, chNull]
cdef XMLCh[5] lnArea
lnArea[:] = [chLatin_a, chLatin_r, chLatin_e, chLatin_a, chNull]
cdef XMLCh[8] lnBalance
lnBalance[:] = [chLatin_b, chLatin_a, chLatin_l, chLatin_a, chLatin_n, chLatin_c, chLatin_e, chNull]
cdef XMLCh[5] lnBase
lnBase[:] = [chLatin_b, chLatin_a, chLatin_s, chLatin_e, chNull]
cdef XMLCh[8] lnContext
lnContext[:] = [chLatin_c, chLatin_o, chLatin_n, chLatin_t, chLatin_e, chLatin_x, chLatin_t, chNull]
cdef XMLCh[11] lnContextRef
lnContextRef[:] = [chLatin_c, chLatin_o, chLatin_n, chLatin_t, chLatin_e, chLatin_x, chLatin_t, chLatin_R, chLatin_e, chLatin_f, chNull]
cdef XMLCh[14] lnCyclesAllowed
lnCyclesAllowed[:] = [chLatin_c, chLatin_y, chLatin_c, chLatin_l, chLatin_e, chLatin_s, chLatin_A, chLatin_l, chLatin_l, chLatin_o, chLatin_w, chLatin_e, chLatin_d, chNull]
cdef XMLCh[10] lnDateUnion
lnDateUnion[:] = [chLatin_d, chLatin_a, chLatin_t, chLatin_e, chLatin_U, chLatin_n, chLatin_i, chLatin_o, chLatin_n, chNull]
cdef XMLCh[9] lnDecimals
lnDecimals[:] = [chLatin_d, chLatin_e, chLatin_c, chLatin_i, chLatin_m, chLatin_a, chLatin_l, chLatin_s, chNull]
cdef XMLCh[11] lnDefinition
lnDefinition[:] = [chLatin_d, chLatin_e, chLatin_f, chLatin_i, chLatin_n, chLatin_i, chLatin_t, chLatin_i, chLatin_o, chLatin_n, chNull]
cdef XMLCh[10] lnDimension
lnDimension[:] = [chLatin_d, chLatin_i, chLatin_m, chLatin_e, chLatin_n, chLatin_s, chLatin_i, chLatin_o, chLatin_n, chNull]
cdef XMLCh[14] lnDimensionItem
lnDimensionItem[:] = [chLatin_d, chLatin_i, chLatin_m, chLatin_e, chLatin_n, chLatin_s, chLatin_i, chLatin_o, chLatin_n, chLatin_I, chLatin_t, chLatin_e, chLatin_m, chNull]
cdef XMLCh[14] lnDocumentation
lnDocumentation[:] = [chLatin_d, chLatin_o, chLatin_c, chLatin_u, chLatin_m, chLatin_e, chLatin_n, chLatin_t, chLatin_a, chLatin_t, chLatin_i, chLatin_o, chLatin_n, chNull]
cdef XMLCh[8] lnElement
lnElement[:] = [chLatin_e, chLatin_l, chLatin_e, chLatin_m, chLatin_e, chLatin_n, chLatin_t, chNull]
cdef XMLCh[8] lnEndDate
lnEndDate[:] = [chLatin_e, chLatin_n, chLatin_d, chLatin_D, chLatin_a, chLatin_t, chLatin_e, chNull]
cdef XMLCh[20] lnEnumerationItemType
lnEnumerationItemType[:] = [chLatin_e, chLatin_n, chLatin_u, chLatin_m, chLatin_e, chLatin_r, chLatin_a, chLatin_t, chLatin_i, chLatin_o, chLatin_n, chLatin_I, chLatin_t, chLatin_e, chLatin_m, chLatin_T, chLatin_y, chLatin_p, chLatin_e, chNull]
cdef XMLCh[21] lnEnumerationsItemType
lnEnumerationsItemType[:] = [chLatin_e, chLatin_n, chLatin_u, chLatin_m, chLatin_e, chLatin_r, chLatin_a, chLatin_t, chLatin_i, chLatin_o, chLatin_n, chLatin_s, chLatin_I, chLatin_t, chLatin_e, chLatin_m, chLatin_T, chLatin_y, chLatin_p, chLatin_e, chNull]
cdef XMLCh[24] lnEnumerationListItemType
lnEnumerationListItemType[:] = [chLatin_e, chLatin_n, chLatin_u, chLatin_m, chLatin_e, chLatin_r, chLatin_a, chLatin_t, chLatin_i, chLatin_o, chLatin_n, chLatin_L, chLatin_i, chLatin_s, chLatin_t, chLatin_I, chLatin_t, chLatin_e, chLatin_m, chLatin_T, chLatin_y, chLatin_p, chLatin_e, chNull]
cdef XMLCh[23] lnEnumerationSetItemType
lnEnumerationSetItemType[:] = [chLatin_e, chLatin_n, chLatin_u, chLatin_m, chLatin_e, chLatin_r, chLatin_a, chLatin_t, chLatin_i, chLatin_o, chLatin_n, chLatin_S, chLatin_e, chLatin_t, chLatin_I, chLatin_t, chLatin_e, chLatin_m, chLatin_T, chLatin_y, chLatin_p, chLatin_e, chNull]
cdef XMLCh[15] lnExplicitMember
lnExplicitMember[:] = [chLatin_e, chLatin_x, chLatin_p, chLatin_l, chLatin_i, chLatin_c, chLatin_i, chLatin_t, chLatin_M, chLatin_e, chLatin_m, chLatin_b, chLatin_e, chLatin_r, chNull]
cdef XMLCh[9] lnExtended
lnExtended[:] = [chLatin_e, chLatin_x, chLatin_t, chLatin_e, chLatin_n, chLatin_d, chLatin_e, chLatin_d, chNull]
cdef XMLCh[6] lnFacts
lnFacts[:] = [chLatin_f, chLatin_a, chLatin_c, chLatin_t, chLatin_s, chNull]
cdef XMLCh[5] lnFrom
lnFrom[:] = [chLatin_f, chLatin_r, chLatin_o, chLatin_m, chNull]
cdef XMLCh[5] lnHref
lnHref[:] = [chLatin_h, chLatin_r, chLatin_e, chLatin_f, chNull]
cdef XMLCh[5] lnHtml
lnHtml[:] = [chLatin_h, chLatin_t, chLatin_m, chLatin_l, chNull]
cdef XMLCh[14] lnHypercubeItem
lnHypercubeItem[:] = [chLatin_h, chLatin_y, chLatin_p, chLatin_e, chLatin_r, chLatin_c, chLatin_u, chLatin_b, chLatin_e, chLatin_I, chLatin_t, chLatin_e, chLatin_m, chNull]
cdef XMLCh[3] lnId
lnId[:] = [chLatin_i, chLatin_d, chNull]
cdef XMLCh[7] lnImport
lnImport[:] = [chLatin_i, chLatin_m, chLatin_p, chLatin_o, chLatin_r, chLatin_t, chNull]
cdef XMLCh[8] lnInclude
lnInclude[:] = [chLatin_i, chLatin_n, chLatin_c, chLatin_l, chLatin_u, chLatin_d, chLatin_e, chNull]
cdef XMLCh[8] lnInstant
lnInstant[:] = [chLatin_i, chLatin_n, chLatin_s, chLatin_t, chLatin_a, chLatin_n, chLatin_t, chNull]
cdef XMLCh[5] lnItem
lnItem[:] = [chLatin_i, chLatin_t, chLatin_e, chLatin_m, chNull]
cdef XMLCh[6] lnLabel
lnLabel[:] = [chLatin_l, chLatin_a, chLatin_b, chLatin_e, chLatin_l, chNull]
cdef XMLCh[5] lnLang
lnLang[:] = [chLatin_l, chLatin_a, chLatin_n, chLatin_g, chNull]
cdef XMLCh[9] lnLinkbase
lnLinkbase[:] = [chLatin_l, chLatin_i, chLatin_n, chLatin_k, chLatin_b, chLatin_a, chLatin_s, chLatin_e, chNull]
cdef XMLCh[12] lnLinkbaseRef
lnLinkbaseRef[:] = [chLatin_l, chLatin_i, chLatin_n, chLatin_k, chLatin_b, chLatin_a, chLatin_s, chLatin_e, chLatin_R, chLatin_e, chLatin_f, chNull]
cdef XMLCh[4] lnLoc
lnLoc[:] = [chLatin_l, chLatin_o, chLatin_c, chNull]
cdef XMLCh[8] lnLocator
lnLocator[:] = [chLatin_l, chLatin_o, chLatin_c, chLatin_a, chLatin_t, chLatin_o, chLatin_r, chNull]
cdef XMLCh[5] lnName
lnName[:] = [chLatin_n, chLatin_a, chLatin_m, chLatin_e, chNull]
cdef XMLCh[10] lnNamespace
lnNamespace[:] = [chLatin_n, chLatin_a, chLatin_m, chLatin_e, chLatin_s, chLatin_p, chLatin_a, chLatin_c, chLatin_e, chNull]
cdef XMLCh[4] lnNil
lnNil[:] = [chLatin_n, chLatin_i, chLatin_l, chNull]
cdef XMLCh[27] lnNoDecimalsMonetaryItemType
lnNoDecimalsMonetaryItemType[:] = [chLatin_n, chLatin_o, chLatin_D, chLatin_e, chLatin_c, chLatin_i, chLatin_m, chLatin_a, chLatin_l, chLatin_s, chLatin_M, chLatin_o, chLatin_n, chLatin_e, chLatin_t, chLatin_a, chLatin_r, chLatin_y, chLatin_I, chLatin_t, chLatin_e, chLatin_m, chLatin_T, chLatin_y, chLatin_p, chLatin_e, chNull]
cdef XMLCh[26] lnNoNamespaceSchemaLocation
lnNoNamespaceSchemaLocation[:] = [chLatin_n, chLatin_o, chLatin_N, chLatin_a, chLatin_m, chLatin_e, chLatin_s, chLatin_p, chLatin_a, chLatin_c, chLatin_e, chLatin_S, chLatin_c, chLatin_h, chLatin_e, chLatin_m, chLatin_a, chLatin_L, chLatin_o, chLatin_c, chLatin_a, chLatin_t, chLatin_i, chLatin_o, chLatin_n, chNull]
cdef XMLCh[38] lnNonNegativeNoDecimalsMonetaryItemType
lnNonNegativeNoDecimalsMonetaryItemType[:] = [chLatin_n, chLatin_o, chLatin_n, chLatin_N, chLatin_e, chLatin_g, chLatin_a, chLatin_t, chLatin_i, chLatin_v, chLatin_e, chLatin_N, chLatin_o, chLatin_D, chLatin_e, chLatin_c, chLatin_i, chLatin_m, chLatin_a, chLatin_l, chLatin_s, chLatin_M, chLatin_o, chLatin_n, chLatin_e, chLatin_t, chLatin_a, chLatin_r, chLatin_y, chLatin_I, chLatin_t, chLatin_e, chLatin_m, chLatin_T, chLatin_y, chLatin_p, chLatin_e, chNull]
cdef XMLCh[6] lnOrder
lnOrder[:] = [chLatin_o, chLatin_r, chLatin_d, chLatin_e, chLatin_r, chNull]
cdef XMLCh[5] lnPart
lnPart[:] = [chLatin_p, chLatin_a, chLatin_r, chLatin_t, chNull]
cdef XMLCh[11] lnPeriodType
lnPeriodType[:] = [chLatin_p, chLatin_e, chLatin_r, chLatin_i, chLatin_o, chLatin_d, chLatin_T, chLatin_y, chLatin_p, chLatin_e, chNull]
cdef XMLCh[10] lnPrecision
lnPrecision[:] = [chLatin_p, chLatin_r, chLatin_e, chLatin_c, chLatin_i, chLatin_s, chLatin_i, chLatin_o, chLatin_n, chNull]
cdef XMLCh[15] lnPreferredLabel
lnPreferredLabel[:] = [chLatin_p, chLatin_r, chLatin_e, chLatin_f, chLatin_e, chLatin_r, chLatin_r, chLatin_e, chLatin_d, chLatin_L, chLatin_a, chLatin_b, chLatin_e, chLatin_l, chNull]
cdef XMLCh[9] lnPriority
lnPriority[:] = [chLatin_p, chLatin_r, chLatin_i, chLatin_o, chLatin_r, chLatin_i, chLatin_t, chLatin_y, chNull]
cdef XMLCh[5] lnPtvl
lnPtvl[:] = [chLatin_p, chLatin_t, chLatin_v, chLatin_l, chNull]
cdef XMLCh[11] lnReferences
lnReferences[:] = [chLatin_r, chLatin_e, chLatin_f, chLatin_e, chLatin_r, chLatin_e, chLatin_n, chLatin_c, chLatin_e, chLatin_s, chNull]
cdef XMLCh[9] lnRegistry
lnRegistry[:] = [chLatin_r, chLatin_e, chLatin_g, chLatin_i, chLatin_s, chLatin_t, chLatin_r, chLatin_y, chNull]
cdef XMLCh[7] lnReport
lnReport[:] = [chLatin_r, chLatin_e, chLatin_p, chLatin_o, chLatin_r, chLatin_t, chNull]
cdef XMLCh[13] lnRelationship
lnRelationship[:] = [chLatin_r, chLatin_e, chLatin_l, chLatin_a, chLatin_t, chLatin_i, chLatin_o, chLatin_n, chLatin_s, chLatin_h, chLatin_i, chLatin_p, chNull]
cdef XMLCh[9] lnResource
lnResource[:] = [chLatin_r, chLatin_e, chLatin_s, chLatin_o, chLatin_u, chLatin_r, chLatin_c, chLatin_e, chNull]
cdef XMLCh[10] lnResources
lnResources[:] = [chLatin_r, chLatin_e, chLatin_s, chLatin_o, chLatin_u, chLatin_r, chLatin_c, chLatin_e, chLatin_s, chNull]
cdef XMLCh[5] lnRole
lnRole[:] = [chLatin_r, chLatin_o, chLatin_l, chLatin_e, chNull]
cdef XMLCh[8] lnRoleRef
lnRoleRef[:] = [chLatin_r, chLatin_o, chLatin_l, chLatin_e, chLatin_R, chLatin_e, chLatin_f, chNull]
cdef XMLCh[9] lnRoleType
lnRoleType[:] = [chLatin_r, chLatin_o, chLatin_l, chLatin_e, chLatin_T, chLatin_y, chLatin_p, chLatin_e, chNull]
cdef XMLCh[8] lnRoleURI
lnRoleURI[:] = [chLatin_r, chLatin_o, chLatin_l, chLatin_e, chLatin_U, chLatin_R, chLatin_I, chNull]
cdef XMLCh[4] lnRss
lnRss[:] = [chLatin_r, chLatin_s, chLatin_s, chNull]
cdef XMLCh[7] lnSchema
lnSchema[:] = [chLatin_s, chLatin_c, chLatin_h, chLatin_e, chLatin_m, chLatin_a, chNull]
cdef XMLCh[7] lnScheme
lnScheme[:] = [chLatin_s, chLatin_c, chLatin_h, chLatin_e, chLatin_m, chLatin_e, chNull]
cdef XMLCh[15] lnSchemaLocation
lnSchemaLocation[:] = [chLatin_s, chLatin_c, chLatin_h, chLatin_e, chLatin_m, chLatin_a, chLatin_L, chLatin_o, chLatin_c, chLatin_a, chLatin_t, chLatin_i, chLatin_o, chLatin_n, chNull]
cdef XMLCh[10] lnSchemaRef
lnSchemaRef[:] = [chLatin_s, chLatin_c, chLatin_h, chLatin_e, chLatin_m, chLatin_a, chLatin_R, chLatin_e, chLatin_f, chNull]
cdef XMLCh[5] lnShow
lnShow[:] = [chLatin_s, chLatin_h, chLatin_o, chLatin_w, chNull]
cdef XMLCh[7] lnSimple
lnSimple[:] = [chLatin_s, chLatin_i, chLatin_m, chLatin_p, chLatin_l, chLatin_e, chNull]
cdef XMLCh[15] lnSQNameItemType
lnSQNameItemType[:] = [chLatin_S, chLatin_Q, chLatin_N, chLatin_a, chLatin_m, chLatin_e, chLatin_I, chLatin_t, chLatin_e, chLatin_m, chLatin_T, chLatin_y, chLatin_p, chLatin_e, chNull]
cdef XMLCh[11] lnSQNameType
lnSQNameType[:] = [chLatin_S, chLatin_Q, chLatin_N, chLatin_a, chLatin_m, chLatin_e, chLatin_T, chLatin_y, chLatin_p, chLatin_e, chNull]
cdef XMLCh[7] lnTarget
lnTarget[:] = [chLatin_t, chLatin_a, chLatin_r, chLatin_g, chLatin_e, chLatin_t, chNull]
cdef XMLCh[16] lnTargetNamespace
lnTargetNamespace[:] = [chLatin_t, chLatin_a, chLatin_r, chLatin_g, chLatin_e, chLatin_t, chLatin_N, chLatin_a, chLatin_m, chLatin_e, chLatin_s, chLatin_p, chLatin_a, chLatin_c, chLatin_e, chNull]
cdef XMLCh[9] lnTestcase
lnTestcase[:] = [chLatin_t, chLatin_e, chLatin_s, chLatin_t, chLatin_c, chLatin_a, chLatin_s, chLatin_e, chNull]
cdef XMLCh[10] lnTestcases
lnTestcases[:] = [chLatin_t, chLatin_e, chLatin_s, chLatin_t, chLatin_c, chLatin_a, chLatin_s, chLatin_e, chLatin_s, chNull]
cdef XMLCh[8] lnTestSet
lnTestSet[:] = [chLatin_t, chLatin_e, chLatin_s, chLatin_t, chLatin_S, chLatin_e, chLatin_t, chNull]
cdef XMLCh[10] lnTestSuite
lnTestSuite[:] = [chLatin_t, chLatin_e, chLatin_s, chLatin_t, chLatin_S, chLatin_u, chLatin_i, chLatin_t, chLatin_e, chNull]
cdef XMLCh[6] lnTitle
lnTitle[:] = [chLatin_t, chLatin_i, chLatin_t, chLatin_l, chLatin_e, chNull]
cdef XMLCh[3] lnTo
lnTo[:] = [chLatin_t, chLatin_o, chNull]
cdef XMLCh[6] lnTuple
lnTuple[:] = [chLatin_t, chLatin_u, chLatin_p, chLatin_l, chLatin_e, chNull]
cdef XMLCh[5] lnType
lnType[:] = [chLatin_t, chLatin_y, chLatin_p, chLatin_e, chNull]
cdef XMLCh[12] lnTypedMember
lnTypedMember[:] = [chLatin_t, chLatin_y, chLatin_p, chLatin_e, chLatin_d, chLatin_M, chLatin_e, chLatin_m, chLatin_b, chLatin_e, chLatin_r, chNull]
cdef XMLCh[5] lnUnit
lnUnit[:] = [chLatin_u, chLatin_n, chLatin_i, chLatin_t, chNull]
cdef XMLCh[8] lnUnitRef
lnUnitRef[:] = [chLatin_u, chLatin_n, chLatin_i, chLatin_t, chLatin_R, chLatin_e, chLatin_f, chNull]
cdef XMLCh[4] lnUse
lnUse[:] = [chLatin_u, chLatin_s, chLatin_e, chNull]
cdef XMLCh[7] lnUsedOn
lnUsedOn[:] = [chLatin_u, chLatin_s, chLatin_e, chLatin_d, chLatin_O, chLatin_n, chNull]
cdef XMLCh[7] lnWeight
lnWeight[:] = [chLatin_w, chLatin_e, chLatin_i, chLatin_g, chLatin_h, chLatin_t, chNull]
cdef XMLCh[5] lnXbrl
lnXbrl[:] = [chLatin_x, chLatin_b, chLatin_r, chLatin_l, chNull]
cdef XMLCh[6] lnXhtml
lnXhtml[:] = [chLatin_x, chLatin_h, chLatin_t, chLatin_m, chLatin_l, chNull]
cdef XMLCh[6] lnXmlns
lnXmlns[:] = [chLatin_x, chLatin_m, chLatin_l, chLatin_n, chLatin_s, chNull]


#singleton address constants
cdef XMLCh[15] nElementQName
nElementQName[:] = [chAt, chLatin_e, chLatin_l, chLatin_e, chLatin_m, chLatin_e, chLatin_n, chLatin_t, chLatin_Q, chLatin_N, chLatin_a, chLatin_m, chLatin_e, chAt, chNull]
cdef XMLCh[14] nElementText
nElementText[:] = [chAt, chLatin_e, chLatin_l, chLatin_e, chLatin_m, chLatin_e, chLatin_n, chLatin_t, chLatin_T, chLatin_e, chLatin_x, chLatin_t, chAt, chNull]
cdef XMLCh[18] nElementSequence
nElementSequence[:] = [chAt, chLatin_e, chLatin_l, chLatin_e, chLatin_m, chLatin_e, chLatin_n, chLatin_t, chLatin_S, chLatin_e, chLatin_q, chLatin_u, chLatin_e, chLatin_n, chLatin_c, chLatin_e, chAt, chNull]
cdef XMLCh[14] nElementTail
nElementTail[:] = [chAt, chLatin_e, chLatin_l, chLatin_e, chLatin_m, chLatin_e, chLatin_n, chLatin_t, chLatin_T, chLatin_a, chLatin_i, chLatin_l, chAt, chNull]
cdef XMLCh[20] nElementTypedValue
nElementTypedValue[:] = [chAt, chLatin_e, chLatin_l, chLatin_e, chLatin_m, chLatin_e, chLatin_n, chLatin_t, chLatin_T, chLatin_y, chLatin_p, chLatin_e, chLatin_d, chLatin_V, chLatin_a, chLatin_l, chLatin_u, chLatin_e, chAt, chNull]
cdef XMLCh[14] nFactIsTuple
nFactIsTuple[:] = [chAt, chLatin_f, chLatin_a, chLatin_c, chLatin_t, chLatin_I, chLatin_s, chLatin_T, chLatin_u, chLatin_p, chLatin_l, chLatin_e, chAt, chNull]
cdef XMLCh[8] nNsmap
nNsmap[:] = [chAt, chLatin_n, chLatin_s, chLatin_m, chLatin_a, chLatin_p, chAt, chNull]
cdef XMLCh[13] nSourceLine
nSourceLine[:] = [chAt, chLatin_s, chLatin_o, chLatin_u, chLatin_r, chLatin_c, chLatin_e, chLatin_L, chLatin_i, chLatin_n, chLatin_e, chAt, chNull]
cdef XMLCh[12] nSourceCol
nSourceCol[:] = [chAt, chLatin_s, chLatin_o, chLatin_u, chLatin_r, chLatin_c, chLatin_e, chLatin_C, chLatin_o, chLatin_l, chAt, chNull]
cdef XMLCh[12] nValidity
nValidity[:] = [chAt, chLatin_s, chLatin_o, chLatin_u, chLatin_r, chLatin_c, chLatin_e, chLatin_C, chLatin_o, chLatin_l, chAt, chNull]

cdef hash_t hArc = PyObject_Hash(u"arc") # hash of "arc"
cdef hash_t hArcroleType = PyObject_Hash(u"arcroleType") # hash of "arcroleType"
cdef hash_t hArcroleRef = PyObject_Hash(u"arcroleRef") # hash of "arcroleRef"
cdef hash_t hContext = PyObject_Hash(u"@context@") # hash of "@context@"
cdef hash_t hDimension = PyObject_Hash(u"@dimension@") # hash of "@dimension@"
cdef hash_t hExtended = PyObject_Hash(u"extended") # hash of "extended"
cdef hash_t hFactItem = PyObject_Hash(u"@factItem@") # hash of "@factItem@"
cdef hash_t hFactTuple = PyObject_Hash(u"@factTuple@") # hash of "@factTuple@"
cdef hash_t hLocator = PyObject_Hash(u"locator") # hash of "locator"
cdef hash_t hPyNone = PyObject_Hash(None)
cdef hash_t hResource = PyObject_Hash(u"resource") # hash of "resource"
cdef hash_t hRoleRef = PyObject_Hash(u"roleRef") # hash of "roleRef"
cdef hash_t hRoleType = PyObject_Hash(u"roleType") # hash of "roleType"
cdef hash_t hRootElement = PyObject_Hash(u"@rootElement@") # hash of "@rootElement@"
cdef hash_t hSimple = PyObject_Hash(u"simple") # hash of "simple"
cdef hash_t hUnit = PyObject_Hash(u"@unit@") # hash of "@unit@"
cdef hash_t hXbrlDimensions = PyObject_Hash(u"XBRL-dimensions") # hash of "XBRL-dimensions"
cdef hash_t hXbrlFormulae = PyObject_Hash(u"XBRL-formulae") # hash of "XBRL-formulae"
cdef hash_t hXbrlTableRendering = PyObject_Hash(u"XBRL-table-rendering") # hash of "XBRL-table-rendering"
cdef hash_t hXbrlFootnotes = PyObject_Hash(u"XBRL-footnotes") # hash of "XBRL-footnotes"

cdef XMLCh[7] xmlnsPrefix
xmlnsPrefix[:] = [chLatin_x, chLatin_m, chLatin_l, chLatin_n, chLatin_s, chColon, chNull]
cdef XMLCh[6] xmlns
xmlns[:] = [chLatin_x, chLatin_m, chLatin_l, chLatin_n, chLatin_s, chNull]

cdef XMLCh[2] xmlchPipe
xmlchPipe[:] = [chPipe, chNull]
cdef XMLCh[2] xmlchLBrace
xmlchLBrace[:] = [chOpenCurly, chNull]
cdef XMLCh[2] xmlchRBrace
xmlchRBrace[:] = [chCloseCurly, chNull]
cdef XMLCh[2] xmlchColon
xmlchColon[:] = [chColon, chNull]

cdef XMLCh[5] xmlchTrue
xmlchTrue[:] = [chLatin_t, chLatin_r, chLatin_u, chLatin_e, chNull]
cdef XMLCh[6] xmlchFalse
xmlchFalse[:] = [chLatin_f, chLatin_a, chLatin_l, chLatin_s, chLatin_e, chNull]
cdef XMLCh[2] xmlchZero
xmlchZero[:] = [chDigit_0, chNull]
cdef XMLCh[2] xmlchOne
xmlchOne[:] = [chDigit_1, chNull]

cdef XMLCh[400] xmlchSchemaLocationsForXsdFileLinkbases
xmlchSchemaLocationsForXsdFileLinkbases[:] = [chSpace, chSpace, chSpace, chSpace, chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_w, chLatin_w, chLatin_w, chPeriod, chLatin_x, chLatin_b, chLatin_r, chLatin_l, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_2, chDigit_0, chDigit_0, chDigit_3, chForwardSlash, chLatin_l, chLatin_i, chLatin_n, chLatin_k, chLatin_b, chLatin_a, chLatin_s, chLatin_e, chSpace, chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_w, chLatin_w, chLatin_w, chPeriod, chLatin_x, chLatin_b, chLatin_r, chLatin_l, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_2, chDigit_0, chDigit_0, chDigit_3, chForwardSlash, chLatin_x, chLatin_b, chLatin_r, chLatin_l, chDash, chLatin_l, chLatin_i, chLatin_n, chLatin_k, chLatin_b, chLatin_a, chLatin_s, chLatin_e, chDash, chDigit_2, chDigit_0, chDigit_0, chDigit_3, chDash, chDigit_1, chDigit_2, chDash, chDigit_3, chDigit_1, chPeriod, chLatin_x, chLatin_s, chLatin_d, chSpace, chSpace, chSpace, chSpace, chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_w, chLatin_w, chLatin_w, chPeriod, chLatin_w, chDigit_3, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_1, chDigit_9, chDigit_9, chDigit_9, chForwardSlash, chLatin_x, chLatin_l, chLatin_i, chLatin_n, chLatin_k, chSpace, chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_w, chLatin_w, chLatin_w, chPeriod, chLatin_x, chLatin_b, chLatin_r, chLatin_l, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_2, chDigit_0, chDigit_0, chDigit_3, chForwardSlash, chLatin_x, chLatin_l, chLatin_i, chLatin_n, chLatin_k, chDash, chDigit_2, chDigit_0, chDigit_0, chDigit_3, chDash, chDigit_1, chDigit_2, chDash, chDigit_3, chDigit_1, chPeriod, chLatin_x, chLatin_s, chLatin_d, chSpace, chSpace, chSpace, chSpace, chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_x, chLatin_b, chLatin_r, chLatin_l, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_2, chDigit_0, chDigit_0, chDigit_8, chForwardSlash, chLatin_g, chLatin_e, chLatin_n, chLatin_e, chLatin_r, chLatin_i, chLatin_c, chSpace, chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_w, chLatin_w, chLatin_w, chPeriod, chLatin_x, chLatin_b, chLatin_r, chLatin_l, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_2, chDigit_0, chDigit_0, chDigit_8, chForwardSlash, chLatin_g, chLatin_e, chLatin_n, chLatin_e, chLatin_r, chLatin_i, chLatin_c, chDash, chLatin_l, chLatin_i, chLatin_n, chLatin_k, chPeriod, chLatin_x, chLatin_s, chLatin_d, chSpace, chSpace, chSpace, chSpace, chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_w, chLatin_w, chLatin_w, chPeriod, chLatin_w, chDigit_3, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chLatin_X, chLatin_M, chLatin_L, chForwardSlash, chDigit_1, chDigit_9, chDigit_9, chDigit_8, chForwardSlash, chLatin_n, chLatin_a, chLatin_m, chLatin_e, chLatin_s, chLatin_p, chLatin_a, chLatin_c, chLatin_e, chSpace, chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_w, chLatin_w, chLatin_w, chPeriod, chLatin_w, chDigit_3, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_2, chDigit_0, chDigit_0, chDigit_1, chForwardSlash, chLatin_x, chLatin_m, chLatin_l, chPeriod, chLatin_x, chLatin_s, chLatin_d, chSpace, chSpace, chSpace, chSpace, chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_a, chLatin_r, chLatin_e, chLatin_l, chLatin_l, chLatin_e, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_2, chDigit_0, chDigit_1, chDigit_8, chForwardSlash, chLatin_X, chLatin_s, chLatin_S, chLatin_y, chLatin_n, chLatin_A, chLatin_n, chLatin_o, chLatin_t, chSpace, chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_a, chLatin_r, chLatin_e, chLatin_l, chLatin_l, chLatin_e, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_2, chDigit_0, chDigit_1, chDigit_8, chForwardSlash, chLatin_X, chLatin_s, chLatin_S, chLatin_y, chLatin_n, chLatin_t, chLatin_h, chLatin_e, chLatin_t, chLatin_i, chLatin_c, chLatin_A, chLatin_n, chLatin_n, chLatin_o, chLatin_t, chLatin_a, chLatin_t, chLatin_i, chLatin_o, chLatin_n, chPeriod, chLatin_x, chLatin_s, chLatin_d, chNull]
# must match    
cdef XMLCh[248] xmlchSchemaLocationsForXsdElements
xmlchSchemaLocationsForXsdElements[:] = [chSpace, chSpace, chSpace, chSpace, chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_w, chLatin_w, chLatin_w, chPeriod, chLatin_x, chLatin_b, chLatin_r, chLatin_l, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_2, chDigit_0, chDigit_0, chDigit_3, chForwardSlash, chLatin_i, chLatin_n, chLatin_s, chLatin_t, chLatin_a, chLatin_n, chLatin_c, chLatin_e, chSpace, chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_w, chLatin_w, chLatin_w, chPeriod, chLatin_x, chLatin_b, chLatin_r, chLatin_l, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_2, chDigit_0, chDigit_0, chDigit_3, chForwardSlash, chLatin_x, chLatin_b, chLatin_r, chLatin_l, chDash, chLatin_i, chLatin_n, chLatin_s, chLatin_t, chLatin_a, chLatin_n, chLatin_c, chLatin_e, chDash, chDigit_2, chDigit_0, chDigit_0, chDigit_3, chDash, chDigit_1, chDigit_2, chDash, chDigit_3, chDigit_1, chPeriod, chLatin_x, chLatin_s, chLatin_d, chSpace, chSpace, chSpace, chSpace, chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_w, chLatin_w, chLatin_w, chPeriod, chLatin_w, chDigit_3, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chLatin_X, chLatin_M, chLatin_L, chForwardSlash, chDigit_1, chDigit_9, chDigit_9, chDigit_8, chForwardSlash, chLatin_n, chLatin_a, chLatin_m, chLatin_e, chLatin_s, chLatin_p, chLatin_a, chLatin_c, chLatin_e, chSpace, chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_w, chLatin_w, chLatin_w, chPeriod, chLatin_w, chDigit_3, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_2, chDigit_0, chDigit_0, chDigit_1, chForwardSlash, chLatin_x, chLatin_m, chLatin_l, chPeriod, chLatin_x, chLatin_s, chLatin_d, chSpace, chSpace, chSpace, chSpace, chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_a, chLatin_r, chLatin_e, chLatin_l, chLatin_l, chLatin_e, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_2, chDigit_0, chDigit_1, chDigit_8, chForwardSlash, chLatin_X, chLatin_s, chLatin_S, chLatin_y, chLatin_n, chLatin_A, chLatin_n, chLatin_o, chLatin_t, chSpace, chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_a, chLatin_r, chLatin_e, chLatin_l, chLatin_l, chLatin_e, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_2, chDigit_0, chDigit_1, chDigit_8, chForwardSlash, chLatin_X, chLatin_s, chLatin_S, chLatin_y, chLatin_n, chLatin_t, chLatin_h, chLatin_e, chLatin_t, chLatin_i, chLatin_c, chLatin_A, chLatin_n, chLatin_n, chLatin_o, chLatin_t, chLatin_a, chLatin_t, chLatin_i, chLatin_o, chLatin_n, chPeriod, chLatin_x, chLatin_s, chLatin_d, chNull]
   
# schemarefs need to be synced with XbrlConsts.hrefScheamImports

cdef XMLCh[35] xmlchNsXsdQuoted1
xmlchNsXsdQuoted1[:] = [chDoubleQuote, chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_w, chLatin_w, chLatin_w, chPeriod, chLatin_w, chDigit_3, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_2, chDigit_0, chDigit_0, chDigit_1, chForwardSlash, chLatin_X, chLatin_M, chLatin_L, chLatin_S, chLatin_c, chLatin_h, chLatin_e, chLatin_m, chLatin_a, chDoubleQuote, chNull]
cdef XMLCh[35] xmlchNsXsdQuoted2
xmlchNsXsdQuoted2[:] = [chSingleQuote, chLatin_h, chLatin_t, chLatin_t, chLatin_p, chColon, chForwardSlash, chForwardSlash, chLatin_w, chLatin_w, chLatin_w, chPeriod, chLatin_w, chDigit_3, chPeriod, chLatin_o, chLatin_r, chLatin_g, chForwardSlash, chDigit_2, chDigit_0, chDigit_0, chDigit_1, chForwardSlash, chLatin_X, chLatin_M, chLatin_L, chLatin_S, chLatin_c, chLatin_h, chLatin_e, chLatin_m, chLatin_a, chSingleQuote, chNull]

# unicode strings
cdef unicode uClarkXbrldtTypedDomainRef = u"{http://xbrl.org/2005/xbrldt}typedDomainRef"
cdef unicode uClarkEnumerationDomain2014 = u"{http://xbrl.org/2014/extensible-enumerations}domain"
cdef unicode uClarkEnumerationDomain2016 = u"{http://xbrl.org/PWD/2016-10-12/extensible-enumerations-1.1}domain"
cdef unicode uClarkEnumerationDomain2YMD = u"{http://xbrl.org/WGWD/YYYY-MM-DD/extensible-enumerations-2.0}domain"
cdef unicode uClarkEnumerationDomain1YMD = u"{http://xbrl.org/WGWD/YYYY-MM-DD/extensible-enumerations-1.1}domain"
cdef unicode uClarkEnumerationLinkrole2014 = u"{http://xbrl.org/2014/extensible-enumerations}linkrole"
cdef unicode uClarkEnumerationLinkrole2016 = u"{http://xbrl.org/PWD/2016-10-12/extensible-enumerations-1.1}linkrole"
cdef unicode uClarkEnumerationLinkrole2YMD = u"{http://xbrl.org/WGWD/YYYY-MM-DD/extensible-enumerations-2.0}linkrole"
cdef unicode uClarkEnumerationLinkrole1YMD = u"{http://xbrl.org/WGWD/YYYY-MM-DD/extensible-enumerations-1.1}linkrole"
cdef unicode uClarkEnumerationUsable2014 = u"{http://xbrl.org/2014/extensible-enumerations}headUsable"
cdef unicode uClarkEnumerationUsable2016 = u"{http://xbrl.org/PWD/2016-10-12/extensible-enumerations-1.1}headUsable"
cdef unicode uClarkEnumerationUsable2YMD = u"{http://xbrl.org/WGWD/YYYY-MM-DD/extensible-enumerations-2.0}headUsable"
cdef unicode uClarkEnumerationUsable1YMD = u"{http://xbrl.org/WGWD/YYYY-MM-DD/extensible-enumerations-1.1}headUsable"
cdef unicode uClarkXlinkActuate = u"{http://www.w3.org/1999/xlink}actuate"
cdef unicode uClarkXlinkArcrole = u"{http://www.w3.org/1999/xlink}arcrole"
cdef unicode uClarkXlinkHref = u"{http://www.w3.org/1999/xlink}href"
cdef unicode uClarkXlinkFrom = u"{http://www.w3.org/1999/xlink}from"
cdef unicode uClarkXlinkLabel = u"{http://www.w3.org/1999/xlink}label"
cdef unicode uClarkXlinkRole = u"{http://www.w3.org/1999/xlink}role"
cdef unicode uClarkXlinkShow = u"{http://www.w3.org/1999/xlink}show"
cdef unicode uClarkXlinkTitle = u"{http://www.w3.org/1999/xlink}title"
cdef unicode uClarkXlinkTo = u"{http://www.w3.org/1999/xlink}to"
cdef unicode uClarkXlinkType = u"{http://www.w3.org/1999/xlink}type"
cdef unicode uClarkXsiNil = u"{http://www.w3.org/2001/XMLSchema-instance}nil"
cdef unicode uClarkXmlBase = u"{http://www.w3.org/XML/1998/namespace}base"
cdef unicode uClarkXmlLang = u"{http://www.w3.org/XML/1998/namespace}lang"



cdef unicode uAnonymousType = u"@anonymousType"
cdef unicode uArcroleURI = u"arcroleURI"
cdef unicode uContextRef = u"contextRef"
cdef unicode uCyclesAllowed = u"cyclesAllowed"
cdef unicode uDecimals = u"decimals"
cdef unicode uDimension = u"dimension"
cdef unicode uEmptyStr = u""
cdef unicode uErrorStr = u"(Error)"
cdef unicode uId = u"id"
cdef unicode uLexicalPatternMismatch = u"lexical pattern mismatch"
cdef unicode uHrefXsd = u"http://www.w3.org/2001/XMLSchema.xsd"
cdef unicode uHrefIx10 = u"http://www.xbrl.org/2008/inlineXBRL/xhtml-inlinexbrl-1_0.xsd"
cdef unicode uHrefIx11 = u"http://www.xbrl.org/2013/inlineXBRL/xhtml-inlinexbrl-1_1.xsd"
cdef unicode uHrefLink = u"http://www.xbrl.org/2003/xbrl-linkbase-2003-12-31.xsd"
cdef unicode uNsIso4217 = u"http://www.xbrl.org/2003/iso4217"
cdef unicode uNsIxbrl11 = u"http://www.xbrl.org/2013/inlineXBRL"
cdef unicode uNsLink = u"http://www.xbrl.org/2003/linkbase"
cdef unicode uNsXbrldi = u"http://xbrl.org/2006/xbrldi"
cdef unicode uNsXbrldt = u"http://xbrl.org/2005/xbrldt"
cdef unicode uNsXbrli = u"http://www.xbrl.org/2003/instance"
cdef unicode uNsXml = u"http://www.w3.org/XML/1998/namespace"
cdef unicode uNsXsd = u"http://www.w3.org/2001/XMLSchema"
cdef unicode uIx = u"ix"
cdef unicode uLink = u"link"
cdef unicode uOrder = u"order"
cdef unicode uPrecision = u"precision"
cdef unicode uPreferredLabel = u"preferredLabel"
cdef unicode uPriority = u"priority"
cdef unicode uRoleURI = u"roleURI"
cdef unicode uScenario = u"scenario"	
cdef unicode uSegment = u"segment"
cdef unicode uUnitRef = u"unitRef"
cdef unicode uUse = u"use"
cdef unicode uWeight = u"weight"
cdef unicode uXbrldi = u"xbrldi"
cdef unicode uXbrli = u"xbrli"
cdef unicode uXbrlDimensions = u"XBRL-dimensions"
cdef unicode uXbrlFormulae = u"XBRL-formulae"
cdef unicode uXbrlTableRendering = u"XBRL-table-rendering"
cdef unicode uXbrlFootnotes = u"XBRL-footnotes"
cdef unicode uXml = u"xml"
cdef unicode uXs = u"xs"

cdef QName qnXbrldiExplicitMember = QName(uNsXbrldi, uXbrldi, u"explicitMember")
cdef QName qnXbrldiTypedMember = QName(uNsXbrldi, uXbrldi, u"typedMember")
cdef QName qnXbrliDateUnion = QName(uNsXbrli, uXbrli, u"dateUnion")
cdef QName qnXbrliDecimalsUnion = QName(uNsXbrli, uXbrli, u"decimalsType")
cdef QName qnXbrliDenominator = QName(uNsXbrli, uXbrli, u"denominator")
cdef QName qnXbrliDivide = QName(uNsXbrli, uXbrli, u"divide")
cdef QName qnXbrliEntity = QName(uNsXbrli, uXbrli, u"entity")
cdef QName qnXbrliEndDate = QName(uNsXbrli, uXbrli, u"endDate")
cdef QName qnXbrliForever = QName(uNsXbrli, uXbrli, u"forever")
cdef QName qnXbrliIdentifier = QName(uNsXbrli, uXbrli, u"identifier")
cdef QName qnXbrliInstant = QName(uNsXbrli, uXbrli, u"instant")
cdef QName qnXbrliMeasure = QName(uNsXbrli, uXbrli, u"measure")
cdef QName qnXbrliNonZeroDecimalUnion = QName(uNsXbrli, uXbrli, u"nonZeroDecimal")
cdef QName qnXbrliNumerator = QName(uNsXbrli, uXbrli, u"numerator")
cdef QName qnXbrliPeriod = QName(uNsXbrli, uXbrli, u"period")
cdef QName qnXbrliPrecisionUnion = QName(uNsXbrli, uXbrli, u"precisionType")
cdef QName qnXbrliScenario = QName(uNsXbrli, uXbrli, uScenario)
cdef QName qnXbrliSegment = QName(uNsXbrli, uXbrli, uSegment)
cdef QName qnXbrliStartDate = QName(uNsXbrli, uXbrli, u"startDate")
cdef QName qnXbrliUnitNumerator = QName(uNsXbrli, uXbrli, u"unitNumerator")
cdef QName qnXbrliUnitDenominator = QName(uNsXbrli, uXbrli, u"unitDenominator")
cdef QName qnXsdSchema = QName(uNsXsd, uXs, u"schema")
cdef QName qnLinkRoleType = QName(uNsLink, uLink, u"roleType")
cdef QName qnLinkArcroleType = QName(uNsLink, uLink, u"arcroleType")
cdef QName qnIxbrl11Hidden = QName(uNsIxbrl11, uIx, u"hidden")


# AnyURI objects
cdef AnyURI uriErrorStr = AnyURI(uErrorStr)
cdef AnyURI uriXml = AnyURI(uNsXml)

# decimal objects
cdef object dZERO = Decimal(0)
cdef object dONE = Decimal(1)
cdef object dNaN = Decimal("nan")
cdef float fNaN = float("nan")

cdef dict EMPTY_DICT = dict()

cdef set inlineElementsWithNoContent = {
    "relationship", # inline 1.1
    "schemaRef", "linkbaseRef", "roleRef", "arcroleRef", # xbrl instance
    "area", "base", "basefont", "br", "col", "frame", "hr", "img", "input", "isindex", "link", "meta", "param", # xhtml
    # elements which can have no text node siblings, tested with IE, Chrome and Safari
    "td", "tr"
    }
    
cdef unicode NO_VALUE = u"@no-value@" # singleton for no value

# regex pattern objects
cdef object pValidateDecimalPattern = re_compile(r"^[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)$")
cdef object pValidateIntegerPattern = re_compile(r"^[+-]?([0-9]+)$")
cdef object pValidateFloatPattern = re_compile(r"^(\+|-)?([0-9]+(\.[0-9]*)?|\.[0-9]+)([Ee](\+|-)?[0-9]+)?$|^(\+|-)?INF$|^NaN$")
cdef object pXpointerFragmentIdentifierPattern = re_compile(r"([\w.]+)(\(([^)]*)\))?")

#generated by setup-arelle_c.py
cdef unicode uDateCompiled = u"2022.02.16"
