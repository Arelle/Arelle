"""
See COPYRIGHT.md for copyright information.

NVAD Lifecycle rules — business commencement and cessation flag/date
pairing.

Rules implemented here:
  NVAD-E-1000  BusinessCommencement must be true when
               BusinessCommencementDate is present
  NVAD-E-1010  BusinessCommencementDate required when
               BusinessCommencement is true
  NVAD-E-1020  BusinessCessation must be true when
               BusinessCessationDate is present
  NVAD-E-1030  BusinessCessationDate required when
               BusinessCessation is true
  NVAD-E-1040  _(BIR52)_ BusinessCessationDeathOfProprietor must be
               tagged when BusinessCessation is true
  NVAD-E-1050  BusinessCessationProprietorDeathDate required when
               BusinessCessationDeathOfProprietor is true
  NVAD-E-1060  BusinessCessationTransferred must be tagged when
               BusinessCessation is true
  NVAD-E-1070  BusinessCessationTransferee required when
               BusinessCessationTransferred is true
  NVAD-E-1080  _(BIR52)_ BusinessCessationTransfereeBusinessNature
               required when BusinessCessationTransferred is true
  NVAD-E-1081  _(BIR51)_ BusinessCessationTransferredAssetsAssociated
               required when BusinessCessation is true
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Facts import hasValidNonNilFactByQname, hasTrueValueFactByQname, getValidNonNilFactsByQname
from arelle.utils.validate.Validation import Validation
from ..DisclosureSystems import ALL_IRD_DISCLOSURE_SYSTEMS
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1000(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1000: BusinessCommencement must be true when
    BusinessCommencementDate is present.

    Whenever BusinessCommencementDate is tagged, BusinessCommencement
    must be tagged true; a commencement date present alongside a false
    (or absent) flag is inconsistent
    """
    modelXbrl = val.modelXbrl
    if not hasValidNonNilFactByQname(modelXbrl, pluginData.businessCommencementDateQn):
        return

    if not hasTrueValueFactByQname(modelXbrl, pluginData.businessCommencementQn):
        yield Validation.error(
            codes="IRD.NVAD-E-1000",
            msg=_(
                "BusinessCommencement must be true when "
                "BusinessCommencementDate is tagged."
            ),
            modelObject=getValidNonNilFactsByQname(
                modelXbrl, pluginData.businessCommencementDateQn
            ),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1010(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1010: BusinessCommencementDate required when
    BusinessCommencement is true.

    Whenever BusinessCommencement is tagged true, BusinessCommencementDate
    must also be tagged.
    """
    modelXbrl = val.modelXbrl
    if not hasTrueValueFactByQname(modelXbrl, pluginData.businessCommencementQn):
        return

    if not hasValidNonNilFactByQname(modelXbrl, pluginData.businessCommencementDateQn):
        yield Validation.error(
            codes="IRD.NVAD-E-1010",
            msg=_(
                "BusinessCommencementDate must be tagged when "
                "BusinessCommencement is true."
            ),
            modelObject=getValidNonNilFactsByQname(
                modelXbrl, pluginData.businessCommencementQn
            ),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1020(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1020: BusinessCessation must be true when
    BusinessCessationDate is present.

    Whenever BusinessCessationDate is tagged, BusinessCessation must
    be tagged true; a cessation date present alongside a false (or
    absent) flag is inconsistent.
    """
    modelXbrl = val.modelXbrl
    if not hasValidNonNilFactByQname(modelXbrl, pluginData.businessCessationDateQn):
        return

    if not hasTrueValueFactByQname(modelXbrl, pluginData.businessCessationQn):
        yield Validation.error(
            codes="IRD.NVAD-E-1020",
            msg=_(
                "BusinessCessation must be true when "
                "BusinessCessationDate is tagged."
            ),
            modelObject=getValidNonNilFactsByQname(
                modelXbrl, pluginData.businessCessationDateQn
            ),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1030(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1030: BusinessCessationDate required when
    BusinessCessation is true.

    Whenever BusinessCessation is tagged true, BusinessCessationDate
    must also be tagged.
    """
    modelXbrl = val.modelXbrl
    if not hasTrueValueFactByQname(modelXbrl, pluginData.businessCessationQn):
        return

    if not hasValidNonNilFactByQname(modelXbrl, pluginData.businessCessationDateQn):
        yield Validation.error(
            codes="IRD.NVAD-E-1030",
            msg=_(
                "BusinessCessationDate must be tagged when "
                "BusinessCessation is true."
            ),
            modelObject=getValidNonNilFactsByQname(
                modelXbrl, pluginData.businessCessationQn
            ),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1040(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1040: _(BIR52)_ BusinessCessationDeathOfProprietor must
    be tagged when BusinessCessation is true.

    BIR52 (partnership/sole-proprietorship) filings must tag
    BusinessCessationDeathOfProprietor — even if its value is false —
    whenever BusinessCessation is true. Skips entirely on BIR51
    filings, where this concept is not required.
    """
    modelXbrl = val.modelXbrl
    if not pluginData.isBir52(modelXbrl):
        return

    if not hasTrueValueFactByQname(modelXbrl, pluginData.businessCessationQn):
        return

    if not hasValidNonNilFactByQname(modelXbrl, pluginData.businessCessationDeathOfProprietorQn):
        yield Validation.error(
            codes="IRD.NVAD-E-1040",
            msg=_(
                "BusinessCessationDeathOfProprietor must be tagged when "
                "BusinessCessation is true in a BIR52 filing."
            ),
            modelObject=getValidNonNilFactsByQname(
                modelXbrl, pluginData.businessCessationQn
            ),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1050(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1050: BusinessCessationProprietorDeathDate required when
    BusinessCessationDeathOfProprietor is true.

    Whenever BusinessCessationDeathOfProprietor is tagged true,
    BusinessCessationProprietorDeathDate must also be tagged.
    """
    modelXbrl = val.modelXbrl
    if not hasTrueValueFactByQname(
        modelXbrl, pluginData.businessCessationDeathOfProprietorQn
    ):
        return

    if not hasValidNonNilFactByQname(modelXbrl, pluginData.businessCessationProprietorDeathDateQn):
        yield Validation.error(
            codes="IRD.NVAD-E-1050",
            msg=_(
                "BusinessCessationProprietorDeathDate must be tagged "
                "when BusinessCessationDeathOfProprietor is true."
            ),
            modelObject=getValidNonNilFactsByQname(
                modelXbrl, pluginData.businessCessationDeathOfProprietorQn
            ),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1060(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1060: BusinessCessationTransferred must be tagged when
    BusinessCessation is true.

    Whenever BusinessCessation is tagged true,
    BusinessCessationTransferred must also be tagged — even if its
    value is false.
    """
    modelXbrl = val.modelXbrl
    if not hasTrueValueFactByQname(modelXbrl, pluginData.businessCessationQn):
        return

    if not hasValidNonNilFactByQname(modelXbrl, pluginData.businessCessationTransferredQn):
        yield Validation.error(
            codes="IRD.NVAD-E-1060",
            msg=_(
                "BusinessCessationTransferred must be tagged when "
                "BusinessCessation is true."
            ),
            modelObject=getValidNonNilFactsByQname(
                modelXbrl, pluginData.businessCessationQn
            ),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1070(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1070: BusinessCessationTransferee required when
    BusinessCessationTransferred is true.

    Whenever BusinessCessationTransferred is tagged true,
    BusinessCessationTransferee must also be tagged.
    """
    modelXbrl = val.modelXbrl
    if not hasTrueValueFactByQname(modelXbrl, pluginData.businessCessationTransferredQn):
        return

    if not hasValidNonNilFactByQname(modelXbrl, pluginData.businessCessationTransfereeQn):
        yield Validation.error(
            codes="IRD.NVAD-E-1070",
            msg=_(
                "BusinessCessationTransferee must be tagged when "
                "BusinessCessationTransferred is true."
            ),
            modelObject=getValidNonNilFactsByQname(
                modelXbrl, pluginData.businessCessationTransferredQn
            ),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1080(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1080: _(BIR52)_ BusinessCessationTransfereeBusinessNature
    required when BusinessCessationTransferred is true.

    BIR52 (partnership/sole-proprietorship) filings must tag
    BusinessCessationTransfereeBusinessNature whenever
    BusinessCessationTransferred is true. Skips entirely on BIR51
    filings, where this concept is not required.
    """
    modelXbrl = val.modelXbrl
    if not pluginData.isBir52(modelXbrl):
        return

    if not hasTrueValueFactByQname(modelXbrl, pluginData.businessCessationTransferredQn):
        return

    if not hasValidNonNilFactByQname(
        modelXbrl, pluginData.businessCessationTransfereeBusinessNatureQn
    ):
        yield Validation.error(
            codes="IRD.NVAD-E-1080",
            msg=_(
                "BusinessCessationTransfereeBusinessNature must be "
                "tagged when BusinessCessationTransferred is true in a "
                "BIR52 filing."
            ),
            modelObject=getValidNonNilFactsByQname(
                modelXbrl, pluginData.businessCessationTransferredQn
            ),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_nvad_e_1081(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """NVAD-E-1081: _(BIR51)_ BusinessCessationTransferredAssetsAssociated
    required when BusinessCessation is true.

    BIR51 (corporation) filings must tag
    BusinessCessationTransferredAssetsAssociated whenever
    BusinessCessation is true. Skips entirely on BIR52 filings, where
    this concept is not required.
    """
    modelXbrl = val.modelXbrl
    if not pluginData.isBir51(modelXbrl):
        return

    if not hasTrueValueFactByQname(modelXbrl, pluginData.businessCessationQn):
        return

    if not hasValidNonNilFactByQname(
        modelXbrl, pluginData.businessCessationTransferredAssetsAssociatedQn
    ):
        yield Validation.error(
            codes="IRD.NVAD-E-1081",
            msg=_(
                "BusinessCessationTransferredAssetsAssociated must be "
                "tagged when BusinessCessation is true in a BIR51 "
                "filing."
            ),
            modelObject=getValidNonNilFactsByQname(
                modelXbrl, pluginData.businessCessationQn
            ),
        )
