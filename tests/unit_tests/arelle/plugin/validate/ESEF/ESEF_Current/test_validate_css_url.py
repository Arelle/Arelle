from unittest import TestCase
from unittest.mock import MagicMock

from arelle.plugin.validate.ESEF.ESEF_Current.ValidateXbrlFinally import validateCssUrl

class TestValidateCssUrl(TestCase):
    def test_url_function(self) -> None:
        modelXbrl = MagicMock()
        validateCssUrl(
            '* { background: url("http://example.com") }',
            MagicMock(), modelXbrl, MagicMock(), MagicMock(), MagicMock())
        expected = dict(
            level='ERROR',
            codes=('ESEF.3.5.1.inlineXbrlDocumentContainsExternalReferences', 'NL.NL-KVK.3.6.2.1.inlineXbrlDocumentContainsExternalReferences'),
        )
        self.assertLessEqual(expected.items(), modelXbrl.log.call_args.kwargs.items())

    def test_url_token(self) -> None:
        modelXbrl = MagicMock()
        validateCssUrl(
            '* { background: url(http://example.com) }',
            MagicMock(), modelXbrl, MagicMock(), MagicMock(), MagicMock())
        expected = dict(
            level='ERROR',
            codes=('ESEF.3.5.1.inlineXbrlDocumentContainsExternalReferences', 'NL.NL-KVK.3.6.2.1.inlineXbrlDocumentContainsExternalReferences'),
        )
        self.assertLessEqual(expected.items(), modelXbrl.log.call_args.kwargs.items())
