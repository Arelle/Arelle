"""
See COPYRIGHT.md for copyright information.
"""
from arelle.ValidateXbrlCalcs import ValidateCalcsMode as CalcsMode
from arelle.Version import authorLabel, copyrightLabel


def testcaseVariationLoaded(testInstance, testcaseInstance, modelTestcaseVariation):
    for result in modelTestcaseVariation.iter("{*}result"):
        for n, v in result.attrib.items():
            if n.endswith("mode"):
                if v == "round-to-nearest":
                    testInstance.modelManager.validateCalcs = CalcsMode.ROUND_TO_NEAREST
                elif v == "truncate":
                    testInstance.modelManager.validateCalcs = CalcsMode.TRUNCATION


def testcaseVariationExpectedResult(modelTestcaseVariation):
    for result in modelTestcaseVariation.iter("{*}warning"):
        return result.text


__pluginInfo__ = {
    'name': 'Testcase obtain expected calc 11 mode from variation/result@mode',
    'version': '0.9',
    'description': "This plug-in removes xxx.  ",
    'license': "Apache-2",
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'TestcaseVariation.Xbrl.Loaded': testcaseVariationLoaded,
    'ModelTestcaseVariation.ExpectedResult': testcaseVariationExpectedResult
}
