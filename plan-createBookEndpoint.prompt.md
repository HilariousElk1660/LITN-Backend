## Plan: create_book PDF upload + processing

Brief TL;DR: convert `POST /create_book` into a multipart/form-data endpoint that accepts metadata plus a PDF, upload the PDF to S3, extract text with PyMuPDF/pdfplumber + OCR fallback, split into chapters/pages, save book metadata and structured contents in the database, and store translated versions.

### Steps
1. Define the endpoint as multipart/form-data in `routers/admin.py`
   - keep metadata fields from `CreateBook`
   - add `pdf_file: UploadFile = File(...)`
   - use `Form(...)` for string/date fields if needed

2. Add S3 upload support in `storage/s3.py`
   - create an S3 client wrapper using `boto3`
   - add helper `upload_fileobj(fileobj, bucket, key, content_type)`
   - return public or signed S3 URL plus stored key

3. Add PDF extraction service in `services/book_service.py`
   - implement `extract_pdf_text(pdf_path)` using `PyMuPDF` first
   - fallback to `pdfplumber` if needed
   - add optional OCR fallback with `pytesseract` for image-only pages

4. Add PDF structure parsing and chapter/page splitting
   - detect chapters by scanning page text for headings like `Chapter`, `CHAPTER`, `Chapter \d+`, or author-defined chapter titles
   - split logical content into:
     - `book`
     - `chapters[]` with chapter title/number/page ranges
     - `pages[]` with page number + extracted text
   - store a JSON structure for the book outline

5. Save book records and translations
   - persist base metadata in `books` table:
     - `admin_name`, `admin_id`, `author_name`, `book_name`, `category`, `published_date`, `price`, `pdf_s3_url`, `structure_json`
   - persist chapter/page details in new tables:
     - `chapters` or `book_chapters`
     - `book_pages`
   - persist translations in `book_translations`
     - `book_id`, `language_code`, `translated_text`, optionally `chapter_id`/`page_id`
   - if no translation engine exists, save translation-ready structure and mark status

6. Save full PDF + parsed structure in S3
   - upload original PDF
   - upload extracted structure JSON as an object at a parallel S3 path
   - optionally upload translated JSON versions

7. Decide sync vs async processing
   - best practice: accept upload, save metadata + PDF immediately, then queue background processing
   - if no task queue exists, use FastAPI `BackgroundTasks` to process chapters/pages after response
   - return a 202/201 with book ID and processing status

### Further Considerations
1. Add required dependencies: `boto3`, `PyMuPDF`, `pdfplumber`, `pytesseract`, `python-multipart`
2. Define S3 env vars: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `S3_BUCKET`
3. Clarify translations: whether to use an external translation service or just store translated fields manually
4. If DB schema is missing, create tables for `books`, `book_chapters`, `book_pages`, `book_translations`, and `book_files`
