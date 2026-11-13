"""Build the coursework Word report from the accompanying Markdown text."""
from pathlib import Path
import re

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'Saloon_Management_System_Final_Report.docx'


def format_paragraph(paragraph, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY):
    paragraph.alignment = alignment
    paragraph.paragraph_format.line_spacing = 1.5
    paragraph.paragraph_format.space_after = Pt(3)
    for run in paragraph.runs:
        run.font.name = 'Trebuchet MS'
        run.font.size = Pt(12)


def add_table(document, lines):
    rows = [[cell.strip() for cell in line.strip('|').split('|')] for line in lines]
    rows = [row for row in rows if not all(re.fullmatch(r'[:\- ]+', cell) for cell in row)]
    table = document.add_table(rows=0, cols=len(rows[0]))
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for index, values in enumerate(rows):
        cells = table.add_row().cells
        for cell, value in zip(cells, values):
            paragraph = cell.paragraphs[0]
            paragraph.add_run(value).bold = index == 0
            format_paragraph(paragraph, WD_ALIGN_PARAGRAPH.LEFT)
            if index == 0:
                shading = OxmlElement('w:shd')
                shading.set(qn('w:fill'), 'EEE5F2')
                cell._tc.get_or_add_tcPr().append(shading)
        properties = table.rows[-1]._tr.get_or_add_trPr()
        properties.append(OxmlElement('w:cantSplit'))
    document.add_paragraph().paragraph_format.space_after = Pt(0)


def build_report():
    document = Document()
    section = document.sections[0]
    section.page_width = Inches(8.27)
    section.page_height = Inches(11.69)
    section.top_margin = Inches(0.65)
    section.bottom_margin = Inches(0.65)
    section.left_margin = Inches(0.75)
    section.right_margin = Inches(0.75)
    section.header_distance = Inches(0.25)
    section.footer_distance = Inches(0.25)

    for name in ('Normal', 'Title', 'Heading 1', 'Heading 2', 'Heading 3', 'List Bullet'):
        style = document.styles[name]
        style.font.name = 'Trebuchet MS'
        style.font.size = Pt(12)
        style.font.color.rgb = RGBColor.from_string('22172A')
        style.paragraph_format.line_spacing = 1.5
        style.paragraph_format.space_after = Pt(3)
        if name.startswith('Heading'):
            style.font.bold = True
            style.paragraph_format.space_before = Pt(6)

    header = section.header.paragraphs[0]
    header.add_run('CSC8101 | Saloon Management System')
    format_paragraph(header, WD_ALIGN_PARAGRAPH.RIGHT)
    footer = section.footer.paragraphs[0]
    footer.add_run('Page ')
    field = OxmlElement('w:fldSimple')
    field.set(qn('w:instr'), 'PAGE')
    footer._p.append(field)
    footer.add_run(' of ')
    total = OxmlElement('w:fldSimple')
    total.set(qn('w:instr'), 'NUMPAGES')
    footer._p.append(total)
    format_paragraph(footer, WD_ALIGN_PARAGRAPH.CENTER)

    lines = (ROOT / 'FINAL_REPORT.md').read_text(encoding='utf-8').splitlines()
    index, page = 0, 1
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if line == '<!-- PAGE -->':
            document.add_page_break()
            page += 1
        elif line.startswith('|'):
            block = []
            while index < len(lines) and lines[index].startswith('|'):
                block.append(lines[index])
                index += 1
            add_table(document, block)
            continue
        elif line == '```diagram':
            block = []
            index += 1
            while lines[index] != '```':
                block.append(lines[index])
                index += 1
            paragraph = document.add_paragraph('\n'.join(block))
            format_paragraph(paragraph, WD_ALIGN_PARAGRAPH.LEFT)
            paragraph.paragraph_format.keep_together = True
        elif line.startswith('#'):
            level = len(line) - len(line.lstrip('#'))
            paragraph = document.add_paragraph(line[level:].strip(), style=f'Heading {min(level, 3)}')
            format_paragraph(paragraph, WD_ALIGN_PARAGRAPH.LEFT)
            if page == 1:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif line.startswith('- '):
            paragraph = document.add_paragraph(line[2:], style='List Bullet')
            format_paragraph(paragraph)
        else:
            paragraph = document.add_paragraph(line)
            alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            if page == 1 and line.startswith(('Uganda', 'MSc', 'CSC8101', 'Student name:', 'Registration number:', 'Submission date:', 'GitHub repository:')):
                alignment = WD_ALIGN_PARAGRAPH.CENTER
            format_paragraph(paragraph, alignment)
        index += 1

    document.core_properties.title = 'Saloon Management System - CSC8101 Final Report'
    document.core_properties.subject = 'MSc Object-Oriented Programming Coursework'
    document.core_properties.author = '[INSERT FULL NAME]'
    document.save(OUTPUT)
    print(OUTPUT)


if __name__ == '__main__':
    build_report()
