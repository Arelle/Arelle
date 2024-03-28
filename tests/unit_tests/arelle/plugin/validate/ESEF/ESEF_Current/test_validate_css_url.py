from unittest import TestCase
from unittest.mock import MagicMock

from arelle.plugin.validate.ESEF.ESEF_Current.ValidateXbrlFinally import validateCssUrl

class TestValidateCssUrl(TestCase):
    def test_url_function(self) -> None:
        modelXbrl = MagicMock()
        validateCssUrl(
            '* { background: url("http://example.com") }',
            MagicMock(), modelXbrl, MagicMock(), MagicMock(), MagicMock())
        self.assertEqual(modelXbrl.error.call_args.args[0], 'ESEF.4.1.6.xHTMLDocumentContainsExternalReferences')

    def test_url_token(self) -> None:
        modelXbrl = MagicMock()
        validateCssUrl(
            '* { background: url(http://example.com) }',
            MagicMock(), modelXbrl, MagicMock(), MagicMock(), MagicMock())
        self.assertEqual(modelXbrl.error.call_args.args[0], 'ESEF.4.1.6.xHTMLDocumentContainsExternalReferences')
