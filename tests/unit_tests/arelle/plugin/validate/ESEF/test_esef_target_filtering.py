from types import SimpleNamespace

from arelle.plugin.validate.ESEF.Util import hasEsefTaxonomy, isEsefExcludedInstance, shouldRunEsefValidationRules

ESEF_NAMESPACE = "http://www.esma.europa.eu/taxonomy/2024-03-27/esef_cor"
NON_ESEF_NAMESPACE = "http://xbrl.frc.org.uk/fr/2022-01-01/core"


def make_model_xbrl(
    namespace_docs: dict | None = None,
    ixds_target: object = object,
    supplemental_models: list | None = None,
    is_supplemental: bool = False,
    primary_namespace_docs: dict | None = None,
) -> SimpleNamespace:
    kwargs: dict = {"namespaceDocs": namespace_docs or {}}
    if ixds_target is not object:
        kwargs["ixdsTarget"] = ixds_target
    if supplemental_models is not None:
        kwargs["supplementalModelXbrls"] = supplemental_models
    if is_supplemental:
        kwargs["isSupplementalIxdsTarget"] = True
    model_xbrl = SimpleNamespace(**kwargs)
    if is_supplemental:
        primary = SimpleNamespace(
            namespaceDocs=primary_namespace_docs or {ESEF_NAMESPACE: []},
            supplementalModelXbrls=[model_xbrl],
        )
    else:
        primary = model_xbrl
    disclosure_system = SimpleNamespace(ESEFplugin=True)
    model_xbrl.modelManager = SimpleNamespace(modelXbrl=primary, disclosureSystem=disclosure_system)
    return model_xbrl


def make_val(
    model_xbrl: SimpleNamespace,
    auth_param: dict | None = None,
    validate_disclosure_system: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        modelXbrl=model_xbrl,
        validateDisclosureSystem=validate_disclosure_system,
        authParam=auth_param or {},
    )


class TestHasEsefTaxonomy:
    def test_returns_true_with_esef_namespace(self) -> None:
        model = SimpleNamespace(namespaceDocs={ESEF_NAMESPACE: []})
        assert hasEsefTaxonomy(model) is True

    def test_returns_true_with_https_esef_namespace(self) -> None:
        model = SimpleNamespace(namespaceDocs={"https://www.esma.europa.eu/taxonomy/2022-03-24/esef_cor": []})
        assert hasEsefTaxonomy(model) is True

    def test_returns_false_without_esef_namespace(self) -> None:
        model = SimpleNamespace(namespaceDocs={NON_ESEF_NAMESPACE: []})
        assert hasEsefTaxonomy(model) is False

    def test_returns_false_with_empty_namespaces(self) -> None:
        model = SimpleNamespace(namespaceDocs={})
        assert hasEsefTaxonomy(model) is False


class TestIsEsefExcludedInstance:
    def test_not_excluded_when_esef_taxonomy_present(self) -> None:
        model_xbrl = make_model_xbrl(namespace_docs={ESEF_NAMESPACE: []}, ixds_target=None)
        val = make_val(model_xbrl, auth_param={"ixTargetUsage": "allowed"})
        assert isEsefExcludedInstance(val) is False

    def test_not_excluded_when_not_ixds(self) -> None:
        model_xbrl = make_model_xbrl(namespace_docs={NON_ESEF_NAMESPACE: []})
        val = make_val(model_xbrl, auth_param={"ixTargetUsage": "allowed"})
        assert isEsefExcludedInstance(val) is False

    def test_not_excluded_when_ix_target_usage_not_allowed(self) -> None:
        model_xbrl = make_model_xbrl(namespace_docs={NON_ESEF_NAMESPACE: []}, ixds_target="DKGAAP")
        val = make_val(model_xbrl, auth_param={"ixTargetUsage": "warning"})
        assert isEsefExcludedInstance(val) is False

    def test_excluded_when_multi_target_and_another_has_esef(self) -> None:
        model_xbrl = make_model_xbrl(
            namespace_docs={NON_ESEF_NAMESPACE: []},
            ixds_target="DKGAAP",
            is_supplemental=True,
        )
        val = make_val(model_xbrl, auth_param={"ixTargetUsage": "allowed"})
        assert isEsefExcludedInstance(val) is True

    def test_not_excluded_when_no_target_has_esef(self) -> None:
        model_xbrl = make_model_xbrl(
            namespace_docs={NON_ESEF_NAMESPACE: []},
            ixds_target=None,
            supplemental_models=[],
        )
        val = make_val(model_xbrl, auth_param={"ixTargetUsage": "allowed"})
        assert isEsefExcludedInstance(val) is False

    def test_excluded_for_supplemental_without_esef(self) -> None:
        model_xbrl = make_model_xbrl(
            namespace_docs={NON_ESEF_NAMESPACE: []},
            ixds_target="UKFRC",
            is_supplemental=True,
        )
        val = make_val(model_xbrl, auth_param={"ixTargetUsage": "allowed"})
        assert isEsefExcludedInstance(val) is True


class TestShouldRunEsefValidationRules:
    def test_false_when_excluded(self) -> None:
        model_xbrl = make_model_xbrl(
            namespace_docs={NON_ESEF_NAMESPACE: []},
            ixds_target="DKGAAP",
            is_supplemental=True,
        )
        val = make_val(model_xbrl, auth_param={"ixTargetUsage": "allowed"})
        assert shouldRunEsefValidationRules(val) is False

    def test_true_when_esef_instance(self) -> None:
        model_xbrl = make_model_xbrl(namespace_docs={ESEF_NAMESPACE: []}, ixds_target=None)
        val = make_val(model_xbrl, auth_param={"ixTargetUsage": "allowed"})
        assert shouldRunEsefValidationRules(val) is True

    def test_false_when_disclosure_system_not_validated(self) -> None:
        model_xbrl = make_model_xbrl(namespace_docs={ESEF_NAMESPACE: []}, ixds_target=None)
        val = make_val(model_xbrl, auth_param={"ixTargetUsage": "allowed"}, validate_disclosure_system=False)
        assert shouldRunEsefValidationRules(val) is False

    def test_false_when_esef_not_selected(self) -> None:
        model_xbrl = make_model_xbrl(namespace_docs={ESEF_NAMESPACE: []}, ixds_target=None)
        model_xbrl.modelManager.disclosureSystem = SimpleNamespace(ESEFplugin=False)
        val = make_val(model_xbrl, auth_param={"ixTargetUsage": "allowed"})
        assert shouldRunEsefValidationRules(val) is False
