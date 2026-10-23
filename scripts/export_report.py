"""
Export docs/final-report.md to Word (.docx) and PDF for hand-in.
===============================================================

WHY THIS FILE EXISTS
--------------------
The report is written in Markdown so it lives in Git next to the code (reviewable,
diffable). The lecturer needs a document. This script turns the Markdown into a
Word file and a PDF with the copy of Microsoft Word installed on this machine, so
nobody has to re-format the report by hand after every change.

HOW IT WORKS (data flow)
------------------------
  docs/final-report.md
     │ 1. pre-process (this file):
     │      - a "[FIGURE n — PLACEHOLDER] ... Save as: `docs/images/x.png`" line becomes
     │        the real picture if docs/images/x.png exists, otherwise a grey "insert here" box
     │      - ```mermaid blocks are dropped (Word cannot draw Mermaid; the figure replaces them)
     │      - relative image links (images/...) become absolute paths Word can open
     │ 2. Markdown → HTML with the `markdown` package (tables, fenced code) + print CSS
     ▼
  temporary .html
     │ 3. PowerShell drives Word through COM (Word.Application):
     │      open the HTML → embed the pictures → A4, 2 cm margins → save .docx and .pdf
     ▼
  docs/final/final-report.docx  +  docs/final/final-report.pdf   (and the page count)

FOR GROUPMATES ADDING IMAGES
----------------------------
Save the image under the exact name given in its placeholder (see docs/final/PLACEHOLDERS.md),
then run this script again. The placeholder is replaced by the picture automatically.

Usage (PowerShell, from the repo root):
  pip install -r requirements-docs.txt
  py scripts\\export_report.py

Requires Microsoft Word on Windows. Owner: Boonabaana Bronia, built with Claude Code.
"""

# ---------------------------------------------------------------------------
# Imports and paths
# ---------------------------------------------------------------------------
import html                                    # escape placeholder text inside HTML
import re                                      # find placeholder lines and mermaid blocks
import subprocess                              # run the PowerShell/Word step
import sys
import tempfile
from pathlib import Path

import struct                                  # read a PNG's width and height from its header

import markdown                                # Markdown -> HTML (pip install markdown)

ROOT = Path(__file__).resolve().parents[1]     # repo root (this file is in scripts/)
SOURCE = ROOT / "docs" / "final-report.md"
OUT_DIR = ROOT / "docs" / "final"
DOCX = OUT_DIR / "final-report.docx"
PDF = OUT_DIR / "final-report.pdf"
IMAGE_WIDTH_PX = 400                           # about 10.5 cm: keeps each figure to roughly a quarter page

# A placeholder line, as written in the report:
# > **[FIGURE 4 — PLACEHOLDER]** Caption: ... · Insert: ... · Save as: `docs/images/x.png` · Owner: ...
PLACEHOLDER = re.compile(
    r"^> \*\*\[FIGURE (?P<n>\d+) — PLACEHOLDER\]\*\* Caption: (?P<caption>.*?) · "
    r"Insert: (?P<insert>.*?) · Save as: `(?P<path>[^`]+)` · Owner: (?P<owner>.*)$",
    re.MULTILINE,
)
MERMAID = re.compile(r"^```mermaid\n.*?^```\n", re.MULTILINE | re.DOTALL)
RELATIVE_IMAGE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<src>images/[^)]+)\)")

# Print styling. Word understands a useful subset of CSS when it opens HTML.
CSS = """
body  { font-family: Calibri, Arial, sans-serif; font-size: 10.5pt; line-height: 1.2; }
p, li { margin-top: 0; margin-bottom: 5pt; }          /* Word adds ~14pt around every <p> otherwise */
ul, ol { margin-top: 0; margin-bottom: 5pt; }
h1    { color: #1B2A5B; font-size: 20pt; }
h2    { color: #1B2A5B; font-size: 15pt; border-bottom: 1px solid #1B2A5B; margin: 14pt 0 6pt 0; }
h3    { color: #1B2A5B; font-size: 12pt; margin: 10pt 0 4pt 0; }
table { border-collapse: collapse; width: 100%; font-size: 8.5pt; margin: 6pt 0; }
th, td { border: 1px solid #9AA3B5; padding: 1pt 4pt; vertical-align: top; line-height: 1.1; }
th    { background: #E8ECF5; }
pre   { font-family: Consolas, monospace; font-size: 8pt; background: #F4F6FA;
        border: 1px solid #D5DAE5; padding: 6pt; }
code  { font-family: Consolas, monospace; font-size: 9.5pt; }
blockquote { border-left: 3px solid #F5A100; margin-left: 0; padding-left: 8pt; color: #333; }
.ph   { border: 2px dashed #9AA3B5; background: #F2F2F2; padding: 8pt; margin: 6pt 0;
        text-align: center; color: #555; font-size: 9.5pt; }
.ph b { color: #B00020; }
.cap  { font-style: italic; font-size: 9.5pt; text-align: center; }
"""


# ---------------------------------------------------------------------------
# Step 1: pre-process the Markdown
# ---------------------------------------------------------------------------
def _img_tag(image: Path, alt: str = "") -> str:
    """
    An <img> with BOTH width and height. Given only a width, Word keeps the picture's
    native pixel height, which stretched every screenshot to a full page. So the height
    is computed from the PNG header (bytes 16-24 hold width and height) to keep the ratio.
    """
    size = f'width="{IMAGE_WIDTH_PX}"'
    with open(image, "rb") as f:
        head = f.read(24)
    if head[:8] == b"\x89PNG\r\n\x1a\n":                    # the PNG signature
        w, h = struct.unpack(">II", head[16:24])
        size += f' height="{round(IMAGE_WIDTH_PX * h / w)}"'
    return f'<p style="text-align:center"><img src="{image.as_uri()}" {size} alt="{html.escape(alt)}"></p>'


def _figure(match: re.Match) -> str:
    """Real picture if the file exists, otherwise a visible 'insert here' box."""
    n, caption, path = match["n"], match["caption"], match["path"]
    image = ROOT / path
    if image.exists():
        return f'\n{_img_tag(image, caption)}\n<p class="cap">Figure {n} — {html.escape(caption)}</p>\n'
    return (f'\n<div class="ph"><b>[FIGURE {n} — INSERT IMAGE HERE]</b><br>{html.escape(caption)}<br>'
            f'Insert: {html.escape(match["insert"])}<br>Save as: {html.escape(path)}</div>\n')


def preprocess(text: str) -> str:
    text = MERMAID.sub("", text)                         # Word cannot render Mermaid
    text = PLACEHOLDER.sub(_figure, text)                # pictures or insert-here boxes
    text = RELATIVE_IMAGE.sub(                           # images/x.png -> absolute file URI, fixed size
        lambda m: _img_tag(ROOT / "docs" / m["src"], m["alt"]), text)
    return text


# ---------------------------------------------------------------------------
# Step 2: Markdown -> HTML document
# ---------------------------------------------------------------------------
def to_html(text: str) -> str:
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    return (f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>Final Report</title>'
            f"<style>{CSS}</style></head><body>{body}</body></html>")


# ---------------------------------------------------------------------------
# Step 3: Word (COM, through PowerShell) -> .docx + .pdf, and count the pages
# ---------------------------------------------------------------------------
POWERSHELL = r"""
$ErrorActionPreference = 'Stop'
$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {
    $doc = $word.Documents.Open('{html}', $false, $true)      # path, ConfirmConversions, ReadOnly
    $doc.ActiveWindow.View.Type = 3                           # print layout, so page counts are real
    foreach ($shape in @($doc.InlineShapes)) {                # embed linked pictures in the file
        if ($shape.LinkFormat) { $shape.LinkFormat.SavePictureWithDocument = $true; $shape.LinkFormat.BreakLink() }
    }
    $ps = $doc.PageSetup
    $ps.PageWidth = 595.3; $ps.PageHeight = 841.9             # A4 in points
    $ps.TopMargin = 56.7; $ps.BottomMargin = 56.7; $ps.LeftMargin = 56.7; $ps.RightMargin = 56.7   # 2 cm
    $doc.SaveAs2('{docx}', 16)                                # 16 = wdFormatDocumentDefault (.docx)
    $doc.ExportAsFixedFormat('{pdf}', 17)                     # 17 = wdExportFormatPDF
    $total = $doc.ComputeStatistics(2)                        # 2 = wdStatisticPages
    # Body = everything before the "References" heading (the brief's 8-12 pages).
    $find = $doc.Content
    $refPage = 0
    if ($find.Find.Execute('References')) {
        while ($find.Paragraphs(1).Range.Text.Trim() -ne 'References' -and $find.Find.Execute('References')) { }
        $refPage = $find.Information(3)                      # 3 = wdActiveEndPageNumber
    }
    Write-Output "PAGES total=$total references_start=$refPage"
    $doc.Close($false)
} finally {
    $word.Quit()
}
"""


def export_with_word(html_path: Path) -> str:
    script = (POWERSHELL.replace("{html}", str(html_path))
              .replace("{docx}", str(DOCX)).replace("{pdf}", str(PDF)))
    result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                            capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"Word export failed:\n{result.stderr or result.stdout}")
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    text = preprocess(SOURCE.read_text(encoding="utf-8"))
    missing = len(re.findall(r"INSERT IMAGE HERE", text))
    with tempfile.TemporaryDirectory() as folder:
        html_path = Path(folder) / "final-report.html"
        html_path.write_text(to_html(text), encoding="utf-8")
        pages = export_with_word(html_path)
    print(f"Wrote {DOCX.relative_to(ROOT)} and {PDF.relative_to(ROOT)}")
    print(pages + "   (body = pages before 'References'; the brief asks for 8-12)")
    print(f"Figure placeholders still waiting for an image: {missing} (see docs/final/PLACEHOLDERS.md)")


if __name__ == "__main__":
    sys.exit(main())
