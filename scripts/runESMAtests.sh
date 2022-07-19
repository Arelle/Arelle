#!/bin/sh

rm -f /users/hermf/temp/ESMA-conf-*
OUTPUTLOGFILE=/users/hermf/temp/ESMA-conf-log.txt
OUTPUTERRFILE=/users/hermf/temp/ESMA-conf-err.txt
ARELLECMDLINESRC=/users/hermf/Documents/mvsl/projects/arelle/arelleproject/src/arelleCmdLine.py
PYTHON=python3.5


for f in \
    https://www.esma.europa.eu/sites/default/files/bzwbk_2016.zip \
    https://www.esma.europa.eu/sites/default/files/bonetherapeutics_2016.zip \
    https://www.esma.europa.eu/sites/default/files/comarch_2016.zip \
    https://www.esma.europa.eu/sites/default/files/enel_2016.zip \
    https://www.esma.europa.eu/sites/default/files/erstegroup_2016.zip \
    https://www.esma.europa.eu/sites/default/files/ferrovial_2016.zip \
    https://www.esma.europa.eu/sites/default/files/generali_2016.zip \
    https://www.esma.europa.eu/sites/default/files/genomicvision_2016.zip \
    https://www.esma.europa.eu/sites/default/files/imerys_2016.zip \
    https://www.esma.europa.eu/sites/default/files/komercnibanka_2016.zip \
    https://www.esma.europa.eu/sites/default/files/helaba_2016.zip \
    https://www.esma.europa.eu/sites/default/files/leoexpress_2016.zip \
    https://www.esma.europa.eu/sites/default/files/molgroup_2016_0.zip \
    https://www.esma.europa.eu/sites/default/files/nelja_2016.zip \
    https://www.esma.europa.eu/sites/default/files/nationalbankofgreece_2016.zip \
    https://www.esma.europa.eu/sites/default/files/ontex_2016.zip \
    https://www.esma.europa.eu/sites/default/files/orangepolska_2016.zip \
    https://www.esma.europa.eu/sites/default/files/siemens_2016.zip \
    https://www.esma.europa.eu/sites/default/files/ucb_2016.zip \
    https://www.esma.europa.eu/sites/default/files/uniqa_2016.zip \
    https://www.esma.europa.eu/sites/default/files/upm_2016.zip \
    https://www.esma.europa.eu/sites/default/files/valmet_2016.zip 
  do
  echo file: $f
$PYTHON $ARELLECMDLINESRC --file $f --plugins validate/ESMA --disclosureSystem esma --validate --packages '/Users/hermf/downloads/IFRST_2017-03-09.zip|/Users/hermf/Documents/mvsl/projects/ESMA/ESMA_ESEF_Taxonomy_Draft.zip' --logFile "$OUTPUTLOGFILE" 2>  "$OUTPUTERRFILE"
done
