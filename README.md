wkhtmltopdf and wkhtmltoimage
-----------------------------

# wkhtmltopdf gui with enhancements

this is a graphical user interface (gui) for the `wkhtmltopdf` command-line tool. i forked an initial concept to make a more usable gui and then added several features, most notably a website crawler.

## basic usage

1.  **input**:
    *   add html files directly using "add file(s)".
    *   add individual urls using "add url".
    *   drag and drop html files onto the input list (if `tkinterdnd2` is installed).
    *   use the "site crawler" to discover and add all html pages from a website:
        *   enter a "start url" (e.g., `https://example.com`).
        *   optionally, check "include subdomains" to crawl links on subdomains of the start url's main domain (e.g., `blog.example.com`).
        *   set "max pages" to limit the crawl (0 for unlimited).
        *   click "crawl site & add urls". discovered html pages will be added to the input list.
        *   *note: the crawler currently does not respect `robots.txt`.*

2.  **pdf options**:
    *   configure page size, orientation, grayscale, javascript, table of contents (toc), and margins. these options will apply to each pdf generated.

3.  **output**:
    *   select an "output directory" using "browse...". all generated pdfs will be saved here. each input item will produce a separate pdf file, named based on its source.

4.  **conversion**:
    *   click "generate command preview" to see an example of the `wkhtmltopdf` command that will be used for the first item in your input list.
    *   click "convert to pdf(s)" to start the process. the application will process each item in the input list one by one.

5.  **log**:
    *   the "log / status" area shows progress, `wkhtmltopdf` output, and any errors.

## requirements

*   `wkhtmltopdf` must be installed and ideally in your system's path. if not found, the gui will prompt you to browse for the executable.
*   python 3
*   `tkinter` (usually included with python)
*   `tkinterdnd2` (optional, for drag-and-drop support): `pip install tkinterdnd2`
*   `requests` (for the crawler): `pip install requests`
*   `beautifulsoup4` (for the crawler): `pip install beautifulsoup4`



wkhtmltopdf and wkhtmltoimage are command line tools to render HTML into PDF
and various image formats using the QT Webkit rendering engine. These run
entirely "headless" and do not require a display or display service.

See https://wkhtmltopdf.org for updated documentation.

## Building
wkhtmltopdf has its own dedicated repository for building and packaging.

See https://github.com/wkhtmltopdf/packaging
