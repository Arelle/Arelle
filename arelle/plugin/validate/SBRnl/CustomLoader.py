'''
See COPYRIGHT.md for copyright information.
'''
import regex as re

def checkForBOMs(modelXbrl, file, mappedUri, filepath, *args, **kwargs):
    # callback is for all opened docs, must only process when SBRNL validation active
    if (modelXbrl.modelManager.validateDisclosureSystem and
        # corrected merge of pre-plugin code per LOGIUS
        getattr(modelXbrl.modelManager.validateDisclosureSystem, "SBRNLplugin", False)):
        #must read file in binary and return nothing to not replace standard loading
        with open(filepath, 'rb') as fb:
            startingBytes = fb.read(8)
            if re.match(b"\\x00\\x00\\xFE\\xFF|\\xFF\\xFE\\x00\\x00|\\x2B\\x2F\\x76\\x38|\\x2B\\x2F\\x76\\x39|\\x2B\\x2F\\x76\\x2B|\\x2B\\x2F\\x76\\x2F|\\xDD\\x73\\x66\\x73|\\xEF\\xBB\\xBF|\\x0E\\xFE\\xFF|\\xFB\\xEE\\x28|\\xFE\\xFF|\\xFF\\xFE",
                        startingBytes):
                modelXbrl.error("SBR.NL.2.1.0.09",
                    _("File MUST not start with a Byte Order Mark (BOM): %(filename)s"),
                    modelObject=modelXbrl, filename=mappedUri)
    return None # must return None for regular document loading to continue
