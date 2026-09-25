# file

Local documents (PDF, Word incl. `.doc` on macOS, PowerPoint `.pptx`, Excel, EPUB, RTF, HTML, Markdown, text) and
document URLs (a `.pdf` link, arxiv.org/pdf/…). An old PowerPoint `.ppt` can't be converted: ask for a `.pptx`.
The content file `content.md` has a header (title, author, date, pages, converter, a link to the copy
`original.<ext>`) and `## Document`: the text. In a PDF every paragraph starts with its page anchor:

```
[p. 3](original.pdf#page=3) The paragraph's text …
```

A slide deck has `## Slide n` headings; plain text (`.txt`, `.csv`, `.json`, `.tex`, ...) sits in one code fence;
other documents keep their own headings (one level below `## Document`).

## Flags

```bash
python3 $S/shared/prepare.py "<path or document URL>" [--refresh]
python3 $S/file/prepare.py "<any URL that serves a document>"   # when the web source says it is not a web page
```

- The file's sha256 is its id: the same document is reused wherever it lies or however it is named (the envelope
  says `reused: true`). `--refresh` converts it again.
- The same path or URL with new content is a new version when it looks like the same document (same title, or
  mostly the same words; `--refresh` forces it): it is converted into the same folder with `changed: true`, and
  `versions` lists the earlier hashes with their dates. The earlier summary is kept as `summary.<sha8>.md/.html`
  and the earlier file as `original.<sha8>.<ext>`, so `summary_exists` is false: write a new summary and say in
  one line that it is of the new version (compare with the old one when it helps). Otherwise (another document
  saved under the same name, e.g. `~/Downloads/paper.pdf`) it gets its own folder.
- The file is copied into the folder as `original.<ext>`, so the page anchors keep working when the file moves.
- Conversion: PDFs with `pdftotext` (poppler, required: it keeps the reading order of two-column papers), markitdown
  as the fallback. Everything else with markitdown (via uvx; the first run installs its dependencies and takes
  about a minute), then `pandoc` for docx/epub/odt/html. `.rtf`: pandoc first; `.doc`: macOS `textutil`.
  `converter` and `attempts` say what ran. Exit 2 when only a missing tool stopped it: run
  `$S/file/install-prerequisites.sh`.
- A URL is downloaded first (up to 500 MB). The web source sends a URL that serves a PDF here (it says `not a web
  page`): run `file/prepare.py` with it. A server that answers with an HTML page (a captcha or login) instead of
  the document is an error: ask the user to download it in a browser and pass the file.

## Anchor links

Copy `[p. n](original.pdf#page=n)` next to the points it supports: the browser opens the copy at that page. The
links are relative to the document's folder, so they only work in that folder's `summary.md`: a digest across
several inputs must not copy them (cite "p. n" of the document in words, or link the document's summary page). For
documents without pages, name the section in words (`(§ Risks)`, `(slide 4)`); there is nothing to link to.

## Reading

Decide what kind of document it is first:

- **Paper:** the question, the method, the main results with their numbers, and the limits the authors state.
  Keep numbers and units exactly as written; cite the page of each result.
- **Report / whitepaper:** the findings and recommendations first, then the evidence for each.
- **Book / long document (> 50 pages):** chapter by chapter; say which parts you only skimmed.
- **Slides:** one line per slide group, not per slide; slides often lack context, so say where the argument is
  only implied.
- **Spreadsheet:** what the sheets hold, the columns, the ranges and totals that matter; no row-by-row retelling.

## Conversion problems

- **Almost no text** (a scanned PDF without a text layer): the script exits 1 and says so. Tell the user it needs
  OCR (e.g. `ocrmypdf`); don't summarize from the file name.
- **Garbled text** (a paragraph that jumps to another column, numbers split off tables, markitdown's fallback
  mixing two columns): read around it and say in one line that the conversion is rough in those places; cite the
  page so the user can check.
- Tables and figures: markitdown keeps simple tables; charts and figure contents are lost. Don't describe figures
  you can't see; mention that a figure exists when the text refers to it.

## Related reading (related section)

There is no related script for documents. For a paper: the works it builds on (from its references, with their
year) and newer work that cites or supersedes it, found with web search. For other documents: sources the
document names. Nothing worth listing: no section.

## Page and files

The page header shows the author and date; the full `content.md` is in the collapsed "Document" section. The folder
`documents/<parent-folder>/<file-stem>/` (a URL: `documents/<host>/<file-stem>/`) holds `summary.md`,
`summary.html`, `content.md`, `metadata.json` (`extras`: kind, original_path, original_file, pages, sha256, size,
converter, versions, aliases) and `original.<ext>` (earlier versions: `original.<sha8>.<ext>`,
`summary.<sha8>.md/.html`).

## Scripts (`scripts/file/`)

| Script | Does |
|---|---|
| `prepare.py` | path or URL → sha256 dedupe / new version / new folder → copy as `original.<ext>` → `convert.py` → `content.md` (page anchors) + `metadata.json` |
| `convert.py` | PDF: pdftotext → markitdown, page split and clean-up; others: markitdown → pandoc (textutil for .doc/.rtf); title, author and date from the document's properties |
