"""
See COPYRIGHT.md for copyright information.
"""
from arelle.Version import authorLabel, copyrightLabel


def testcaseVariationExpectedResult(modelTestcaseVariation):
    for result in modelTestcaseVariation.iter("{*}warning"):
        return result.text


__pluginInfo__ = {
    "name": "Testcase obtain expected calc 11 mode from variation/result@mode",
    "version": "0.9",
    "description": "This plug-in removes xxx.  ",
    "license": "Apache-2",
    "author": authorLabel,
    "copyright": copyrightLabel,
    # classes of mount points (required)
    "ModelTestcaseVariation.ExpectedResult": testcaseVariationExpectedResult
}
