import pytest
from parser import ParsedElement, classifyBlock, headingLevel, headingText, updateSection, makeId


class TestClassifyBlock:
    def test_heading(self):
        assert classifyBlock('# Main Title') == 'heading'
        assert classifyBlock('## Subtitle') == 'heading'
        assert classifyBlock('### Third Level') == 'heading'

    def test_table(self):
        assert classifyBlock('| Header 1 | Header 2 |') == 'table'
        assert classifyBlock('| --- | --- |') == 'table'

    def test_list(self):
        assert classifyBlock('- Item 1') == 'list'
        assert classifyBlock('* Item 1') == 'list'
        assert classifyBlock('+ Item 1') == 'list'
        assert classifyBlock('1. Item 1') == 'list'
        assert classifyBlock('10. Item 1') == 'list'

    def test_paragraph(self):
        assert classifyBlock('This is a paragraph.') == 'paragraph'
        assert classifyBlock('Some text without special formatting.') == 'paragraph'


class TestHeadingLevel:
    def test_level_1(self):
        assert headingLevel('# Title') == 1

    def test_level_2(self):
        assert headingLevel('## Subtitle') == 2

    def test_level_3(self):
        assert headingLevel('### Third') == 3

    def test_level_6(self):
        assert headingLevel('###### Sixth') == 6


class TestHeadingText:
    def test_extract_text(self):
        assert headingText('# Main Title') == 'Main Title'
        assert headingText('## Subtitle') == 'Subtitle'
        assert headingText('### Third Level') == 'Third Level'

    def test_trim_whitespace(self):
        assert headingText('#   Title with spaces   ') == 'Title with spaces'


class TestUpdateSection:
    def test_root_level(self):
        result = updateSection([], 1, 'Chapter 1')
        assert result == ['Chapter 1']

    def test_same_level(self):
        result = updateSection(['Chapter 1'], 1, 'Chapter 2')
        assert result == ['Chapter 2']

    def test_deeper_level(self):
        result = updateSection(['Chapter 1'], 2, 'Section 1.1')
        assert result == ['Chapter 1', 'Section 1.1']

    def test_skip_levels(self):
        result = updateSection(['Chapter 1', 'Section 1.1'], 1, 'Chapter 2')
        assert result == ['Chapter 2']

    def test_deep_nesting(self):
        initial = ['Chapter 1', 'Section 1.1', 'Subsection 1.1.1']
        result = updateSection(initial, 2, 'Section 1.2')
        assert result == ['Chapter 1', 'Section 1.2']


class TestMakeId:
    def test_id_format(self):
        docId = makeId('my_doc', 1)
        assert docId == 'my_doc-0001'

    def test_id_padding(self):
        assert makeId('doc', 1) == 'doc-0001'
        assert makeId('doc', 10) == 'doc-0010'
        assert makeId('doc', 100) == 'doc-0100'
        assert makeId('doc', 1000) == 'doc-1000'

    def test_different_doc_names(self):
        assert makeId('alpha', 5) == 'alpha-0005'
        assert makeId('beta', 5) == 'beta-0005'


class TestParsedElement:
    def test_element_creation(self, sample_element):
        assert sample_element.docName == 'test_doc'
        assert sample_element.elementType == 'paragraph'
        assert len(sample_element.sectionPath) == 2
        assert sample_element.accessLevel == 'internal'

    def test_element_with_no_section(self):
        elem = ParsedElement(
            docName='doc',
            sectionPath=[],
            page=1,
            elementType='paragraph',
            text='Text',
            elementId='elem-0001',
            accessLevel='internal',
        )
        assert elem.sectionPath == []

    def test_element_with_no_page(self):
        elem = ParsedElement(
            docName='doc',
            sectionPath=['Section'],
            page=None,
            elementType='paragraph',
            text='Text',
            elementId='elem-0001',
            accessLevel='internal',
        )
        assert elem.page is None
