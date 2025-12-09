"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from typing import Iterable

from collections import defaultdict
from jaconv import jaconv
from lxml.etree import _Element

from arelle import XbrlConst
from arelle.ModelDocument import ModelDocument
from arelle.ModelObject import ModelObject
from arelle.typing import TypeGetText
from arelle.utils.validate.Validation import Validation

_: TypeGetText

# Table of content number sets per EDINET documentation:
# Figure "3-4-5 設定可能な目次番号の一覧" in "File Specification for EDINET Filing"
# https://disclosure2dl.edinet-fsa.go.jp/guide/static/disclosure/download/ESE140104.pdf
TOC_DIGITS = [
    '一',
    '二',
    '三',
    '四',
    '五',
    '六',
    '七',
    '八',
    '九',
    '十',
]
FULL_WIDTH_DIGIT_MAP = {
    str(d): jaconv.h2z(str(d), kana=True, ascii=True, digit=True)
    for d in range(0, 10)
}
KATAKANA_GOJUON_SEQUENCE = [
    # a-column
    'ア', 'イ', 'ウ', 'エ', 'オ',
    # k-column
    'カ', 'キ', 'ク', 'ケ', 'コ',
    # s-column
    'サ', 'シ', 'ス', 'セ', 'ソ',
    # t-column
    'タ', 'チ', 'ツ', 'テ', 'ト',
    # n-column
    'ナ', 'ニ', 'ヌ', 'ネ', 'ノ',
    # h-column
    'ハ', 'ヒ', 'フ', 'ヘ', 'ホ',
    # m-column
    'マ', 'ミ', 'ム', 'メ', 'モ',
    # y-column
    'ヤ', 'ユ', 'ヨ',
    # r-column
    'ラ', 'リ', 'ル', 'レ', 'ロ',
    # w-column
    'ワ', 'ヲ',
    # n-row
    'ン'
]
TOC_NUMBER_SETS = {
    1: {
        '第一部': [f'第{d}部' for d in TOC_DIGITS] + [f'第十{d}部' for d in TOC_DIGITS[:-1]] + ['第二十部']
    },
    2: {
        '第１': [
            '第' + ''.join(FULL_WIDTH_DIGIT_MAP[ddd] for ddd in dd)
            for dd in [
                str(d) for d in range(1, 61)
            ]
        ],
    },
    3: {
        '１': [
            ''.join(FULL_WIDTH_DIGIT_MAP[ddd] for ddd in dd)
            for dd in [
                str(d) for d in range(1, 61)
            ]
        ],
    },
    4: {
        '（１）': [
            '（' + ''.join(FULL_WIDTH_DIGIT_MAP[ddd] for ddd in dd) + '）'
            for dd in [
                str(d) for d in range(1, 61)
            ]
        ],
    },
    5: {
        '①': [chr(ord('①') + d) for d in range(0, 20)],
        f'（{KATAKANA_GOJUON_SEQUENCE[0]}）': [f'（{d}）' for d in KATAKANA_GOJUON_SEQUENCE],
        KATAKANA_GOJUON_SEQUENCE[0]: KATAKANA_GOJUON_SEQUENCE,
        '（ａ）': ['（' + chr(ord('ａ') + d) + '）' for d in range(0, 26)],
        'ａ': [chr(ord('ａ') + d) for d in range(0, 26)],
    },
}
SHALLOWEST_LEVEL = min(TOC_NUMBER_SETS.keys())
DEEPEST_LEVEL = max(TOC_NUMBER_SETS.keys())

PROHIBITED_BETWEEN_TAGS = frozenset({
    XbrlConst.qnXhtmlDel.localName,
    XbrlConst.qnXhtmlImg.localName,
    XbrlConst.qnXhtmlDel.clarkNotation,
    XbrlConst.qnXhtmlImg.clarkNotation,
})


class TableOfContentsBuilder:
    _currentDocument: ModelDocument | None
    _currentLevel: int
    _documents: list[ModelDocument]
    _floatingLevel: int | None
    _levelLabels: dict[int, set[str]]
    _levelPositions: dict[int, int]
    _levelSequences: dict[int, list[str] | None]
    _tocEntryCount: int
    _tocSequence: list[tuple[str, str, ModelObject]]
    _validations: list[Validation]

    def __init__(self) -> None:
        self._currentDocument = None
        self._currentLevel = SHALLOWEST_LEVEL
        self._floatingLevel = None
        self._levelLabels = defaultdict(set)
        self._levelPositions = defaultdict(int)
        self._levelSequences = {}
        self._documents = []
        self._tocEntryCount = 0
        self._tocSequence = []
        self._validations = []

    def _build(self) -> None:
        documents = sorted(self._documents, key=lambda doc: doc.basename)
        for document in documents:
            rootElt = document.xmlRootElement
            for elt in rootElt.iterdescendants():
                if not isinstance(elt, ModelObject):
                    continue
                if elt.elementQname.localName == 'title':
                    continue
                if elt.text is not None:
                    self._element(elt)

    def _checkCurrentLevelNext(self, number: str, nextPosition: int, currentSequence: list[str] | None) -> bool:

        # NEXT IN SEQUENCE
        # We can only move ahead in the sequence if it has been established AND
        # we have not reached the end of the allowed numbers in the sequence.
        if currentSequence is None:
            # No sequence established at this level.
            return False
        if nextPosition >= len(currentSequence):
            # We have reached the end of the sequence at this level.
            return False
        nextNumberInSequence = currentSequence[nextPosition]
        if number == nextNumberInSequence:
            # Increment the position at the current level.
            self._levelPositions[self._currentLevel] = self._levelPositions[self._currentLevel] + 1
            # Reset the floating status.
            self._floatingLevel = None
            return True
        return False

    def _checkDeepLevel(self, number: str) -> bool:
        # STARTING DEEPER SEQUENCE
        # We can move deeper one or more levels.
        if self._floatingLevel is not None:
            # We don't move deeper if we are floating.
            return False
        deeperStartingNumbers = {
            startingNumber: level
            for level in range(min(self._currentLevel + 1, DEEPEST_LEVEL), DEEPEST_LEVEL + 1)
            for startingNumber in TOC_NUMBER_SETS[level]
        }
        if number not in deeperStartingNumbers:
            # The number is not the first entry in a deeper level sequence.
            return False
        # Set the level to the deeper level.
        self._currentLevel = deeperStartingNumbers[number]
        # Establish the sequence at the deeper level.
        self._levelSequences[self._currentLevel] = TOC_NUMBER_SETS[self._currentLevel][number]
        # Reset the duplicates at the deeper level.
        self._levelLabels[self._currentLevel].clear()
        # Reset the position at the deeper level.
        self._levelPositions[self._currentLevel] = 1
        return True

    def _checkShallowLevel(self, number: str) -> bool:
        # RESUMING SHALLOWER SEQUENCE
        # We may be moving back up one or more levels.
        nextLevel = None
        for shallowLevel in reversed(range(SHALLOWEST_LEVEL, self._currentLevel)):
            shallowSequence = self._levelSequences.get(shallowLevel)
            # For each level, should we be checking earlier and later numbers in the sequence
            # to fire EC3002E or EC3003E?
            if shallowSequence is not None and number == shallowSequence[self._levelPositions[shallowLevel]]:
                # This is the next number in the upper sequence.
                # Move up one level.
                nextLevel = shallowLevel
                break
            shallowLevel -= 1
        if nextLevel is None:
            return False
        # For each level shallower than the new level down to the current level...
        for i in range(nextLevel + 1, self._currentLevel + 1):
            # Reset the position.
            self._levelPositions[i] = 0
            # Reset the duplicates.
            self._levelLabels[i].clear()
            # Reset the sequence.
            self._levelSequences[i] = None
        # Set the level to the shallower level.
        self._currentLevel = nextLevel
        # Increment the position at the shallower level.
        self._levelPositions[self._currentLevel] = self._levelPositions[self._currentLevel] + 1
        # Reset the floating status.
        self._floatingLevel = None
        return True

    def _closeDocument(self) -> None:
        assert self._currentDocument is not None, "No document is currently open."
        # EDINET.EC2001E: There must be at least one table of contents entry in each file.
        if self._tocEntryCount == 0:
            self._validations.append(Validation.error(
                codes='EDINET.EC2001E',
                msg=_("The table of contents is not listed at the beginning. "
                      "File name: '%(path)s'. "
                      "Please provide the table of contents entry for the file."),
                path=self._currentDocument.basename,
            ))
        self._currentDocument = None

    def _element(self, elt: ModelObject) -> None:
        # New document, close previous.
        if self._currentDocument is not None and self._currentDocument != elt.document:
            self._closeDocument()
        # First or new document, open document.
        if self._currentDocument is None:
            self._openDocument(elt.document)

        number, label, tail, eltsInLabel, eltsBetweenNumAndLabel = self._getTextParts(elt)

        textValue = ''.join(elt.textNodes())
        if (
                (label is None and ('【' in textValue or '】' in textValue)) or
                (tail is not None and ('【' in tail or '】' in tail))
        ):
            self._validations.append(Validation.error(
                codes='EDINET.EC2011E',
                msg=_("\"【\" or \"】\" is used in the text. "
                      "File name: '%(path)s' (line %(line)s). "
                      "Corner brackets (【】) cannot be used in the main text "
                      "except for the table of contents. Please delete the "
                      "corner brackets (【】) in the relevant file."),
                path=elt.document.basename,
                line=elt.sourceline,
                modelObject=elt,
            ))

        if label is None:
            return

        if len(eltsInLabel) > 0:
            self._validations.append(Validation.error(
                codes='EDINET.EC2008E',
                msg=_("The table of contents label contains HTML tags. "
                      "File name: '%(path)s' (line %(line)s). "
                      "HTML tags are not allowed in table of contents labels. "
                      "Please remove the HTML tags from the relevant file."),
                path=elt.document.basename,
                line=elt.sourceline,
                modelObject=elt,
            ))

        if any(
                e.tag in PROHIBITED_BETWEEN_TAGS
                for e in eltsBetweenNumAndLabel
        ):
            self._validations.append(Validation.error(
                codes='EDINET.EC2009E',
                msg=_("An invalid tag is used between the table of contents number "
                      "and the table of contents item. "
                      "File name: '%(path)s' (line %(line)s). "
                      "Please delete the tag (\"del\" or \"img\") used between the "
                      "table of contents number and the table of contents item of "
                      "the relevant file."),
                path=elt.document.basename,
                line=elt.sourceline,
                modelObject=elt,
            ))

        if '【' in label[1:]:
            self._validations.append(Validation.error(
                codes='EDINET.EC2004E',
                msg=_("The opening bracket (【) is repeated. "
                      "File name: '%(path)s' (line %(line)s). "
                      "When viewed in a browser, it is not possible to display "
                      "more than one table of contents item on one line. Please "
                      "delete the brackets (【) in the relevant file."),
                path=elt.document.basename,
                line=elt.sourceline,
                modelObject=elt,
            ))

        if '】' not in label:
            # EDINET.EC2007E: The table of contents entries must be enclosed in square brackets (】).
            self._validations.append(Validation.error(
                codes='EDINET.EC2007E',
                msg=_("The table of contents entry is not closed with '】'. "
                      "File name: '%(path)s' (line %(line)s). "
                      "Add a closing bracket (】) to match the open bracket (【) "
                      "in the table of contents entry for the file in question."),
                path=elt.document.basename,
                line=elt.sourceline,
                modelObject=elt,
            ))

        self._tocSequence.append((number, label, elt))
        self._tocEntryCount += 1

    def _getTextParts(
            self,
            elt: ModelObject
    ) -> tuple[str, str | None, str | None, list[ModelObject], list[ModelObject]]:
        """
        Determines the TOC number, label, and tail of a given element (if set correctly)
        based on the text nodes directly beneath the element.
        Also captures misplaced elements in provided lists for error handling.
        """
        eltsInLabel = []
        eltsBetweenNumAndLabel = []
        textParts = [(None, elt.text)] + [
            (child, child.tail)
            for child in elt.iterchildren()
        ]

        number = ''
        label = None
        tail = None
        while len(textParts) > 0:
            textElt, text = textParts.pop(0)

            # If we're iterating over an element, check if it's misplaced
            if textElt is not None:
                if number and label is None:
                    eltsBetweenNumAndLabel.append(textElt)
                if label is not None and '】' not in label and tail is None:
                    eltsInLabel.append(textElt)

            # If no text, move on
            if not text:
                continue

            if label is None:
                # We're building the number
                start, sep, end = text.partition('【')
                if sep:
                    number += start
                    label = sep  # Start the label
                    # Process the remainder of this text node next
                    textParts.insert(0, (None, end))
                else:
                    number += start
            elif tail is None:
                # We're building the label
                start, sep, end = text.partition('】')
                if sep:
                    label += start + sep
                    tail = ''  # Start the tail
                    # Process the remainder of this text node next
                    textParts.insert(0, (None, end))
                else:
                    label += start
            else:
                # We're building the tail
                tail += text

        return (
            number.strip(),
            label.strip() if label else label,
            tail.strip() if tail else tail,
            eltsInLabel,
            eltsBetweenNumAndLabel,
        )

    def _isFloating(self) -> bool:
        return self._floatingLevel is not None or self._currentLevel >= DEEPEST_LEVEL

    def _normalizeNumber(self, number: str) -> str:
        # EDINET does not support:
        # - Mixture of half-width and full-width digits within a number.
        # - Mixture of half-width and full-width parentheses within a number.
        # EDINET does support:
        # - Mixture of half-width digits with full-width parentheses, and vice versa.
        # We will normalize to full-width parantheses and digits for number validation.
        if "(" in number and "）" in number: # Half-width (, full-width ）
            return number
        if "（" in number and ")" in number: # Full-width (, half-width )
            return number
        paranthesesFullWidth: bool | None = None
        numbersFullWidth: bool | None = None
        for c in number:
            if c in ("(", ")"):
                if paranthesesFullWidth == True:
                    return number # Mix of half/full-width parantheses
                paranthesesFullWidth = False
            elif c in ("（", " ）"):
                if paranthesesFullWidth == False:
                    return number # Mix of half/full-width parantheses
                paranthesesFullWidth = True
            elif c in FULL_WIDTH_DIGIT_MAP:
                if numbersFullWidth == True:
                    return number # Mix of half/full-width digits
                numbersFullWidth = False
            elif c in FULL_WIDTH_DIGIT_MAP.values():
                if numbersFullWidth == False:
                    return number # Mix of half/full-width digits
                numbersFullWidth = True
        return jaconv.h2z(number, kana=True, ascii=True, digit=True)

    def _openDocument(self, modelDocument: ModelDocument) -> None:
        assert self._currentDocument is None, "Close current document before opening another."
        self._tocEntryCount = 0
        self._currentDocument = modelDocument

    def _validateItem(self, number: str, label: str, elt: ModelObject) -> Iterable[Validation]:
        # Convert to full-width, ONLY if fully half-width.
        # EDINET does not support a mixture of half-width and full-width digits in TOC numbers.
        number = self._normalizeNumber(number)
        nextPosition = self._levelPositions[self._currentLevel]
        currentSequence = self._levelSequences.get(self._currentLevel)

        # UN-NUMBERED (FLOATING) ITEM
        # Floating items trigger special behavior for following items
        # until the current or shallower level is resumed.
        if number == "":
            # Only trigger floating/warning if we are not already floating, and we
            # aren't already at the deepest level.
            if not self._isFloating():
                # EDINET.EC2002W: The table of contents number must be present.
                # Note from documentation: Even if the data content is normal, it may be identified as an
                # exception and a warning may be displayed.
                yield Validation.warning(
                    codes='EDINET.EC2002W',
                    msg=_("The table of contents number is not listed. "
                          "File name: '%(path)s' (line %(line)s). "
                          "Please include the table of contents number of the relevant file."),
                    path=elt.document.basename,
                    line=elt.sourceline,
                    modelObject=elt,
                )
                self._floatingLevel = self._currentLevel
            return

        if self._checkCurrentLevelNext(number, nextPosition, currentSequence):
            return
        if self._checkDeepLevel(number):
            return
        if self._checkShallowLevel(number):
            return

        # OTHER NUMBER IN CURRENT SEQUENCE
        if currentSequence is not None and  number in currentSequence:
            numberIndex = currentSequence.index(number)
            assert numberIndex != nextPosition
            # Is it repeating a previous number?
            if numberIndex < nextPosition:
                # EDINET.EC3002E: Table of contents numbers for table of contents entries
                # must not be repeated within the same hierarchy.
                yield Validation.error(
                    codes='EDINET.EC3002E',
                    msg=_("The table of contents number of the table of contents "
                          "item is duplicated in the same hierarchy. "
                          "File name: '%(path)s' (line %(line)s). "
                          "Please correct the table of contents number in the "
                          "table of contents entry of the relevant file."),
                    path=elt.document.basename,
                    line=elt.sourceline,
                    modelObject=elt,
                )
                return
            # Is it skipping ahead?
            if numberIndex > nextPosition:
                # EDINET.EC3003E: There must be no gaps in the table of contents numbers
                # within the same hierarchy.
                yield Validation.error(
                    codes='EDINET.EC3003E',
                    msg=_("There is a gap in the table of contents number "
                          "within the same hierarchy. "
                          "File name: '%(path)s' (line %(line)s). "
                          "Please enter the missing table of contents number "
                          "in the appropriate file."),
                    number=number,
                    label=label,
                    path=elt.document.basename,
                    line=elt.sourceline,
                    modelObject=elt,
                )
                # Jump ahead to minimize further errors.
                # Increment the position at the current level.
                self._levelPositions[self._currentLevel] = numberIndex + 1
                # Reset the floating status.
                self._floatingLevel = None
                return

        # INVALID NUMBER
        # Not un-numbered (floating), not next in sequence, not starting deeper sequence,
        # not resuming shallower sequence.
        if self._floatingLevel is None:
            # The difference between EC3004W and EC3005E is unclear based on documentation.
            # We will implement the higher level severity version of the two.
            # EDINET.EC3004W: The table of contents number of the table of contents
            # item must be set.
            # EDINET.EC3005E: The table of contents numbers for the table of contents
            # entries must be as specified in the format.
            yield Validation.error(
                codes='EDINET.EC3005E',
                msg=_("The table of contents number for item '%(number)s %(label)s' is incorrect. "
                      "File name: '%(path)s' (line %(line)s). "
                      "Please correct the table of contents number of the "
                      "table of contents item of the corresponding file."),
                number=number,
                label=label,
                path=elt.document.basename,
                line=elt.sourceline,
                modelObject=elt,
            )

    def addDocument(self, modelDocument: ModelDocument) -> None:
        self._documents.append(modelDocument)

    def validate(self) -> Iterable[Validation]:
        self._build()
        if self._currentDocument is not None:
            self._closeDocument()
        # Yield errors encountered during loading/build.
        yield from self._validations

        # Tracks the current level.
        self._currentLevel = SHALLOWEST_LEVEL
        # Tracks the current position in the sequence at each level.
        self._levelPositions: dict[int, int] = defaultdict(int)
        # Tracks the active number set at each level.
        self._levelSequences: dict[int, list[str] | None] = {
            self._currentLevel: next(iter(TOC_NUMBER_SETS[self._currentLevel].values()))
        }
        # Tracks unique labels within a sequence.
        self._levelLabels = defaultdict(set)
        # Tracks floating status.
        self._floatingLevel = None
        for number, label, elt in self._tocSequence:
            yield from self._validateItem(number, label, elt)

            # We are only concerned about duplicates if we are not floating.
            if not self._isFloating():
                if label in self._levelLabels[self._currentLevel]:
                    # EDINET.EC2005E: Table of contents entries must not be duplicated.
                    # Note: Sample filings suggest this applies to entries that are
                    # siblings within the hierarchy.
                    yield Validation.error(
                        codes='EDINET.EC2005E',
                        msg=_("The table of contents item ('%(label)s') is duplicated. "
                              "File name: '%(path)s' (line %(line)s). "
                              "Please remove the duplicate table of contents in the appropriate file."),
                        label=label,
                        path=elt.document.basename,
                        line=elt.sourceline,
                        modelObject=elt,
                    )
                else:
                    self._levelLabels[self._currentLevel].add(label)

            if not self._isFloating():
                # EDINET.EC2003E: The table of contents must be no longer than 384 bytes
                # (equivalent to 128 full-width characters).
                if len(label.encode('utf-8')) > 384:
                    yield Validation.error(
                        codes='EDINET.EC2003E',
                        msg=_("The table of contents entry exceeds 384 bytes. "
                              "File name: '%(path)s' (line %(line)s). "
                              "Please modify the table of contents of the relevant "
                              "file so that it is within 384B (bytes) (equivalent to "
                              "128 full-width characters)."),
                        path=elt.document.basename,
                        line=elt.sourceline,
                        modelObject=elt,
                    )

            # Uncomment for debugging output of TOC structure.
            # print(
            #     f'{" " if self._floatingLevel is not None else "|"}\t' * (self._currentLevel - 1) +
            #     f"{number} [{label}] \t{elt.document.basename}"
            # )
