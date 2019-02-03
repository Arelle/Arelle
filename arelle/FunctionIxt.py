#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Created on July 5, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
try:
    import regex as re
except ImportError:
    import re
from arelle.PluginManager import pluginClassMethods
from arelle import XPathContext
from datetime import datetime

class ixtFunctionNotAvailable(Exception):
    def __init__(self):
        self.args =  (_("ixt function not available"),)
    def __repr__(self):
        return self.args[0]
    
def call(xc, p, qn, args):
    try:
        _ixtFunction = ixtNamespaceFunctions[qn.namespaceURI][qn.localName]
    except KeyError:
        raise XPathContext.FunctionNotAvailable(str(qn))
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    if len(args[0]) != 1: raise XPathContext.FunctionArgType(0,"xs:string")
    return _ixtFunction(str(args[0][0]))

# class of deferred-compilation patterns
# reduces load time by .5 sec (debug) .15 sec (compiled)
class RePattern:
    def __init__(self, pattern, flags=0):
        self.pattern = pattern
        self.regex = None
        self.flags = flags
    
    def match(self, target):
        if self.regex is None:
            self.regex = re.compile(self.pattern, self.flags)
        return self.regex.match(target)

    def search(self, target):
        if self.regex is None:
            self.regex = re.compile(self.pattern, self.flags)
        return self.regex.search(target)

dateslashPattern = RePattern(r"^\s*(\d+)/(\d+)/(\d+)\s*$")
daymonthslashPattern = RePattern(r"^\s*([0-9]{1,2})/([0-9]{1,2})\s*$")
monthdayslashPattern = RePattern(r"^\s*([0-9]{1,2})/([0-9]{1,2})\s*$")
datedotPattern = RePattern(r"^\s*(\d+)\.(\d+)\.(\d+)\s*$")
daymonthPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+([0-9]{1,2})\s*$")
monthdayPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+([0-9]{1,2})[A-Za-z]*\s*$")
daymonthyearPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+([0-9]{1,2})[^0-9]+([0-9]{4}|[0-9]{1,2})\s*$")
monthdayyearPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+([0-9]{1,2})[^0-9]+([0-9]{4}|[0-9]{1,2})\s*$")

dateUsPattern = RePattern(r"^\s*(\w+)\s+(\d+),\s+(\d+)\s*$")
dateEuPattern = RePattern(r"^\s*(\d+)\s+(\w+)\s+(\d+)\s*$")
daymonthBgPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(ян|фев|мар|апр|май|маи|юни|юли|авг|сеп|окт|ное|дек|ЯН|ФЕВ|МАР|АПР|МАЙ|МАИ|ЮНИ|ЮЛИ|АВГ|СЕП|ОКТ|НОЕ|ДЕК|Ян|Фев|Мар|Апр|Май|Маи|Юни|Юли|Авг|Сеп|Окт|Ное|Дек)[^0-9]{0,6}\s*$")
daymonthCsPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(ledna|února|unora|března|brezna|dubna|května|kvetna|června|cervna|července|cervence|srpna|září|zari|října|rijna|listopadu|prosince|led|úno|uno|bře|bre|dub|kvě|kve|čvn|cvn|čvc|cvc|srp|zář|zar|říj|rij|lis|pro|LEDNA|ÚNORA|UNORA|BŘEZNA|BREZNA|DUBNA|KVĚTNA|KVETNA|ČERVNA|CERVNA|ČERVENCE|CERVENCE|SRPNA|ZÁŘÍ|ZARI|ŘÍJNA|RIJNA|LISTOPADU|PROSINCE|LED|ÚNO|UNO|BŘE|BRE|DUB|KVĚ|KVE|ČVN|CVN|ČVC|CVC|SRP|ZÁŘ|ZAR|ŘÍJ|RIJ|LIS|PRO|Ledna|Února|Unora|Března|Brezna|Dubna|Května|Kvetna|Června|Cervna|Července|Cervence|Srpna|Září|Zari|Října|Rijna|Listopadu|Prosince|Led|Úno|Uno|Bře|Bre|Dub|Kvě|Kve|Čvn|Cvn|Čvc|Cvc|Srp|Zář|Zar|Říj|Rij|Lis|Pro)\.?\s*$")
daymonthDePattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(jan|jän|jaen|feb|mär|maer|mar|apr|mai|jun|jul|aug|sep|okt|nov|dez|JAN|JÄN|JAEN|FEB|MÄR|MAER|MAR|APR|MAI|JUN|JUL|AUG|SEP|OKT|NOV|DEZ|Jan|Jän|Jaen|Feb|Mär|Maer|Mar|Apr|Mai|Jun|Jul|Aug|Sep|Okt|Nov|Dez)[^0-9]{0,6}\s*$")
daymonthDkPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(jan|feb|mar|apr|maj|jun|jul|aug|sep|okt|nov|dec)([A-Za-z]*)([.]*)\s*$", re.IGNORECASE)
daymonthElPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(ιαν|ίαν|φεβ|μάρ|μαρ|απρ|άπρ|αρίλ|άρίλ|αριλ|άριλ|μαΐ|μαι|μάι|μαϊ|μάϊ|ιούν|ίούν|ίουν|ιουν|ιούλ|ίούλ|ίουλ|ίουλ|ιουλ|αύγ|αυγ|σεπ|οκτ|όκτ|νοέ|νοε|δεκ|ΙΑΝ|ΊΑΝ|IΑΝ|ΦΕΒ|ΜΆΡ|ΜΑΡ|ΑΠΡ|ΆΠΡ|AΠΡ|AΡΙΛ|ΆΡΙΛ|ΑΡΙΛ|ΜΑΪ́|ΜΑΙ|ΜΆΙ|ΜΑΪ|ΜΆΪ|ΙΟΎΝ|ΊΟΎΝ|ΊΟΥΝ|IΟΥΝ|ΙΟΥΝ|IΟΥΝ|ΙΟΎΛ|ΊΟΎΛ|ΊΟΥΛ|IΟΎΛ|ΙΟΥΛ|IΟΥΛ|ΑΎΓ|ΑΥΓ|ΣΕΠ|ΟΚΤ|ΌΚΤ|OΚΤ|ΝΟΈ|ΝΟΕ|ΔΕΚ|Ιαν|Ίαν|Iαν|Φεβ|Μάρ|Μαρ|Απρ|Άπρ|Aπρ|Αρίλ|Άρίλ|Aρίλ|Aριλ|Άριλ|Αριλ|Μαΐ|Μαι|Μάι|Μαϊ|Μάϊ|Ιούν|Ίούν|Ίουν|Iούν|Ιουν|Iουν|Ιούλ|Ίούλ|Ίουλ|Iούλ|Ιουλ|Iουλ|Αύγ|Αυγ|Σεπ|Οκτ|Όκτ|Oκτ|Νοέ|Νοε|Δεκ)[^0-9]{0,8}\s*$")
daymonthEnPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s*$")
monthdayEnPattern = RePattern(r"^\s*(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)[^0-9]+([0-9]{1,2})[A-Za-z]{0,2}\s*$")
daymonthEsPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic|ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC|Ene|Feb|Mar|Abr|May|Jun|Jul|Ago|Sep|Oct|Nov|Dic)[^0-9]{0,7}\s*$")
daymonthEtPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(jaan|veebr|märts|marts|apr|mai|juuni|juuli|aug|sept|okt|nov|dets|JAAN|VEEBR|MÄRTS|MARTS|APR|MAI|JUUNI|JUULI|AUG|SEPT|OKT|NOV|DETS|Jaan|Veebr|Märts|Marts|Apr|Mai|Juuni|Juuli|Aug|Sept|Okt|Nov|Dets)[^0-9]{0,5}\s*$")
daymonthFiPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]*[^0-9a-zA-Z]+(tam|hel|maa|huh|tou|kes|hei|elo|syy|lok|mar|jou|TAM|HEL|MAA|HUH|TOU|KES|HEI|ELO|SYY|LOK|MAR|JOU|Tam|Hel|Maa|Huh|Tou|Kes|Hei|Elo|Syy|Lok|Mar|Jou)[^0-9]{0,8}\s*$")
daymonthFrPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(janv|févr|fevr|mars|avr|mai|juin|juil|août|aout|sept|oct|nov|déc|dec|JANV|FÉVR|FEVR|MARS|AVR|MAI|JUIN|JUIL|AOÛT|AOUT|SEPT|OCT|NOV|DÉC|DEC|Janv|Févr|Fevr|Mars|Avr|Mai|Juin|Juil|Août|Aout|Sept|Oct|Nov|Déc|Dec)[^0-9]{0,5}\s*$")
daymonthHrPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(sij|velj|ožu|ozu|tra|svi|lip|srp|kol|ruj|lis|stu|pro|SIJ|VELJ|OŽU|OZU|TRA|SVI|LIP|SRP|KOL|RUJ|LIS|STU|PRO|Sij|Velj|Ožu|Ozu|Tra|Svi|Lip|Srp|Kol|Ruj|Lis|Stu|Pro)[^0-9]{0,6}\s*$")
monthdayHuPattern = RePattern(r"^\s*(jan|feb|márc|marc|ápr|apr|máj|maj|jún|jun|júl|jul|aug|szept|okt|nov|dec|JAN|FEB|MÁRC|MARC|ÁPR|APR|MÁJ|MAJ|JÚN|JUN|JÚL|JUL|AUG|SZEPT|OKT|NOV|DEC|Jan|Feb|Márc|Marc|Ápr|Apr|Máj|Maj|Jún|Jun|Júl|Jul|Aug|Szept|Okt|Nov|Dec)[^0-9]{0,7}[^0-9]+([0-9]{1,2})\s*$")
daymonthItPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(gen|feb|mar|apr|mag|giu|lug|ago|set|ott|nov|dic|GEN|FEB|MAR|APR|MAG|GIU|LUG|AGO|SET|OTT|NOV|DIC|Gen|Feb|Mar|Apr|Mag|Giu|Lug|Ago|Set|Ott|Nov|Dic)[^0-9]{0,6}\s*$")
monthdayLtPattern = RePattern(r"^\s*(sau|vas|kov|bal|geg|bir|lie|rugp|rgp|rugs|rgs|spa|spl|lap|gru|grd|SAU|VAS|KOV|BAL|GEG|BIR|LIE|RUGP|RGP|RUGS|RGS|SPA|SPL|LAP|GRU|GRD|Sau|Vas|Kov|Bal|Geg|Bir|Lie|Rugp|Rgp|Rugs|Rgs|Spa|Spl|Lap|Gru|Grd)[^0-9]{0,6}[^0-9]+([0-9]{1,2})[^0-9]*\s*$")
daymonthLvPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(janv|febr|marts|apr|maijs|jūn|jun|jūl|jul|aug|sept|okt|nov|dec|JANV|FEBR|MARTS|APR|MAIJS|JŪN|JUN|JŪL|JUL|AUG|SEPT|OKT|NOV|DEC|Janv|Febr|Marts|Apr|Maijs|Jūn|Jun|Jūl|Jul|Aug|Sept|Okt|Nov|Dec)[^0-9]{0,6}\s*$")
daymonthNlPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(jan|feb|maa|mrt|apr|mei|jun|jul|aug|sep|okt|nov|dec|JAN|FEB|MAA|MRT|APR|MEI|JUN|JUL|AUG|SEP|OKT|NOV|DEC|Jan|Feb|Maa|Mrt|Apr|Mei|Jun|Jul|Aug|Sep|Okt|Nov|Dec)[^0-9]{0,6}\s*$")
daymonthNoPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(jan|feb|mar|apr|mai|jun|jul|aug|sep|okt|nov|des|JAN|FEB|MAR|APR|MAI|JUN|JUL|AUG|SEP|OKT|NOV|DES|Jan|Feb|Mar|Apr|Mai|Jun|Jul|Aug|Sep|Okt|Nov|Des)[^0-9]{0,6}\s*$")
daymonthPlPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]*[^0-9a-zA-Z]+(sty|lut|mar|kwi|maj|cze|lip|sie|wrz|paź|paz|lis|gru|STY|LUT|MAR|KWI|MAJ|CZE|LIP|SIE|WRZ|PAŹ|PAZ|LIS|GRU|Sty|Lut|Mar|Kwi|Maj|Cze|Lip|Sie|Wrz|Paź|Paz|Lis|Gru)[^0-9]{0,9}s*$")
daymonthPtPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez|JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ|Jan|Fev|Mar|Abr|Mai|Jun|Jul|Ago|Set|Out|Nov|Dez)[^0-9]{0,6}\s*$")
daymonthRomanPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]*[^XVIxvi]((I?(X|V|I)I{0,3})|(i?(x|v|i)i{0,3}))\s*$")
daymonthRoPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(ian|feb|mar|apr|mai|iun|iul|aug|sep|oct|noi|nov|dec|IAN|FEB|MAR|APR|MAI|IUN|IUL|AUG|SEP|OCT|NOI|NOV|DEC|Ian|Feb|Mar|Apr|Mai|Iun|Iul|Aug|Sep|Oct|Noi|Nov|Dec)[^0-9]{0,7}\s*$")
daymonthSkPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(jan|feb|mar|apr|máj|maj|jún|jun|júl|jul|aug|sep|okt|nov|dec|JAN|FEB|MAR|APR|MÁJ|MAJ|JÚN|JUN|JÚL|JUL|AUG|SEP|OKT|NOV|DEC|Jan|Feb|Mar|Apr|Máj|Maj|Jún|Jun|Júl|Jul|Aug|Sep|Okt|Nov|Dec)[^0-9]{0,6}\s*$")
daymonthSlPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(jan|feb|mar|apr|maj|jun|jul|avg|sep|okt|nov|dec|JAN|FEB|MAR|APR|MAJ|JUN|JUL|AVG|SEP|OKT|NOV|DEC|Jan|Feb|Mar|Apr|Maj|Jun|Jul|Avg|Sep|Okt|Nov|Dec)[^0-9]{0,6}\s*$")
daymonthyearBgPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(ян|фев|мар|апр|май|маи|юни|юли|авг|сеп|окт|ное|дек|ЯН|ФЕВ|МАР|АПР|МАЙ|МАИ|ЮНИ|ЮЛИ|АВГ|СЕП|ОКТ|НОЕ|ДЕК|Ян|Фев|Мар|Апр|Май|Маи|Юни|Юли|Авг|Сеп|Окт|Ное|Дек)[A-Za-z]*[^0-9]+([0-9]{1,2}|[0-9]{4})[^0-9]*\s*$")
daymonthyearCsPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(ledna|února|unora|března|brezna|dubna|května|kvetna|června|cervna|července|cervence|srpna|září|zari|října|rijna|listopadu|prosince|led|úno|uno|bře|bre|dub|kvě|kve|čvn|cvn|čvc|cvc|srp|zář|zar|říj|rij|lis|pro|LEDNA|ÚNORA|UNORA|BŘEZNA|BREZNA|DUBNA|KVĚTNA|KVETNA|ČERVNA|CERVNA|ČERVENCE|CERVENCE|SRPNA|ZÁŘÍ|ZARI|ŘÍJNA|RIJNA|LISTOPADU|PROSINCE|LED|ÚNO|UNO|BŘE|BRE|DUB|KVĚ|KVE|ČVN|CVN|ČVC|CVC|SRP|ZÁŘ|ZAR|ŘÍJ|RIJ|LIS|PRO|Ledna|Února|Unora|Března|Brezna|Dubna|Května|Kvetna|Června|Cervna|Července|Cervence|Srpna|Září|Zari|Října|Rijna|Listopadu|Prosince|Led|Úno|Uno|Bře|Bre|Dub|Kvě|Kve|Čvn|Cvn|Čvc|Cvc|Srp|Zář|Zar|Říj|Rij|Lis|Pro)[^0-9a-zA-Z]+[^0-9]*([0-9]{1,2}|[0-9]{4})\s*$")
daymonthyearDePattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(jan|jän|jaen|feb|mär|maer|mar|apr|mai|jun|jul|aug|sep|okt|nov|dez|JAN|JÄN|JAEN|FEB|MÄR|MAER|MAR|APR|MAI|JUN|JUL|AUG|SEP|OKT|NOV|DEZ|Jan|Jän|Jaen|Feb|Mär|Maer|Mar|Apr|Mai|Jun|Jul|Aug|Sep|Okt|Nov|Dez)[^0-9]+([0-9]{1,2}|[0-9]{4})\s*$")
daymonthyearDkPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(jan|feb|mar|apr|maj|jun|jul|aug|sep|okt|nov|dec)([A-Za-z]*)([.]*)[^0-9]*([0-9]{4}|[0-9]{1,2})\s*$", re.IGNORECASE)
daymonthyearElPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(ιαν|ίαν|φεβ|μάρ|μαρ|απρ|άπρ|αρίλ|άρίλ|αριλ|άριλ|μαΐ|μαι|μάι|μαϊ|μάϊ|ιούν|ίούν|ίουν|ιουν|ιούλ|ίούλ|ίουλ|ίουλ|ιουλ|αύγ|αυγ|σεπ|οκτ|όκτ|νοέ|νοε|δεκ|ΙΑΝ|ΊΑΝ|IΑΝ|ΦΕΒ|ΜΆΡ|ΜΑΡ|ΑΠΡ|ΆΠΡ|AΠΡ|AΡΙΛ|ΆΡΙΛ|ΑΡΙΛ|ΜΑΪ́|ΜΑΙ|ΜΆΙ|ΜΑΪ|ΜΆΪ|ΙΟΎΝ|ΊΟΎΝ|ΊΟΥΝ|IΟΎΝ|ΙΟΥΝ|IΟΥΝ|ΙΟΎΛ|ΊΟΎΛ|ΊΟΥΛ|IΟΎΛ|ΙΟΥΛ|IΟΥΛ|ΑΎΓ|ΑΥΓ|ΣΕΠ|ΟΚΤ|ΌΚΤ|OΚΤ|ΝΟΈ|ΝΟΕ|ΔΕΚ|Ιαν|Ίαν|Iαν|Φεβ|Μάρ|Μαρ|Απρ|Άπρ|Aπρ|Αρίλ|Άρίλ|Aρίλ|Aριλ|Άριλ|Αριλ|Μαΐ|Μαι|Μάι|Μαϊ|Μάϊ|Ιούν|Ίούν|Ίουν|Iούν|Ιουν|Iουν|Ιούλ|Ίούλ|Ίουλ|Iούλ|Ιουλ|Iουλ|Αύγ|Αυγ|Σεπ|Οκτ|Όκτ|Oκτ|Νοέ|Νοε|Δεκ)[^0-9]+([0-9]{1,2}|[0-9]{4})\s*$")
daymonthyearEnPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)[^0-9]+([0-9]{4}|[0-9]{1,2})\s*$")
monthdayyearEnPattern = RePattern(r"^\s*(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)[^0-9]+([0-9]+)[^0-9]+([0-9]{4}|[0-9]{1,2})\s*$")
daymonthyearEsPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic|ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC|Ene|Feb|Mar|Abr|May|Jun|Jul|Ago|Sep|Oct|Nov|Dic)[^0-9]+([0-9]{1,2}|[0-9]{4})\s*$")
daymonthyearEtPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(jaan|veebr|märts|marts|apr|mai|juuni|juuli|aug|sept|okt|nov|dets|JAAN|VEEBR|MÄRTS|MARTS|APR|MAI|JUUNI|JUULI|AUG|SEPT|OKT|NOV|DETS|Jaan|Veebr|Märts|Marts|Apr|Mai|Juuni|Juuli|Aug|Sept|Okt|Nov|Dets)[^0-9]+([0-9]{1,2}|[0-9]{4})\s*$")
daymonthyearFiPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]*[^0-9a-zA-Z]+(tam|hel|maa|huh|tou|kes|hei|elo|syy|lok|mar|jou|TAM|HEL|MAA|HUH|TOU|KES|HEI|ELO|SYY|LOK|MAR|JOU|Tam|Hel|Maa|Huh|Tou|Kes|Hei|Elo|Syy|Lok|Mar|Jou)[^0-9]+([0-9]{1,2}|[0-9]{4})\s*$")
daymonthyearFrPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(janv|févr|fevr|mars|avr|mai|juin|juil|août|aout|sept|oct|nov|déc|dec|JANV|FÉVR|FEVR|MARS|AVR|MAI|JUIN|JUIL|AOÛT|AOUT|SEPT|OCT|NOV|DÉC|DEC|Janv|Févr|Fevr|Mars|Avr|Mai|Juin|Juil|Août|Aout|Sept|Oct|Nov|Déc|Dec)[^0-9]+([0-9]{1,2}|[0-9]{4})\s*$")
daymonthyearHrPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(sij|velj|ožu|ozu|tra|svi|lip|srp|kol|ruj|lis|stu|pro|SIJ|VELJ|OŽU|OZU|TRA|SVI|LIP|SRP|KOL|RUJ|LIS|STU|PRO|Sij|Velj|Ožu|Ozu|Tra|Svi|Lip|Srp|Kol|Ruj|Lis|Stu|Pro)[^0-9]+([0-9]{1,2}|[0-9]{4})\s*$")
yearmonthdayHuPattern = RePattern(r"^\s*([0-9]{1,2}|[0-9]{4})[^0-9]+(jan|feb|márc|marc|ápr|apr|máj|maj|jún|jun|júl|jul|aug|szept|okt|nov|dec|JAN|FEB|MÁRC|MARC|ÁPR|APR|MÁJ|MAJ|JÚN|JUN|JÚL|JUL|AUG|SZEPT|OKT|NOV|DEC|Jan|Feb|Márc|Marc|Ápr|Apr|Máj|Maj|Jún|Jun|Júl|Jul|Aug|Szept|Okt|Nov|Dec)[^0-9]+([0-9]{1,2})\s*$")
daymonthyearInPattern = RePattern(r"^\s*([0-9\u0966-\u096F]{1,2})\s([\u0966-\u096F]{2}|[^\s0-9\u0966-\u096F]+)\s([0-9\u0966-\u096F]{2}|[0-9\u0966-\u096F]{4})\s*$")
daymonthyearItPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(gen|feb|mar|apr|mag|giu|lug|ago|set|ott|nov|dic|GEN|FEB|MAR|APR|MAG|GIU|LUG|AGO|SET|OTT|NOV|DIC|Gen|Feb|Mar|Apr|Mag|Giu|Lug|Ago|Set|Ott|Nov|Dic)[^0-9]+([0-9]{1,2}|[0-9]{4})\s*$")
yearmonthdayLtPattern = RePattern(r"^\s*([0-9]{1,2}|[0-9]{4})[^0-9]*[^0-9a-zA-Z]+(sau|vas|kov|bal|geg|bir|lie|rugp|rgp|rugs|rgs|spa|spl|lap|gru|grd|SAU|VAS|KOV|BAL|GEG|BIR|LIE|RUGP|RGP|RUGS|RGS|SPA|SPL|LAP|GRU|GRD|Sau|Vas|Kov|Bal|Geg|Bir|Lie|Rugp|Rgp|Rugs|Rgs|Spa|Spl|Lap|Gru|Grd)[^0-9]+([0-9]{1,2})[^0-9]*\s*$")
yeardaymonthLvPattern = RePattern(r"^\s*([0-9]{1,2}|[0-9]{4})[^0-9]+([0-9]{1,2})[^0-9]+(janv|febr|marts|apr|maijs|jūn|jun|jūl|jul|aug|sept|okt|nov|dec|JANV|FEBR|MARTS|APR|MAIJS|JŪN|JUN|JŪL|JUL|AUG|SEPT|OKT|NOV|DEC|Janv|Febr|Marts|Apr|Maijs|Jūn|Jun|Jūl|Jul|Aug|Sept|Okt|Nov|Dec)[^0-9]*\s*$")
daymonthyearNlPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(jan|feb|maa|mrt|apr|mei|jun|jul|aug|sep|okt|nov|dec|JAN|FEB|MAA|MRT|APR|MEI|JUN|JUL|AUG|SEP|OKT|NOV|DEC|Jan|Feb|Maa|Mrt|Apr|Mei|Jun|Jul|Aug|Sep|Okt|Nov|Dec)[^0-9]+([0-9]{1,2}|[0-9]{4})\s*$")
daymonthyearNoPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(jan|feb|mar|apr|mai|jun|jul|aug|sep|okt|nov|des|JAN|FEB|MAR|APR|MAI|JUN|JUL|AUG|SEP|OKT|NOV|DES|Jan|Feb|Mar|Apr|Mai|Jun|Jul|Aug|Sep|Okt|Nov|Des)[^0-9]+([0-9]{1,2}|[0-9]{4})\s*$")
daymonthyearPlPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]*[^0-9a-zA-Z]+(sty|lut|mar|kwi|maj|cze|lip|sie|wrz|paź|paz|lis|gru|STY|LUT|MAR|KWI|MAJ|CZE|LIP|SIE|WRZ|PAŹ|PAZ|LIS|GRU|Sty|Lut|Mar|Kwi|Maj|Cze|Lip|Sie|Wrz|Paź|Paz|Lis|Gru)[^0-9]+([0-9]{1,2}|[0-9]{4})[^0-9]*\s*$")
daymonthyearPtPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez|JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ|Jan|Fev|Mar|Abr|Mai|Jun|Jul|Ago|Set|Out|Nov|Dez)[^0-9]+([0-9]{1,2}|[0-9]{4})\s*$")
daymonthyearRomanPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]*[^XVIxvi]((I?(X|V|I)I{0,3})|(i?(x|v|i)i{0,3}))[^XVIxvi][^0-9]*([0-9]{1,2}|[0-9]{4})\s*$")
daymonthyearRoPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(ian|feb|mar|apr|mai|iun|iul|aug|sep|oct|noi|nov|dec|IAN|FEB|MAR|APR|MAI|IUN|IUL|AUG|SEP|OCT|NOI|NOV|DEC|Ian|Feb|Mar|Apr|Mai|Iun|Iul|Aug|Sep|Oct|Noi|Nov|Dec)[^0-9]+([0-9]{1,2}|[0-9]{4})\s*$")
daymonthyearSkPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(jan|feb|mar|apr|máj|maj|jún|jun|júl|jul|aug|sep|okt|nov|dec|JAN|FEB|MAR|APR|MÁJ|MAJ|JÚN|JUN|JÚL|JUL|AUG|SEP|OKT|NOV|DEC|Jan|Feb|Mar|Apr|Máj|Maj|Jún|Jun|Júl|Jul|Aug|Sep|Okt|Nov|Dec)[^0-9]+([0-9]{1,2}|[0-9]{4})\s*$")
daymonthyearSlPattern = RePattern(r"^\s*([0-9]{1,2})[^0-9]+(jan|feb|mar|apr|maj|jun|jul|avg|sep|okt|nov|dec|JAN|FEB|MAR|APR|MAJ|JUN|JUL|AVG|SEP|OKT|NOV|DEC|Jan|Feb|Mar|Apr|Maj|Jun|Jul|Avg|Sep|Okt|Nov|Dec)[^0-9]+([0-9]{1,2}|[0-9]{4})\s*$")
monthyearBgPattern = RePattern(r"^\s*(ян|фев|мар|апр|май|маи|юни|юли|авг|сеп|окт|ное|дек|ЯН|ФЕВ|МАР|АПР|МАЙ|МАИ|ЮНИ|ЮЛИ|АВГ|СЕП|ОКТ|НОЕ|ДЕК|Ян|Фев|Мар|Апр|Май|Маи|Юни|Юли|Авг|Сеп|Окт|Ное|Дек)[^0-9]+([0-9]{1,2}|[0-9]{4})[^0-9]*\s*$")
monthyearCsPattern = RePattern(r"^\s*(leden|únor|unor|březen|brezen|duben|květen|kveten|červen|cerven|červenec|cervenec|srpen|září|zari|říjen|rijen|listopad|prosinec|led|úno|uno|bře|bre|dub|kvě|kve|čvn|cvn|čvc|cvc|srp|zář|zar|říj|rij|lis|pro|LEDEN|ÚNOR|UNOR|BŘEZEN|BREZEN|DUBEN|KVĚTEN|KVETEN|ČERVEN|CERVEN|ČERVENEC|CERVENEC|SRPEN|ZÁŘÍ|ZARI|ŘÍJEN|RIJEN|LISTOPAD|PROSINEC|LED|ÚNO|UNO|BŘE|BRE|DUB|KVĚ|KVE|ČVN|CVN|ČVC|CVC|SRP|ZÁŘ|ZAR|ŘÍJ|RIJ|LIS|PRO|Leden|Únor|Unor|Březen|Brezen|Duben|Květen|Kveten|Červen|Cerven|Červenec|Cervenec|Srpen|Září|Zari|Říjen|Rijen|Listopad|Prosinec|Led|Úno|Uno|Bře|Bre|Dub|Kvě|Kve|Čvn|Cvn|Čvc|Cvc|Srp|Zář|Zar|Říj|Rij|Lis|Pro)[^0-9a-zA-Z]+[^0-9]*([0-9]{1,2}|[0-9]{4})\s*$")
monthyearDePattern = RePattern(r"^\s*(jan|jän|jaen|feb|mär|maer|mar|apr|mai|jun|jul|aug|sep|okt|nov|dez|JAN|JÄN|JAEN|FEB|MÄR|MAER|MAR|APR|MAI|JUN|JUL|AUG|SEP|OKT|NOV|DEZ|Jan|Jän|Jaen|Feb|Mär|Maer|Mar|Apr|Mai|Jun|Jul|Aug|Sep|Okt|Nov|Dez)[^0-9]+([0-9]{1,2}|[0-9]{4})\s*$")
monthyearDkPattern = RePattern(r"^\s*(jan|feb|mar|apr|maj|jun|jul|aug|sep|okt|nov|dec)([A-Za-z]*)([.]*)[^0-9]*([0-9]{4}|[0-9]{1,2})\s*$", re.IGNORECASE)
monthyearElPattern = RePattern(r"^\s*(ιαν|ίαν|φεβ|μάρ|μαρ|απρ|άπρ|αρίλ|άρίλ|αριλ|άριλ|μαΐ|μαι|μάι|μαϊ|μάϊ|ιούν|ίούν|ίουν|ιουν|ιούλ|ίούλ|ίουλ|ίουλ|ιουλ|αύγ|αυγ|σεπ|οκτ|όκτ|νοέ|νοε|δεκ|ΙΑΝ|ΊΑΝ|IΑΝ|ΦΕΒ|ΜΆΡ|ΜΑΡ|ΑΠΡ|ΆΠΡ|AΠΡ|AΡΙΛ|ΆΡΙΛ|ΑΡΙΛ|ΜΑΪ́|ΜΑΙ|ΜΆΙ|ΜΑΪ|ΜΆΪ|ΙΟΎΝ|ΊΟΎΝ|ΊΟΥΝ|IΟΎΝ|ΙΟΥΝ|IΟΥΝ|ΙΟΎΛ|ΊΟΎΛ|ΊΟΥΛ|IΟΎΛ|ΙΟΥΛ|IΟΥΛ|ΑΎΓ|ΑΥΓ|ΣΕΠ|ΟΚΤ|ΌΚΤ|OΚΤ|ΝΟΈ|ΝΟΕ|ΔΕΚ|Ιαν|Ίαν|Iαν|Φεβ|Μάρ|Μαρ|Απρ|Άπρ|Aπρ|Αρίλ|Άρίλ|Aρίλ|Aριλ|Άριλ|Αριλ|Μαΐ|Μαι|Μάι|Μαϊ|Μάϊ|Ιούν|Ίούν|Ίουν|Iούν|Ιουν|Iουν|Ιούλ|Ίούλ|Ίουλ|Iούλ|Ιουλ|Iουλ|Αύγ|Αυγ|Σεπ|Οκτ|Όκτ|Oκτ|Νοέ|Νοε|Δεκ)[^0-9]+([0-9]{1,2}|[0-9]{4})\s*$")
monthyearEnPattern = RePattern(r"^\s*(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)[^0-9]+([0-9]{1,2}|[0-9]{4})\s*$")
yearmonthEnPattern = RePattern(r"^\s*([0-9]{1,2}|[0-9]{4})[^0-9]+(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s*$")
monthyearEsPattern = RePattern(r"^\s*(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic|ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC|Ene|Feb|Mar|Abr|May|Jun|Jul|Ago|Sep|Oct|Nov|Dic)[^0-9]+([0-9]{1,2}|[0-9]{4})\s*$")
monthyearEtPattern = RePattern(r"^\s*(jaan|veebr|märts|marts|apr|mai|juuni|juuli|aug|sept|okt|nov|dets|JAAN|VEEBR|MÄRTS|MARTS|APR|MAI|JUUNI|JUULI|AUG|SEPT|OKT|NOV|DETS|Jaan|Veebr|Märts|Marts|Apr|Mai|Juuni|Juuli|Aug|Sept|Okt|Nov|Dets)[^0-9]+([0-9]{1,2}|[0-9]{4})\s*$")
monthyearFiPattern = RePattern(r"^\s*(tam|hel|maa|huh|tou|kes|hei|elo|syy|lok|mar|jou|TAM|HEL|MAA|HUH|TOU|KES|HEI|ELO|SYY|LOK|MAR|JOU|Tam|Hel|Maa|Huh|Tou|Kes|Hei|Elo|Syy|Lok|Mar|Jou)[^0-9]+([0-9]{1,2}|[0-9]{4})\s*$")
monthyearFrPattern = RePattern(r"^\s*(janv|févr|fevr|mars|avr|mai|juin|juil|août|aout|sept|oct|nov|déc|dec|JANV|FÉVR|FEVR|MARS|AVR|MAI|JUIN|JUIL|AOÛT|AOUT|SEPT|OCT|NOV|DÉC|DEC|Janv|Févr|Fevr|Mars|Avr|Mai|Juin|Juil|Août|Aout|Sept|Oct|Nov|Déc|Dec)[^0-9]+([0-9]{1,2}|[0-9]{4})\s*$")
monthyearHrPattern = RePattern(r"^\s*(sij|velj|ožu|ozu|tra|svi|lip|srp|kol|ruj|lis|stu|pro|SIJ|VELJ|OŽU|OZU|TRA|SVI|LIP|SRP|KOL|RUJ|LIS|STU|PRO|Sij|Velj|Ožu|Ozu|Tra|Svi|Lip|Srp|Kol|Ruj|Lis|Stu|Pro)[^0-9]+([0-9]{1,2}|[0-9]{4})\s*$")
yearmonthHuPattern = RePattern(r"^\s*([0-9]{1,2}|[0-9]{4})[^0-9]+(jan|feb|márc|marc|ápr|apr|máj|maj|jún|jun|júl|jul|aug|szept|okt|nov|dec|JAN|FEB|MÁRC|MARC|ÁPR|APR|MÁJ|MAJ|JÚN|JUN|JÚL|JUL|AUG|SZEPT|OKT|NOV|DEC|Jan|Feb|Márc|Marc|Ápr|Apr|Máj|Maj|Jún|Jun|Júl|Jul|Aug|Szept|Okt|Nov|Dec)[^0-9]{0,7}\s*$")
monthyearItPattern = RePattern(r"^\s*(gen|feb|mar|apr|mag|giu|lug|ago|set|ott|nov|dic|GEN|FEB|MAR|APR|MAG|GIU|LUG|AGO|SET|OTT|NOV|DIC|Gen|Feb|Mar|Apr|Mag|Giu|Lug|Ago|Set|Ott|Nov|Dic)[^0-9]+([0-9]{1,2}|[0-9]{4})\s*$")
monthyearInPattern = RePattern(r"^\s*([^\s0-9\u0966-\u096F]+)\s([0-9\u0966-\u096F]{4})\s*$")
yearmonthLtPattern = RePattern(r"^\s*([0-9]{1,2}|[0-9]{4})[^0-9]*[^0-9a-zA-Z]+(sau|vas|kov|bal|geg|bir|lie|rugp|rgp|rugs|rgs|spa|spl|lap|gru|grd|SAU|VAS|KOV|BAL|GEG|BIR|LIE|RUGP|RGP|RUGS|RGS|SPA|SPL|LAP|GRU|GRD|Sau|Vas|Kov|Bal|Geg|Bir|Lie|Rugp|Rgp|Rugs|Rgs|Spa|Spl|Lap|Gru|Grd)[^0-9]*\s*$")
yearmonthLvPattern = RePattern(r"^\s*([0-9]{1,2}|[0-9]{4})[^0-9]+(janv|febr|marts|apr|maijs|jūn|jun|jūl|jul|aug|sept|okt|nov|dec|JANV|FEBR|MARTS|APR|MAIJS|JŪN|JUN|JŪL|JUL|AUG|SEPT|OKT|NOV|DEC|Janv|Febr|Marts|Apr|Maijs|Jūn|Jun|Jūl|Jul|Aug|Sept|Okt|Nov|Dec)[^0-9]{0,7}\s*$")
monthyearNlPattern = RePattern(r"^\s*(jan|feb|maa|mrt|apr|mei|jun|jul|aug|sep|okt|nov|dec|JAN|FEB|MAA|MRT|APR|MEI|JUN|JUL|AUG|SEP|OKT|NOV|DEC|Jan|Feb|Maa|Mrt|Apr|Mei|Jun|Jul|Aug|Sep|Okt|Nov|Dec)[^0-9]+([0-9]{1,2}|[0-9]{4})\s*$")
monthyearNoPattern = RePattern(r"^\s*(jan|feb|mar|apr|mai|jun|jul|aug|sep|okt|nov|des|JAN|FEB|MAR|APR|MAI|JUN|JUL|AUG|SEP|OKT|NOV|DES|Jan|Feb|Mar|Apr|Mai|Jun|Jul|Aug|Sep|Okt|Nov|Des)[^0-9]+([0-9]{1,2}|[0-9]{4})\s*$")
monthyearPlPattern = RePattern(r"^\s*(sty|lut|mar|kwi|maj|cze|lip|sie|wrz|paź|paz|lis|gru|STY|LUT|MAR|KWI|MAJ|CZE|LIP|SIE|WRZ|PAŹ|PAZ|LIS|GRU|Sty|Lut|Mar|Kwi|Maj|Cze|Lip|Sie|Wrz|Paź|Paz|Lis|Gru)[^0-9]+([0-9]{1,2}|[0-9]{4})[^0-9]*\s*$")
monthyearPtPattern = RePattern(r"^\s*(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez|JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ|Jan|Fev|Mar|Abr|Mai|Jun|Jul|Ago|Set|Out|Nov|Dez)[^0-9]+([0-9]{1,2}|[0-9]{4})\s*$")
monthyearRomanPattern = RePattern(r"^\s*((I?(X|V|I)I{0,3})|(i?(x|v|i)i{0,3}))[^XVIxvi][^0-9]*([0-9]{1,2}|[0-9]{4})\s*$")
monthyearRoPattern = RePattern(r"^\s*(ian|feb|mar|apr|mai|iun|iul|aug|sep|oct|noi|nov|dec|IAN|FEB|MAR|APR|MAI|IUN|IUL|AUG|SEP|OCT|NOI|NOV|DEC|Ian|Feb|Mar|Apr|Mai|Iun|Iul|Aug|Sep|Oct|Noi|Nov|Dec)[^0-9]+([0-9]{1,2}|[0-9]{4})\s*$")
monthyearSkPattern = RePattern(r"^\s*(jan|feb|mar|apr|máj|maj|jún|jun|júl|jul|aug|sep|okt|nov|dec|JAN|FEB|MAR|APR|MÁJ|MAJ|JÚN|JUN|JÚL|JUL|AUG|SEP|OKT|NOV|DEC|Jan|Feb|Mar|Apr|Máj|Maj|Jún|Jun|Júl|Jul|Aug|Sep|Okt|Nov|Dec)[^0-9]+([0-9]{1,2}|[0-9]{4})\s*$")
monthyearSlPattern = RePattern(r"^\s*(jan|feb|mar|apr|maj|jun|jul|avg|sep|okt|nov|dec|JAN|FEB|MAR|APR|MAJ|JUN|JUL|AVG|SEP|OKT|NOV|DEC|Jan|Feb|Mar|Apr|Maj|Jun|Jul|Avg|Sep|Okt|Nov|Dec)[^0-9]+([0-9]{1,2}|[0-9]{4})\s*$")

# TR1-only patterns, only allow space separators, no all-CAPS month name, only 2 or 4 digit years
dateLongUkTR1Pattern = RePattern(r"^\s*(\d|\d{2,2}) (January|February|March|April|May|June|July|August|September|October|November|December) (\d{2,2}|\d{4,4})\s*$")
dateShortUkTR1Pattern = RePattern(r"^\s*(\d|\d{2,2}) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d{2,2}|\d{4,4})\s*$")
dateLongUsTR1Pattern = RePattern(r"^\s*(January|February|March|April|May|June|July|August|September|October|November|December) (\d|\d{2,2}), (\d{2,2}|\d{4,4})\s*$")
dateShortUsTR1Pattern = RePattern(r"^\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d|\d{2,2}), (\d{2,2}|\d{4,4})\s*$")
daymonthLongEnTR1Pattern = RePattern(r"^\s*(\d|\d{2,2}) (January|February|March|April|May|June|July|August|September|October|November|December)\s*$")
daymonthShortEnTR1Pattern = RePattern(r"^\s*([0-9]{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*$")
monthdayLongEnTR1Pattern = RePattern(r"^\s*(January|February|March|April|May|June|July|August|September|October|November|December) (\d|\d{2,2})\s*$")
monthdayShortEnTR1Pattern = RePattern(r"^\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+([0-9]{1,2})[A-Za-z]{0,2}\s*$")
monthyearShortEnTR1Pattern = RePattern(r"^\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+([0-9]{2}|[0-9]{4})\s*$")
monthyearLongEnTR1Pattern = RePattern(r"^\s*(January|February|March|April|May|June|July|August|September|October|November|December)\s+([0-9]{2}|[0-9]{4})\s*$")
yearmonthShortEnTR1Pattern = RePattern(r"^\s*([0-9]{2}|[0-9]{4})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*$")
yearmonthLongEnTR1Pattern = RePattern(r"^\s*([0-9]{2}|[0-9]{4})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s*$")

erayearmonthjpPattern = RePattern(r"^[\s ]*(明治|明|大正|大|昭和|昭|平成|平|新号|新)[\s ]*([0-9０-９]{1,2}|元)[\s ]*(年)[\s ]*([0-9０-９]{1,2})[\s ]*(月)[\s ]*$")
erayearmonthdayjpPattern = RePattern(r"^[\s ]*(明治|明|大正|大|昭和|昭|平成|平|新号|新)[\s ]*([0-9０-９]{1,2}|元)[\s ]*(年)[\s ]*([0-9０-９]{1,2})[\s ]*(月)[\s ]*([0-9０-９]{1,2})[\s ]*(日)[\s ]*$")
yearmonthcjkPattern = RePattern(r"^[\s ]*([0-9０-９]{1,2}|[0-9０-９]{4})[\s ]*(年)[\s ]*([0-9０-９]{1,2})[\s ]*(月)[\s ]*$")
yearmonthdaycjkPattern = RePattern(r"^[\s ]*([0-9０-９]{1,2}|[0-9０-９]{4})[\s ]*(年)[\s ]*([0-9０-９]{1,2})[\s ]*(月)[\s ]*([0-9０-９]{1,2})[\s ]*(日)[\s ]*$")

monthyearPattern = RePattern("^[\\s\u00A0]*([0-9]{1,2})[^0-9]+([0-9]{4}|[0-9]{1,2})[\\s\u00A0]*$")
yearmonthdayPattern = RePattern("^[\\s\u00A0]*([0-9]{4}|[0-9]{1,2})[^0-9]+([0-9]{1,2})[^0-9]+([0-9]{1,2})[\\s\u00A0]*$")

zeroDashPattern = RePattern(r"^\s*([-]|\u002D|\u002D|\u058A|\u05BE|\u2010|\u2011|\u2012|\u2013|\u2014|\u2015|\uFE58|\uFE63|\uFF0D)\s*$")
numDotDecimalPattern = RePattern(r"^\s*[0-9]{1,3}([, \xA0]?[0-9]{3})*(\.[0-9]+)?\s*$")
numDotDecimalTR4Pattern = RePattern(r"^\s*([0-9]{1,3}([, \xA0]?[0-9]{3})*(\.[0-9]+)?|\.[0-9]+)\s*$")
numDotDecimalInPattern = RePattern(r"^(([0-9]{1,2}[, \xA0])?([0-9]{2}[, \xA0])*[0-9]{3})([.][0-9]+)?$|^([0-9]+)([.][0-9]+)?$")
numCommaDecimalPattern = RePattern(r"^\s*[0-9]{1,3}([. \xA0]?[0-9]{3})*(,[0-9]+)?\s*$")
numUnitDecimalPattern = RePattern(r"^([0]|([1-9][0-9]{0,2}([.,\uFF0C\uFF0E]?[0-9]{3})*))[^0-9,.\uFF0C\uFF0E]+([0-9]{1,2})[^0-9,.\uFF0C\uFF0E]*$")
numUnitDecimalInPattern = RePattern(r"^(([0-9]{1,2}[, \xA0])?([0-9]{2}[, \xA0])*[0-9]{3})([^0-9]+)([0-9]{1,2})([^0-9]*)$|^([0-9]+)([^0-9]+)([0-9]{1,2})([^0-9]*)$")
numCommaPattern = RePattern(r"^\s*[0-9]+(,[0-9]+)?\s*$")
numCommaDotPattern = RePattern(r"^\s*[0-9]{1,3}(,[0-9]{3,3})*([.][0-9]+)?\s*$")
numDashPattern = RePattern(r"^\s*-\s*$")
numDotCommaPattern = RePattern(r"^\s*[0-9]{1,3}([.][0-9]{3,3})*(,[0-9]+)?\s*$")
numSpaceDotPattern = RePattern(r"^\s*[0-9]{1,3}([ \xA0][0-9]{3,3})*([.][0-9]+)?\s*$")
numSpaceCommaPattern = RePattern(r"^\s*[0-9]{1,3}([ \xA0][0-9]{3,3})*(,[0-9]+)?\s*$")

monthnumber = {# english
               "january":1, "february":2, "march":3, "april":4, "may":5, "june":6, 
               "july":7, "august":8, "september":9, "october":10, "november":11, "december":12, 
               "jan":1, "feb":2, "mar":3, "apr":4, "may":5, "jun":6, 
               "jul":7, "aug":8, "sep":9, "oct":10, "nov":11, "dec":12, 
               # bulgarian
               "ян":1, "фев":2, "мар":3, "апр":4, "май":5, "маи":5, "юни":6,
               "юли":7, "авг":8, "сеп":9, "окт":10, "ное":11, "дек":12,
               # danish
               "jan":1, "feb":2, "mar": 3, "apr":4, "maj":5, "jun":6,
               "jul":7, "aug":8, "sep":9, "okt":10, "nov":11, "dec":12,
               # de: german
               "jan":1, "jän":1, "jaen":1, "feb":2, "mär":3, "maer":3, "mar":3,"apr":4, 
               "mai":5, "jun":6, "jul":7, "aug":8, "sep":9, "okt":10, "nov":11, "dez":12,
               # el: greek
               "ιαν":1, "ίαν":1, "φεβ":2, "μάρ":3, "μαρ":3, "απρ":4, "άπρ":4, "αρίλ":4, "άρίλ":4, 
               "αριλ":4, "άριλ":4, "μαΐ":5, "μαι":5, "μάι":5, "μαϊ":5, "μάϊ":5, "ιούν":6, "ίούν":6, 
               "ίουν":6, "ιουν":6, "ιούλ":7, "ίούλ":7, "ίουλ":7, "ίουλ":7, "ιουλ":7, "αύγ":8, "αυγ":8, 
               "σεπ":9, "οκτ":10, "όκτ":10, "νοέ":11, "νοε":11, "δεκ":12,
               # es: spanish (differences)
               "ene":1, "abr":4, "ago":8, "dic":12,
               # et: estonian (differences)
               "jaan":1, "veebr":2, "märts":3, "marts":3, "mai":5, "juuni":6, "juuli":7, "sept":9, "okt":10, "dets":12,
               # fr: french (differences)
               "janv":1, "févr":2, "fevr":2, "mars":3, "avr":4, "mai":5, "juin":6, "juil":7, "août":8, "aout":8, "déc":12, 
               # hu: hungary (differences)
               "márc":3, "marc":3, "ápr":4, "máj":5, "maj":5, "jún":6, "jun":6, "júl":7, "jul":7, "szept":9, "okt":10, 
               # it: italy (differences)
               "gen":1, "mag":5, "giu":6, "lug":7, "ago":8, "set":9, "ott":10, "dic":12, 
               # lv: latvian (differences)
               "janv":1, "febr":2, "marts":3, "maijs":5, "jūn":6, "jūl":7, "okt":10,
               # nl: dutch (differences)
               "maa":3, "mrt":3, "mei":5, 
               # no: norway
               "mai":5, "des":12, 
               # pt: portugese (differences)
               "fev":2, "ago":8, "set":9, "out":10, "dez":12, 
               # ro: romanian (differences)
               "ian":1, "iul":7, "noi":11,
               # sk: skovak (differences)
               "máj":5, "maj":5, "jún":6, "júl":7, 
               # sl: sloveniabn
               "avg":8, 
               }

monthnumbercs = {"ledna":1, "leden":1, "února":2, "unora":2, "únor":2, "unor":2, 
                 "března":3, "brezna":3, "březen":3, "brezen":3, "dubna":4, "duben":4, 
                 "května":5, "kvetna":5, "květen":5, "kveten":5,
                "června":6, "cervna":6, "července":7, "cervence":7, 
                "červen":6, "cerven":6, "červenec":7, "cervenec":7, 
                "srpna":8, "srpen":8, "září":9, "zari":9, 
                "října":10, "rijna":10, "říjen":10, "rijen":10, "listopadu":11, "listopad":11, 
                "prosince":12, "prosinec":12,
                "led":1, "úno":2, "uno":2, "bře":3, "bre":3, "dub":4, "kvě":5, "kve":5,
                "čvn":6, "cvn":6, "čvc":7, "cvc":7, "srp":8, "zář":9, "zar":9,
                "říj":10, "rij":10, "lis":11, "pro":12
                }

monthnumberfi = {"tam":1, "hel":2, "maa":3, "huh":4, "tou":5, "kes":6, "hei":7, "elo":8, "syy":9, "lok":10, "mar":11, "jou":12}

monthnumberhr = {"sij":1, "velj":2, "ožu":3, "ozu":3, "tra":4, "svi":5, "lip":6, "srp":7, "kol":8, "ruj":9, "lis":10, "stu":11, "pro":12}

monthnumberlt = {"sau":1, "vas":2, "kov":3, "bal":4, "geg":5, "bir":6, "lie":7, "rugp":8, "rgp":8, "rugs":9, "rgs":9, "spa":10, "spl":10, "lap":11, "gru":12, "grd":12}

monthnumberpl = {"sty":1, "lut":2, "mar":3, "kwi":4, "maj":5, "cze":6, "lip":7, "sie":8, "wrz":9, "paź":10, "paz":10, "lis":11, "gru":12}

monthnumberroman = {"i":1, "ii":2, "iii":3, "iv":4, "v":5, "vi":6, "vii":7, "viii":8, "ix":9, "x":10, "xi":11, "xii":12}

maxDayInMo = {"01": "30", "02": "29", "03": "31", "04": "30", "05": "31", "06": "30",
              "07": "31", "08": "31", "09": "30", "10": "31", "11": "30", "12":"31",
              1: "30", 2: "29", 3: "31", 4: "30", 5: "31", 6: "30",
              7: "31", 8: "31", 9: "30", 10: "31", 11: "30", 12:"31"}
gLastMoDay = [31,28,31,30,31,30,31,31,30,31,30,31]

gregorianHindiMonthNumber = {
                "\u091C\u0928\u0935\u0930\u0940": "01",
                "\u092B\u0930\u0935\u0930\u0940": "02", 
                "\u092E\u093E\u0930\u094D\u091A": "03", 
                "\u0905\u092A\u094D\u0930\u0948\u0932": "04",
                "\u092E\u0908": "05", 
                "\u091C\u0942\u0928": "06",
                "\u091C\u0941\u0932\u093E\u0908": "07", 
                "\u0905\u0917\u0938\u094D\u0924": "08",
                "\u0938\u093F\u0924\u0902\u092C\u0930": "09",
                "\u0905\u0915\u094D\u0924\u0942\u092C\u0930": "10",
                "\u0928\u0935\u092E\u094D\u092C\u0930": "11",
                "\u0926\u093F\u0938\u092E\u094D\u092C\u0930": "12"
                }

sakaMonthNumber = {
                "Chaitra":1, "\u091A\u0948\u0924\u094D\u0930":1,
                "Vaisakha":2, "Vaishakh":2, "Vai\u015B\u0101kha":2, "\u0935\u0948\u0936\u093E\u0916":2, "\u092C\u0948\u0938\u093E\u0916":2,
                "Jyaishta":3, "Jyaishtha":3, "Jyaistha":3, "Jye\u1E63\u1E6Dha":3, "\u091C\u094D\u092F\u0947\u0937\u094D\u0920":3,
                "Asadha":4, "Ashadha":4, "\u0100\u1E63\u0101\u1E0Dha":4, "\u0906\u0937\u093E\u0922":4, "\u0906\u0937\u093E\u0922\u093C":4,
                "Sravana":5, "Shravana":5, "\u015Ar\u0101va\u1E47a":5, "\u0936\u094D\u0930\u093E\u0935\u0923":5, "\u0938\u093E\u0935\u0928":5,
                "Bhadra":6, "Bhadrapad":6, "Bh\u0101drapada":6, "Bh\u0101dra":6, "Pro\u1E63\u1E6Dhapada":6, "\u092D\u093E\u0926\u094D\u0930\u092A\u0926":6, "\u092D\u093E\u0926\u094B":6,
                "Aswina":7, "Ashwin":7, "Asvina":7, "\u0100\u015Bvina":7, "\u0906\u0936\u094D\u0935\u093F\u0928":7, 
                "Kartiak":8, "Kartik":8, "Kartika":8, "K\u0101rtika":8, "\u0915\u093E\u0930\u094D\u0924\u093F\u0915":8, 
                "Agrahayana":9,"Agrah\u0101ya\u1E47a":9,"Margashirsha":9, "M\u0101rga\u015B\u012Br\u1E63a":9, "\u092E\u093E\u0930\u094D\u0917\u0936\u0940\u0930\u094D\u0937":9, "\u0905\u0917\u0939\u0928":9,
                "Pausa":10, "Pausha":10, "Pau\u1E63a":10, "\u092A\u094C\u0937":10,
                "Magha":11, "Magh":11, "M\u0101gha":11, "\u092E\u093E\u0918":11,
                "Phalguna":12, "Phalgun":12, "Ph\u0101lguna":12, "\u092B\u093E\u0932\u094D\u0917\u0941\u0928":12,
                }
sakaMonthPattern = RePattern(r"(C\S*ait|\u091A\u0948\u0924\u094D\u0930)|"
                              r"(Vai|\u0935\u0948\u0936\u093E\u0916|\u092C\u0948\u0938\u093E\u0916)|"
                              r"(Jy|\u091C\u094D\u092F\u0947\u0937\u094D\u0920)|"
                              r"(dha|\u1E0Dha|\u0906\u0937\u093E\u0922|\u0906\u0937\u093E\u0922\u093C)|"
                              r"(vana|\u015Ar\u0101va\u1E47a|\u0936\u094D\u0930\u093E\u0935\u0923|\u0938\u093E\u0935\u0928)|"
                              r"(Bh\S+dra|Pro\u1E63\u1E6Dhapada|\u092D\u093E\u0926\u094D\u0930\u092A\u0926|\u092D\u093E\u0926\u094B)|"
                              r"(in|\u0906\u0936\u094D\u0935\u093F\u0928)|"
                              r"(K\S+rti|\u0915\u093E\u0930\u094D\u0924\u093F\u0915)|"
                              r"(M\S+rga|Agra|\u092E\u093E\u0930\u094D\u0917\u0936\u0940\u0930\u094D\u0937|\u0905\u0917\u0939\u0928)|"
                              r"(Pau|\u092A\u094C\u0937)|"
                              r"(M\S+gh|\u092E\u093E\u0918)|"
                              r"(Ph\S+lg|\u092B\u093E\u0932\u094D\u0917\u0941\u0928)")
sakaMonthLength = (30,31,31,31,31,31,30,30,30,30,30,30) # Chaitra has 31 days in Gregorian leap year
sakaMonthOffset = ((3,22,0),(4,21,0),(5,22,0),(6,22,0),(7,23,0),(8,23,0),(9,23,0),(10,23,0),(11,22,0),(12,22,0),(1,21,1),(2,20,1))

# common helper functions
def checkDate(y,m,d):
    try:
        datetime(_INT(y), _INT(m), _INT(d))
        return True
    except (ValueError):
        return False

def z2(arg):   # zero pad to 2 digits
    if len(arg) == 1:
        return '0' + arg
    return arg

def yr4(arg):   # zero pad to 4 digits
    if len(arg) == 1:
        return '200' + arg
    elif len(arg) == 2:
        return '20' + arg
    return arg

def yrin(arg, _mo, _day):   # zero pad to 4 digits
    if len(arg) == 2:
        if arg > '21' or (arg == '21' and _mo >= 10 and _day >= 11):
            return '19' + arg
        else:
            return '20' + arg
    return arg

def devanagariDigitsToNormal(devanagariDigits):
    normal = ''
    for d in devanagariDigits:
        if '\u0966' <= d <= '\u096F':
            normal += chr( ord(d) - 0x0966 + ord('0') )
        else:
            normal += d
    return normal

def jpDigitsToNormal(jpDigits):
    normal = ''
    for d in jpDigits:
        if '\uFF10' <= d <= '\uFF19':
            normal += chr( ord(d) - 0xFF10 + ord('0') )
        else:
            normal += d
    return normal

def sakaToGregorian(sYr, sMo, sDay): # replacement of plug-in sakaCalendar.py which is LGPL-v3 licensed
    gYr = sYr + 78  # offset from Saka to Gregorian year
    sStartsInLeapYr = gYr % 4 == 0 and (not gYr % 100 == 0 or gYr % 400 == 0) # Saka yr starts in leap yr
    if gYr < 0:
        raise ValueError(_("Saka calendar year not supported: {0} {1} {2} "), sYr, sMo, sDay)
    if  sMo < 1 or sMo > 12:
        raise ValueError(_("Saka calendar month error: {0} {1} {2} "), sYr, sMo, sDay)
    sMoLength = sakaMonthLength[sMo - 1]
    if sStartsInLeapYr and sMo == 1:
        sMoLength += 1 # Chaitra has 1 extra day when starting in gregorian leap years
    if sDay < 1 or sDay > sMoLength: 
        raise ValueError(_("Saka calendar day error: {0} {1} {2} "), sYr, sMo, sDay)
    gMo, gDayOffset, gYrOffset = sakaMonthOffset[sMo - 1] # offset Saka to Gregorian by Saka month
    if sStartsInLeapYr and sMo == 1:
        gDayOffset -= 1 # Chaitra starts 1 day earlier when starting in Gregorian leap years
    gYr += gYrOffset # later Saka months offset into next Gregorian year
    gMoLength = gLastMoDay[gMo - 1] # month length (days in month)
    if gMo == 2 and gYr % 4 == 0 and (not gYr % 100 == 0 or gYr % 400 == 0): # does Phalguna (Feb) end in a Gregorian leap year?
        gMoLength += 1 # Phalguna (Feb) is in a Gregorian leap year (Feb has 29 days)
    gDay = gDayOffset + sDay - 1
    if gDay > gMoLength: # overflow from Gregorial month of start of Saka month to next Gregorian month
        gDay -= gMoLength
        gMo += 1
        if gMo == 13:  # overflow from Gregorian year of start of Saka year to following Gregorian year
            gMo = 1
            gYr += 1
    return (gYr, gMo, gDay)

# see: http://www.i18nguy.com/l10n/emperor-date.html        
eraStart = {'新号': 2018,
            '新': 2018,
            '\u5E73\u6210': 1988, 
            '\u5E73': 1988,
            '\u660E\u6CBB': 1867,
            '\u660E': 1867,
            '\u5927\u6B63': 1911,
            '\u5927': 1911,
            '\u662D\u548C': 1925,
            '\u662D': 1925
            }

def eraYear(era,yr):
    return eraStart[era] + (1 if yr == '元' else _INT(yr))

# transforms    

def booleanfalse(arg):
    return 'false'
    
def booleantrue(arg):
    return 'true'

def dateslashus(arg):
    m = dateslashPattern.match(arg)
    if m and m.lastindex == 3:
        return "{0}-{1}-{2}".format(yr4(m.group(3)), z2(m.group(1)), z2(m.group(2)))
    raise XPathContext.FunctionArgType(0,"xs:date")
    
def dateslasheu(arg):
    m = dateslashPattern.match(arg)
    if m and m.lastindex == 3:
        return "{0}-{1}-{2}".format(yr4(m.group(3)), z2(m.group(2)), z2(m.group(1)))
    raise XPathContext.FunctionArgType(0,"xs:date")
    
def datedotus(arg):
    m = datedotPattern.match(arg)
    if m and m.lastindex == 3:
        return "{0}-{1}-{2}".format(yr4(m.group(3)), z2(m.group(1)), z2(m.group(2)))
    raise XPathContext.FunctionArgType(0,"xs:date")
    
def datedoteu(arg):
    m = datedotPattern.match(arg)
    if m and m.lastindex == 3:
        return "{0}-{1}-{2}".format(yr4(m.group(3)), z2(m.group(2)), z2(m.group(1)))
    raise XPathContext.FunctionArgType(0,"xs:date")
    
def datelongusTR1(arg):
    return datedaymonthyear(arg, dateLongUsTR1Pattern, dy=2, mo=1, yr=3)
    
def dateshortusTR1(arg):
    return datedaymonthyear(arg, dateShortUsTR1Pattern, dy=2, mo=1, yr=3)
    
def datelongukTR1(arg):
    return datedaymonthyear(arg, dateLongUkTR1Pattern)

def dateshortukTR1(arg):
    return datedaymonthyear(arg, dateShortUkTR1Pattern)
    
def datelongeu(arg):
    return datedaymonthyear(arg, dateEuPattern)
    
def datedaymonthTR2(arg):
    m = daymonthPattern.match(arg)
    if m and m.lastindex == 2:
        mo = z2(m.group(2))
        day = z2(m.group(1))
        if "01" <= day <= maxDayInMo.get(mo, "00"): 
            return "--{0}-{1}".format(mo, day)
    raise XPathContext.FunctionArgType(0,"xs:gMonthDay")
    
def datemonthday(arg):
    m = monthdayPattern.match(arg)
    if m and m.lastindex == 2:
        mo = z2(m.group(1))
        day = z2(m.group(2))
        if "01" <= day <= maxDayInMo.get(mo, "00"): 
            return "--{0}-{1}".format(mo, day)
    raise XPathContext.FunctionArgType(0,"xs:gMonthDay")
    
def datedaymonthSlashTR1(arg):
    return datedaymonth(arg, daymonthslashPattern)
    m = daymonthslashPattern.match(arg)
    if m and m.lastindex == 2:
        mo = z2(m.group(2))
        day = z2(m.group(1))
        return "--{0}-{1}".format(mo, day)
    raise XPathContext.FunctionArgType(0,"xs:gMonthDay")
    
def datemonthdaySlashTR1(arg):
    m = monthdayslashPattern.match(arg)
    if m and m.lastindex == 2:
        mo = z2(m.group(1))
        day = z2(m.group(2))
        return "--{0}-{1}".format(mo, day)
    raise XPathContext.FunctionArgType(0,"xs:gMonthDay")

def datedaymonth(arg, pattern, moTbl=monthnumber, dy=1, mo=2, lastindex=2):
    m = pattern.match(arg)
    try:
        if m and m.lastindex == lastindex:
            _day = z2(m.group(dy))
            _mo = m.group(mo)
            _mo = moTbl[_mo.lower()] if moTbl else int(_mo)
            if "01" <= _day <= maxDayInMo.get(_mo, "00"):
                return "--{0:02}-{1}".format(_mo, _day)
    except KeyError:
        pass
    raise XPathContext.FunctionArgType(0,"xs:gMonthDay")
    
def datedaymonthbg(arg):
    return datedaymonth(arg, daymonthBgPattern)

def datedaymonthcs(arg):
    return datedaymonth(arg, daymonthCsPattern, monthnumbercs)

def datedaymonthde(arg):
    return datedaymonth(arg, daymonthDePattern)

def datedaymonthdk(arg):
    m = daymonthDkPattern.match(arg)
    if m and m.lastindex == 4:
        day = z2(m.group(1))
        mon3 = m.group(2).lower()
        monEnd = m.group(3)
        monPer = m.group(4)
        if (mon3 in monthnumber):
            mo = monthnumber[mon3]
            if (((not monEnd and not monPer) or
                 (not monEnd and monPer) or
                 (monEnd and not monPer)) and
                "01" <= day <= maxDayInMo.get(mo, "00")):
                return "--{0:02}-{1}".format(mo, day)
    raise XPathContext.FunctionArgType(0,"xs:gMonthDay")
    
def datedaymonthel(arg):
    return datedaymonth(arg, daymonthElPattern)

def datedaymonthen(arg):
    return datedaymonth(arg, daymonthEnPattern)
    
def datedaymonthShortEnTR1(arg):
    return datedaymonth(arg, daymonthShortEnTR1Pattern, dy=1, mo=2)
    
def datedaymonthLongEnTR1(arg):
    return datedaymonth(arg, daymonthLongEnTR1Pattern, dy=1, mo=2)
    
def datemonthdayen(arg):
    return datedaymonth(arg, monthdayEnPattern, dy=2, mo=1)

def datemonthdayLongEnTR1(arg):
    return datedaymonth(arg, monthdayLongEnTR1Pattern, dy=2, mo=1)

def datemonthdayShortEnTR1(arg):
    return datedaymonth(arg, monthdayShortEnTR1Pattern, dy=2, mo=1)

def datedaymonthel(arg):
    return datedaymonth(arg, daymonthElPattern)

def datedaymonthes(arg):
    return datedaymonth(arg, daymonthEsPattern)

def datedaymonthet(arg):
    return datedaymonth(arg, daymonthEtPattern)

def datedaymonthfi(arg):
    return datedaymonth(arg, daymonthFiPattern, monthnumberfi)

def datedaymonthfr(arg):
    return datedaymonth(arg, daymonthFrPattern)

def datedaymonthhr(arg):
    return datedaymonth(arg, daymonthHrPattern, monthnumberhr)

def datemonthdayhu(arg):
    return datedaymonth(arg, monthdayHuPattern, dy=2, mo=1)

def datedaymonthit(arg):
    return datedaymonth(arg, daymonthItPattern)

def datemonthdaylt(arg):
    return datedaymonth(arg, monthdayLtPattern, monthnumberlt, dy=2, mo=1)

def datedaymonthlv(arg):
    return datedaymonth(arg, daymonthLvPattern)

def datedaymonthnl(arg):
    return datedaymonth(arg, daymonthNlPattern)

def datedaymonthno(arg):
    return datedaymonth(arg, daymonthNoPattern)

def datedaymonthpl(arg):
    return datedaymonth(arg, daymonthPlPattern, monthnumberpl)

def datedaymonthpt(arg):
    return datedaymonth(arg, daymonthPtPattern)

def datedaymonthroman(arg):
    return datedaymonth(arg, daymonthRomanPattern, monthnumberroman)

def datedaymonthro(arg):
    return datedaymonth(arg, daymonthRoPattern)

def datedaymonthsk(arg):
    return datedaymonth(arg, daymonthSkPattern)

def datedaymonthsl(arg):
    return datedaymonth(arg, daymonthSlPattern)

def datedaymonthyearTR2(arg):
    return datedaymonthyear(arg, daymonthyearPattern, None, dy=1, mo=2, yr=3)
    
def datemonthdayyear(arg): 
    return datedaymonthyear(arg, monthdayyearPattern, None, dy=2, mo=1, yr=3)
    
def datemonthyearTR3(arg):
    m = monthyearPattern.match(arg) # "(M)M*(Y)Y(YY)", with non-numeric separator,
    if m and m.lastindex == 2:
        _mo = z2(m.group(1))
        if "01" <= _mo <= "12":
            return "{0}-{1:2}".format(yr4(m.group(2)), _mo)
    raise XPathContext.FunctionArgType(0,"xs:gYearMonth")
    
def datemonthyear(arg, pattern, moTbl=monthnumber, mo=1, yr=2, lastindex=2):
    m = pattern.match(arg)
    try:
        if m and m.lastindex == lastindex:
            return "{0}-{1:02}".format(yr4(m.group(yr)), moTbl[m.group(mo).lower()])
    except KeyError:
        pass
    raise XPathContext.FunctionArgType(0,"xs:gYearMonth")
    
def datemonthyearbg(arg):
    return datemonthyear(arg, monthyearBgPattern)

def datemonthyearcs(arg):
    return datemonthyear(arg, monthyearCsPattern, monthnumbercs)

def datemonthyearde(arg):
    return datemonthyear(arg, monthyearDePattern)

    
def datemonthyeardk(arg):
    m = monthyearDkPattern.match(arg)
    if m and m.lastindex == 4:
        mon3 = m.group(1).lower()
        monEnd = m.group(2)
        monPer = m.group(3)
        if mon3 in monthnumber and ((not monEnd and not monPer) or
                                    (not monEnd and monPer) or
                                    (monEnd and not monPer)):
            return "{0}-{1:02}".format(yr4(m.group(4)), monthnumber[mon3])
    raise XPathContext.FunctionArgType(0,"xs:gYearMonth")
    
def datemonthyearel(arg):
    return datemonthyear(arg, monthyearElPattern)

def datemonthyearen(arg):
    return datemonthyear(arg, monthyearEnPattern, mo=1, yr=2)
    
def datemonthyearShortEnTR1(arg):
    return datemonthyear(arg, monthyearShortEnTR1Pattern, mo=1, yr=2)
    
def datemonthyearLongEnTR1(arg):
    return datemonthyear(arg, monthyearLongEnTR1Pattern, mo=1, yr=2)
    
def datemonthyeares(arg):
    return datemonthyear(arg, monthyearEsPattern)
    
def datemonthyearin(arg):
    m = monthyearInPattern.match(arg)
    try:
        return "{0}-{1}".format(yr4(devanagariDigitsToNormal(m.group(2))), 
                                   gregorianHindiMonthNumber[m.group(1)])
    except (AttributeError, IndexError, KeyError):
        pass
    raise XPathContext.FunctionArgType(0,"xs:gYearMonth")
    
def dateyearmonthen(arg):
    return datemonthyear(arg, yearmonthEnPattern, mo=2, yr=1)

def datemonthyeares(arg):
    return datemonthyear(arg, monthyearEsPattern)

def datemonthyearet(arg):
    return datemonthyear(arg, monthyearEtPattern)

def datemonthyearfi(arg):
    return datemonthyear(arg, monthyearFiPattern, monthnumberfi)

def datemonthyearfr(arg):
    return datemonthyear(arg, monthyearFrPattern)

def datemonthyearhr(arg):
    return datemonthyear(arg, monthyearHrPattern, monthnumberhr)

def datemonthyearin(arg):
    m = monthyearInPattern.match(arg)
    try:
        return "{0}-{1}".format(yr4(devanagariDigitsToNormal(m.group(2))), 
                                   gregorianHindiMonthNumber[m.group(1)])
    except (AttributeError, IndexError, KeyError):
        pass
    raise XPathContext.FunctionArgType(0,"xs:gYearMonth")

def datemonthyearit(arg):
    return datemonthyear(arg, monthyearItPattern)

def datemonthyearnl(arg):
    return datemonthyear(arg, monthyearNlPattern)

def datemonthyearno(arg):
    return datemonthyear(arg, monthyearNoPattern)

def datemonthyearpl(arg):
    return datemonthyear(arg, monthyearPlPattern, monthnumberpl)

def datemonthyearpt(arg):
    return datemonthyear(arg, monthyearPtPattern)

def datemonthyearroman(arg):
    return datemonthyear(arg, monthyearRomanPattern, monthnumberroman, mo=1, yr=6, lastindex=6)

def datemonthyearro(arg):
    return datemonthyear(arg, monthyearRoPattern)

def datemonthyearsk(arg):
    return datemonthyear(arg, monthyearSkPattern)

def datemonthyearsl(arg):
    return datemonthyear(arg, monthyearSlPattern)

def dateyearmonthhu(arg):
    return datemonthyear(arg, yearmonthHuPattern, mo=2, yr=1)

def dateyearmonthlt(arg):
    return datemonthyear(arg, yearmonthLtPattern, monthnumberlt, mo=2, yr=1)

def dateyearmonthlv(arg):
    return datemonthyear(arg, yearmonthLvPattern, mo=2, yr=1)

def dateyearmonthShortEnTR1(arg):
    return datemonthyear(arg, yearmonthShortEnTR1Pattern, mo=2, yr=1)

def dateyearmonthLongEnTR1(arg):
    return datemonthyear(arg, yearmonthLongEnTR1Pattern, mo=2, yr=1)

def datedaymonthyear(arg, pattern, moTbl=monthnumber, dy=1, mo=2, yr=3, lastindex=3):
    m = pattern.match(arg)
    try:
        if m and m.lastindex == lastindex:
            _yr = yr4(m.group(yr))
            _day = z2(m.group(dy))
            _mo = m.group(mo)
            _mo = moTbl[_mo.lower()] if moTbl else int(_mo)
            if checkDate(_yr, _mo, _day):
                return "{0}-{1:02}-{2}".format(_yr, _mo, _day)
    except KeyError:
        pass
    raise XPathContext.FunctionArgType(0,"xs:date")

def datedaymonthyearbg(arg):
    return datedaymonthyear(arg, daymonthyearBgPattern)

def datedaymonthyearcs(arg):
    return datedaymonthyear(arg, daymonthyearCsPattern, monthnumbercs)

def datedaymonthyearde(arg):
    return datedaymonthyear(arg, daymonthyearDePattern)

def datedaymonthyeardk(arg):
    m = daymonthyearDkPattern.match(arg)
    if m and m.lastindex == 5:
        _yr = yr4(m.group(5))
        _day = z2(m.group(1))
        _mon3 = m.group(2).lower()
        _monEnd = m.group(3)
        _monPer = m.group(4)
        if _mon3 in monthnumber and ((not _monEnd and not _monPer) or
                                     (not _monEnd and _monPer) or
                                     (_monEnd and not _monPer)):
            _mo = monthnumber[_mon3]
            if checkDate(_yr, _mo, _day):
                return "{0}-{1:02}-{2}".format(_yr, _mo, _day)
    raise XPathContext.FunctionArgType(0,"xs:date")

def datedaymonthyearel(arg):
    return datedaymonthyear(arg, daymonthyearElPattern)

def datedaymonthyearen(arg):
    return datedaymonthyear(arg, daymonthyearEnPattern)

def datemonthdayyearen(arg):
    return datedaymonthyear(arg, monthdayyearEnPattern, dy=2, mo=1, yr=3)
    
def datedaymonthyeares(arg):
    return datedaymonthyear(arg, daymonthyearEsPattern)

def datedaymonthyearet(arg):
    return datedaymonthyear(arg, daymonthyearEtPattern)

def datedaymonthyearfi(arg):
    return datedaymonthyear(arg, daymonthyearFiPattern, monthnumberfi)

def datedaymonthyearfr(arg):
    return datedaymonthyear(arg, daymonthyearFrPattern)

def datedaymonthyearhr(arg):
    return datedaymonthyear(arg, daymonthyearHrPattern, monthnumberhr)

def dateyearmonthdayhu(arg):
    return datedaymonthyear(arg, yearmonthdayHuPattern, dy=3, mo=2, yr=1)

def datedaymonthyearin(arg):
    m = daymonthyearInPattern.match(arg)
    try:
        _yr = yr4(devanagariDigitsToNormal(m.group(3)))
        _mo = gregorianHindiMonthNumber.get(m.group(2), devanagariDigitsToNormal(m.group(2)))
        _day = z2(devanagariDigitsToNormal(m.group(1)))
        if checkDate(_yr, _mo, _day):
            return "{0}-{1}-{2}".format(_yr, _mo, _day)
    except (AttributeError, IndexError, KeyError):
        pass
    raise XPathContext.FunctionArgType(0,"xs:date")

def datedaymonthyearit(arg):
    return datedaymonthyear(arg, daymonthyearItPattern)

def dateyeardaymonthlv(arg):
    return datedaymonthyear(arg, yeardaymonthLvPattern, dy=2, mo=3, yr=1)

def dateyearmonthdaylt(arg):
    return datedaymonthyear(arg, yearmonthdayLtPattern, monthnumberlt, dy=3, mo=2, yr=1)

def datedaymonthyearnl(arg):
    return datedaymonthyear(arg, daymonthyearNlPattern)

def datedaymonthyearno(arg):
    return datedaymonthyear(arg, daymonthyearNoPattern)

def datedaymonthyearpl(arg):
    return datedaymonthyear(arg, daymonthyearPlPattern, monthnumberpl)

def datedaymonthyearpt(arg):
    return datedaymonthyear(arg, daymonthyearPtPattern)

def datedaymonthyearroman(arg):
    return datedaymonthyear(arg, daymonthyearRomanPattern, monthnumberroman, dy=1, mo=2, yr=7, lastindex=7)

def datedaymonthyearro(arg):
    return datedaymonthyear(arg, daymonthyearRoPattern)

def datedaymonthyearsk(arg):
    return datedaymonthyear(arg, daymonthyearSkPattern)

def datedaymonthyearsl(arg):
    return datedaymonthyear(arg, daymonthyearSlPattern)

def calindaymonthyear(arg):
    m = daymonthyearInPattern.match(arg)
    try:
        # Transformation registry 3 requires use of pattern comparisons instead of exact transliterations
        #_mo = _INT(sakaMonthNumber[m.group(2)])
        # pattern approach
        _mo = sakaMonthPattern.search(m.group(2)).lastindex
        _day = _INT(devanagariDigitsToNormal(m.group(1)))
        _yr = _INT(devanagariDigitsToNormal(yrin(m.group(3), _mo, _day)))
        #sakaDate = [_yr, _mo, _day]
        #for pluginMethod in pluginClassMethods("SakaCalendar.ToGregorian"):  # LGPLv3 plugin (moved to examples/plugin)
        #    gregorianDate = pluginMethod(sakaDate)
        #    return "{0}-{1:02}-{2:02}".format(gregorianDate[0], gregorianDate[1], gregorianDate[2])
        #raise NotImplementedError (_("ixt:calindaymonthyear requires plugin sakaCalendar.py, please install plugin.  "))
        gregorianDate = sakaToGregorian(_yr, _mo, _day) # native implementation for Arelle
        return "{0}-{1:02}-{2:02}".format(gregorianDate[0], gregorianDate[1], gregorianDate[2])
    except (AttributeError, IndexError, KeyError, ValueError):
        pass
    raise XPathContext.FunctionArgType(0,"xs:date")

def dateerayearmonthdayjp(arg):
    m = erayearmonthdayjpPattern.match(jpDigitsToNormal(arg))
    if m and m.lastindex == 7:
        _yr = eraYear(m.group(1), m.group(2))
        _mo = z2(m.group(4))
        _day = z2(m.group(6))
        if checkDate(_yr, _mo, _day):
            return "{0}-{1}-{2}".format(_yr, _mo, _day)
    raise XPathContext.FunctionArgType(0,"xs:date")

def dateyearmonthday(arg):
    m = yearmonthdayPattern.match(jpDigitsToNormal(arg)) # (Y)Y(YY)*MM*DD with kangu full-width numerals
    if m and m.lastindex == 3:
        _yr = yr4(m.group(1))
        _mo = z2(m.group(2))
        _day = z2(m.group(3))
        if checkDate(_yr, _mo, _day):
            return "{0}-{1}-{2}".format(_yr, _mo, _day)
    raise XPathContext.FunctionArgType(0,"xs:date")

def dateerayearmonthjp(arg):
    m = erayearmonthjpPattern.match(jpDigitsToNormal(arg))
    if m and m.lastindex == 5:
        _yr = eraYear(m.group(1), m.group(2))
        _mo = z2(m.group(4))
        if "01" <= _mo <= "12":
            return "{0}-{1}".format(_yr, _mo)
    raise XPathContext.FunctionArgType(0,"xs:gYearMonth")

def dateyearmonthdaycjk(arg):
    m = yearmonthdaycjkPattern.match(jpDigitsToNormal(arg))
    if m and m.lastindex == 6:
        _yr = yr4(m.group(1))
        _mo = z2(m.group(3))
        _day = z2(m.group(5))
        if checkDate(_yr, _mo, _day):
            return "{0}-{1}-{2}".format(_yr, _mo, _day)
    raise XPathContext.FunctionArgType(0,"xs:date")

def dateyearmonthcjk(arg):
    m = yearmonthcjkPattern.match(jpDigitsToNormal(arg))
    if m and m.lastindex == 4:
        _mo =  z2(m.group(3))
        if "01" <= _mo <= "12":
            return "{0}-{1}".format(yr4(m.group(1)), _mo)
    raise XPathContext.FunctionArgType(0,"xs:date")

def nocontent(arg):
    return ''

def numcommadecimal(arg):
    if numCommaDecimalPattern.match(arg):
        return arg.replace('.', '').replace(',', '.').replace(' ', '').replace('\u00A0', '')
    raise XPathContext.FunctionArgType(0,"ixt:nonNegativeDecimalType")

def numcommadot(arg):
    if numCommaDotPattern.match(arg):
        return arg.replace(',', '')
    raise XPathContext.FunctionArgType(0,"ixt:numcommadot")

def numdash(arg):
    if numDashPattern.match(arg):
        return arg.replace('-','0')
    raise XPathContext.FunctionArgType(0,"ixt:numdash")

def numspacedot(arg):
    if numSpaceDotPattern.match(arg):
        return arg.replace(' ', '').replace('\u00A0', '')
    raise XPathContext.FunctionArgType(0,"ixt:numspacedot")

def numcomma(arg):
    if numCommaPattern.match(arg):
        return arg.replace(',', '.')
    raise XPathContext.FunctionArgType(0,"ixt:numcomma")

def numdotcomma(arg):
    if numDotCommaPattern.match(arg):
        return arg.replace('.', '').replace(',', '.')
    raise XPathContext.FunctionArgType(0,"ixt:numdotcomma")

def numspacecomma(arg):
    if numSpaceCommaPattern.match(arg):
        return arg.replace(' ', '').replace('\u00A0', '').replace(',', '.')
    raise XPathContext.FunctionArgType(0,"ixt:numspacecomma")

def zerodash(arg):
    if zeroDashPattern.match(arg):
        return '0'
    raise XPathContext.FunctionArgType(0,"ixt:zerodashType")

def numdotdecimal(arg):
    if numDotDecimalPattern.match(arg):
        return arg.replace(',', '').replace(' ', '').replace('\u00A0', '')
    raise XPathContext.FunctionArgType(0,"ixt:numdotdecimalType")

def numdotdecimalTR4(arg):
    if numDotDecimalTR4Pattern.match(arg):
        return arg.replace(',', '').replace(' ', '').replace('\u00A0', '')
    raise XPathContext.FunctionArgType(0,"ixt:numdotdecimalType")

def numdotdecimalin(arg):
    m = numDotDecimalInPattern.match(arg)
    if m:
        m2 = [g for g in m.groups() if g is not None]
        if m2[-1].startswith("."):
            fract = m2[-1]
        else:
            fract = ""
        return m2[0].replace(',','').replace(' ','').replace('\xa0','') + fract
    raise XPathContext.FunctionArgType(1,"ixt:numdotdecimalinType")

def numunitdecimal(arg):
    # remove comma (normal), full-width comma, and stops (periods)
    m = numUnitDecimalPattern.match(jpDigitsToNormal(arg))
    if m and m.lastindex > 1:
        return m.group(1).replace('.','').replace(',','').replace('\uFF0C','').replace('\uFF0E','') + '.' + z2(m.group(m.lastindex))
    raise XPathContext.FunctionArgType(1,"ixt:nonNegativeDecimalType")

def numunitdecimalin(arg):
    m = numUnitDecimalInPattern.match(arg)
    if m:
        m2 = [g for g in m.groups() if g is not None]
        return m2[0].replace(',','').replace(' ','').replace('\xa0','') + '.' + z2(m2[-2])
    raise XPathContext.FunctionArgType(1,"ixt:numunitdecimalinType")
    
tr1Functions = {
    # 2010-04-20 functions
    'dateslashus': dateslashus,
    'dateslasheu': dateslasheu,
    'datedotus': datedotus,
    'datedoteu': datedoteu,
    'datelongus': datelongusTR1,
    'dateshortus': dateshortusTR1,
    'datelonguk': datelongukTR1,
    'dateshortuk': dateshortukTR1,
    'numcommadot': numcommadot,
    'numdash': numdash,
    'numspacedot': numspacedot,
    'numdotcomma': numdotcomma,
    'numcomma': numcomma,
    'numspacecomma': numspacecomma,
    'datelongdaymonthuk': datedaymonthLongEnTR1,
    'dateshortdaymonthuk': datedaymonthShortEnTR1,
    'datelongmonthdayus': datemonthdayLongEnTR1,
    'dateshortmonthdayus': datemonthdayShortEnTR1,
    'dateslashdaymontheu': datedaymonthSlashTR1,
    'dateslashmonthdayus': datemonthdaySlashTR1,
    'datelongyearmonth': dateyearmonthLongEnTR1,
    'dateshortyearmonth': dateyearmonthShortEnTR1,
    'datelongmonthyear': datemonthyearLongEnTR1,
    'dateshortmonthyear': datemonthyearShortEnTR1
}

tr2Functions = {
                           
    # 2011-07-31 functions
    'booleanfalse': booleanfalse,
    'booleantrue': booleantrue,
    'datedaymonth': datedaymonthTR2,
    'datedaymonthen': datedaymonthen,
    'datedaymonthyear': datedaymonthyearTR2,
    'datedaymonthyearen': datedaymonthyearen,
    'dateerayearmonthdayjp': dateerayearmonthdayjp,
    'dateerayearmonthjp': dateerayearmonthjp,
    'datemonthday': datemonthday,
    'datemonthdayen': datemonthdayen,
    'datemonthdayyear': datemonthdayyear,
    'datemonthdayyearen': datemonthdayyearen,
    'datemonthyearen': datemonthyearen,
    'dateyearmonthdaycjk': dateyearmonthdaycjk,
    'dateyearmonthen': dateyearmonthen,
    'dateyearmonthcjk': dateyearmonthcjk,
    'nocontent': nocontent,
    'numcommadecimal': numcommadecimal,
    'zerodash': zerodash,
    'numdotdecimal': numdotdecimal,
    'numunitdecimal': numunitdecimal
}
    
    # transformation registry v-3 functions
tr3Functions = tr2Functions.copy() # tr3 starts with tr2 and adds more functions
tr3Functions.update ({
    # same as v2: 'booleanfalse': booleanfalse,
    # same as v2: 'booleantrue': booleantrue,
    'calindaymonthyear': calindaymonthyear, # TBD: calindaymonthyear,
    #'calinmonthyear': nocontent, # TBD: calinmonthyear,
    # same as v2: 'datedaymonth': datedaymonthTR2,
    'datedaymonthdk': datedaymonthdk,
    # same as v2: 'datedaymonthen': datedaymonthen,
    # same as v2: 'datedaymonthyear': datedaymonthyearTR2,
    'datedaymonthyeardk': datedaymonthyeardk,
    # same as v2: 'datedaymonthyearen': datedaymonthyearen,
    'datedaymonthyearin': datedaymonthyearin,
    # same as v2: 'dateerayearmonthdayjp': dateerayearmonthdayjp,
    # same as v2: 'dateerayearmonthjp': dateerayearmonthjp,
    # same as v2: 'datemonthday': datemonthday,
    # same as v2: 'datemonthdayen': datemonthdayen,
    # same as v2: 'datemonthdayyear': datemonthdayyear, 
    # same as v2: 'datemonthdayyearen': datemonthdayyearen,
    'datemonthyear': datemonthyearTR3,
    'datemonthyeardk': datemonthyeardk,
    # same as v2: 'datemonthyearen': datemonthyearen,
    'datemonthyearin': datemonthyearin,
    # same as v2: 'dateyearmonthcjk': dateyearmonthcjk,
    'dateyearmonthday': dateyearmonthday, # (Y)Y(YY)*MM*DD allowing kanji full-width numerals
    # same as v2: 'dateyearmonthdaycjk': dateyearmonthdaycjk,
    # same as v2: 'dateyearmonthen': dateyearmonthen,
    # same as v2: 'nocontent': nocontent,
    # same as v2: 'numcommadecimal': numcommadecimal,
    # same as v2: 'numdotdecimal': numdotdecimal,
    'numdotdecimalin': numdotdecimalin,
    # same as v2: 'numunitdecimal': numunitdecimal,
    'numunitdecimalin': numunitdecimalin,
    # same as v2: 'zerodash': zerodash,
})
    # transformation registry v-4 functions
tr4Functions = tr3Functions.copy() # tr4 starts with tr3 and adds more functions
tr4Functions.update ({
    # same as v2: 'booleanfalse': booleanfalse,
    # same as v2: 'booleantrue': booleantrue,
    # same as v3: 'calindaymonthyear': calindaymonthyear,
    # same as v3: 'calinmonthyear': nocontent, # TBD: calinmonthyear,
    # same as v2: 'datedaymonth': datedaymonthTR2,
    'datedaymonthbg': datedaymonthbg,
    'datedaymonthcs': datedaymonthcs,
    'datedaymonthde': datedaymonthde,
    'datedaymonthel': datedaymonthel,
    'datedaymonthbg': datedaymonthbg,
    'datedaymonthcs': datedaymonthcs,
    'datedaymonthde': datedaymonthde,
    'datedaymonthel': datedaymonthel,
    'datedaymonthes': datedaymonthes,
    'datedaymonthet': datedaymonthet,
    'datedaymonthfi': datedaymonthfi,
    'datedaymonthfr': datedaymonthfr,
    'datedaymonthhr': datedaymonthhr,
    'datemonthdayhu': datemonthdayhu,
    'datedaymonthit': datedaymonthit,
    'datemonthdaylt': datemonthdaylt,
    'datedaymonthlv': datedaymonthlv,
    'datedaymonthnl': datedaymonthnl,
    'datedaymonthno': datedaymonthno,
    'datedaymonthpl': datedaymonthpl,
    'datedaymonthpt': datedaymonthpt,
    'datedaymonthroman': datedaymonthroman,
    'datedaymonthro': datedaymonthro,
    'datedaymonthse': datedaymonthdk,
    'datedaymonthsk': datedaymonthsk,
    'datedaymonthsl': datedaymonthsl,

    # same as v3: 'datedaymonthdk': datedaymonthdk,
    # same as v2: 'datedaymonthen': datedaymonthen,
    # same as v2: 'datedaymonthyear': datedaymonthyearTR2,
    'datedaymonthyearbg': datedaymonthyearbg,
    'datedaymonthyearcs': datedaymonthyearcs,
    'datedaymonthyearde': datedaymonthyearde,
    'datedaymonthyearel': datedaymonthyearel,
    'datedaymonthyeares': datedaymonthyeares,
    'datedaymonthyearet': datedaymonthyearet,
    'datedaymonthyearfi': datedaymonthyearfi,
    'datedaymonthyearfr': datedaymonthyearfr,
    'datedaymonthyearhr': datedaymonthyearhr,
    'dateyearmonthdayhu': dateyearmonthdayhu,
    'datedaymonthyearit': datedaymonthyearit,
    'dateyeardaymonthlv': dateyeardaymonthlv,
    'dateyearmonthdaylt': dateyearmonthdaylt,
    'datedaymonthyearnl': datedaymonthyearnl,
    'datedaymonthyearno': datedaymonthyearno,
    'datedaymonthyearpl': datedaymonthyearpl,
    'datedaymonthyearpt': datedaymonthyearpt,
    'datedaymonthyearroman': datedaymonthyearroman,
    'datedaymonthyearro': datedaymonthyearro,
    'datedaymonthyearse': datedaymonthyeardk,
    'datedaymonthyearsk': datedaymonthyearsk,
    'datedaymonthyearsl': datedaymonthyearsl,    # same as v3: 'datedaymonthyeardk': datedaymonthyeardk,
    # same as v2: 'datedaymonthyearen': datedaymonthyearen,
    # same as v3: 'datedaymonthyearin': datedaymonthyearin,
    # same as v2: 'dateerayearmonthdayjp': dateerayearmonthdayjp,
    # same as v2: 'dateerayearmonthjp': dateerayearmonthjp,
    # same as v2: 'datemonthday': datemonthday,
    # same as v2: 'datemonthdayen': datemonthdayen,
    # same as v2: 'datemonthdayyear': datemonthdayyear, 
    # same as v2: 'datemonthdayyearen': datemonthdayyearen,
    # same as v3: 'datemonthyear': datemonthyearTR3,
    'datemonthyearbg': datemonthyearbg,
    'datemonthyearcs': datemonthyearcs,
    'datemonthyearde': datemonthyearde,
    'datemonthyearel': datemonthyearel,
    'datemonthyeares': datemonthyeares,
    'datemonthyearet': datemonthyearet,
    'datemonthyearfi': datemonthyearfi,
    'datemonthyearfr': datemonthyearfr,
    'datemonthyearhr': datemonthyearhr,
    'dateyearmonthhu': dateyearmonthhu,
    'datemonthyearin': datemonthyearin,
    'datemonthyearit': datemonthyearit,
    'dateyearmonthlt': dateyearmonthlt,
    'dateyearmonthlv': dateyearmonthlv,
    'datemonthyearnl': datemonthyearnl,
    'datemonthyearno': datemonthyearno,
    'datemonthyearpl': datemonthyearpl,
    'datemonthyearpt': datemonthyearpt,
    'datemonthyearroman': datemonthyearroman,
    'datemonthyearro': datemonthyearro,
    'datemonthyearse': datemonthyeardk,
    'datemonthyearsk': datemonthyearsk,
    'datemonthyearsl': datemonthyearsl,
    'dateyeardaymonthlv': dateyeardaymonthlv,
    'dateyearmonthdayhu': dateyearmonthdayhu,
    'dateyearmonthdaylt': dateyearmonthdaylt,
    'dateyearmonthhu': dateyearmonthhu,
    'dateyearmonthlt': dateyearmonthlt,
    'dateyearmonthlv': dateyearmonthlv,
    # same as v3: 'datemonthyeardk': datemonthyeardk,
    # same as v2: 'datemonthyearen': datemonthyearen,
    # same as v3: 'datemonthyearin': datemonthyearin,
    # same as v2: 'dateyearmonthcjk': dateyearmonthcjk,
    # same as v3: 'dateyearmonthday': dateyearmonthday, # (Y)Y(YY)*MM*DD allowing kanji full-width numerals
    # same as v2: 'dateyearmonthdaycjk': dateyearmonthdaycjk,
    # same as v2: 'dateyearmonthen': dateyearmonthen,
    # same as v2: 'nocontent': nocontent,
    # same as v2: 'numcommadecimal': numcommadecimal,
    'numdotdecimal': numdotdecimalTR4, # relax requirement for 0 before decimal
    # same as v3: 'numdotdecimalin': numdotdecimalin,
    # same as v2: 'numunitdecimal': numunitdecimal,
    # same as v3: 'numunitdecimalin': numunitdecimalin,
    # same as v2: 'zerodash': zerodash,
})
deprecatedNamespaceURI = 'http://www.xbrl.org/2008/inlineXBRL/transformation' # the CR/PR pre-REC namespace

ixtNamespaces = {
    "ixt v1": 'http://www.xbrl.org/inlineXBRL/transformation/2010-04-20',
    "ixt v2": 'http://www.xbrl.org/inlineXBRL/transformation/2011-07-31',
    "ixt v3": 'http://www.xbrl.org/inlineXBRL/transformation/2015-02-26',
    "ixt v4": 'http://www.xbrl.org/inlineXBRL/transformation/WGWD/YYYY-MM-DD'
    }

ixtNamespaceFunctions = {
    ixtNamespaces["ixt v1"]: tr1Functions, # transformation registry v1
    ixtNamespaces["ixt v2"]: tr2Functions, # transformation registry v2
    ixtNamespaces["ixt v3"]: tr3Functions, # transformation registry v3
    ixtNamespaces["ixt v4"]: tr4Functions, # transformation registry v3
    'http://www.xbrl.org/2008/inlineXBRL/transformation': tr1Functions # the CR/PR pre-REC namespace
}
