# file

Local documents (PDF, Word, PowerPoint, Excel, EPUB, HTML, Markdown, text) and document URLs (a `.pdf` link,
arxiv.org/pdf/…). The content file `content.md` has a header (title, author, date, pages, converter, a link to the
copy `original.<ext>`) and `## Document`: the text. In a PDF every paragraph starts with its page anchor:

```
[p. 3](original.pdf#page=3) The paragraph's text …
```

A slide deck has `## Slide n` headings; other documents keep their own headings (one level below `## Document`).

## Flags

```bash
python3 $S/shared/prepare.py "<path or document URL>" [--refresh]
python3 $S/file/prepare.py "<any URL that serves a document>"   # when the web source says it is not a web page
```

- The file's sha256 is its id: the same document is reused wherever it lies or however it is named (the envelope
  says `reused: true`). `--refresh` converts it again.
- The same path or URL with new content (an edited draft) is converted into the same folder: `changed: true` and
  `versions` lists the earlier hashes with their dates. Say in one line that this summary is of the new version.
- The file is copied into the folder as `original.<ext>`, so the page anchors keep working when the file moves.
- Conversion: markitdown first (via uvx; the first run installs its dependencies and takes about a minute), then
  `pdftotext` for PDFs or `pandoc` for docx/epub/odt/html. `converter` and `attempts` say what ran.
- A URL is downloaded first (up to 500 MB). The web source sends a URL that serves a PDF here (it says `not a web
  page`): run `file/prepare.py` with it.

## Anchor links

Copy `[p. n](original.pdf#page=n)` next to the points it supports: the browser opens the copy at that page. For
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
- **Garbled text** (two-column layouts mixed, words run together, numbers split off tables): read around it and
  say in one line that the conversion is rough in those places; cite the page so the user can check.
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
converter, versions, aliases) and `original.<ext>`.

## Scripts (`scripts/file/`)

| Script | Does |
|---|---|
| `prepare.py` | path or URL → sha256 dedupe → copy as `original.<ext>` → `convert.py` → `content.md` (page anchors) + `metadata.json` |
| `convert.py` | markitdown → pdftotext / pandoc; PDF page split and clean-up; title, author and date from the document's properties |
