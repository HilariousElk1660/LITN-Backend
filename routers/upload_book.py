from decimal import Decimal
import json
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query, Path, Body, Depends, params,BackgroundTasks,Depends,File,Form,UploadFile,status
from datetime import datetime, timedelta, date, timezone
from typing import Optional, List, Dict
import uuid
import os
import tempfile
import json
from uuid import UUID
from dataclasses import dataclass, field
from pydantic import BaseModel
import fitz  # PyMuPDF
import pdfplumber
from PIL import Image
import pytesseract
import re
import io
import logging
import requests
import json
import os
from openrouter import OpenRouter

from core.database import get_connection
router = APIRouter()

import cloudinary
import cloudinary.uploader
import cloudinary.api
load_dotenv()

    
cloudinary.config( 
  cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"), 
  api_key = os.getenv("CLOUDINARY_API_KEY"),  
  api_secret = os.getenv("CLOUDINARY_SECRET_KEY")
)

ALLOWED_BOOK_CONTENT_TYPES = {"application/pdf"}
ALLOWED_BOOK_COVER_CONTENT_TYPES = {"image/jpeg", "image/png"}
logger = logging.getLogger(__name__)
@router.post("/create_book")
async def create_book(
    background_tasks: BackgroundTasks,
    admin_id: str = Form(...),
    uploaded_by: str = Form(...),
    author_name: str = Form(...),
    book_name: str = Form(...),
    category: str = Form(...),
    published_date: str = Form(...),
    price: Decimal = Form(...),
    book_division_type: str = Form(...),
    book_cover: UploadFile = File(...),
    pdf_file: UploadFile = File(...),

):
    """ 
    From routers import auth, admin, upload_book
    Create a new book. can only be accessed by admins
    """
    try:
        
        #checking doc type
        if pdf_file.content_type not in ALLOWED_BOOK_CONTENT_TYPES:
            raise HTTPException(status_code=400, detail="Only PDF uploads are supported")

        if book_cover.content_type not in ALLOWED_BOOK_COVER_CONTENT_TYPES:
            raise HTTPException(status_code=400, detail="Only JPEG and PNG cover images are supported")
        
        #max size:
        
        
        # book_cover_url = await upload_book_cover(book_cover)

        book_pdf_file = pdf_file
        pdf_bytes = await book_pdf_file.read()
        # print('bytes:', pdf_bytes) 
        # return book_cover_url
       
        [new_book_id, new_book_file_id] = await create_book(
            admin_id,
            uploaded_by,
            author_name,
            book_name,
            category,
            published_date,
            price,
            book_division_type,
            # book_cover_url
            "url"
        )

        #save pdf
        # book_pdf_url = await upload_book_pdf(pdf_file)
        book_details = {
            "book_id": new_book_id,
            "book_file_id": new_book_file_id,
            "book_division_type": book_division_type,
            "book_title": book_name,
            "author_name": author_name

        }
        background_tasks.add_task(process_book_pdf,book_details, pdf_bytes)
        logger.info("Book creation initiated.")
        return {
            "book_id":new_book_id,
            "book_file_id":new_book_file_id,
            "book_name":book_name,
            "author_name":author_name,
            "processing_status":"pending",
            # "book_url":book_pdf_url,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail="Error occurred while creating book: " + str(e))


#----------------------*STORAGE FUNCTIONS*-----------------------


async def upload_book_cover(book_cover: UploadFile) -> str:
    """
    Upload a book cover image to Cloudinary/S3 and returns book url
    """
    try:
        book_cover_details = cloudinary.uploader.upload(book_cover.file)
        return book_cover_details.get("secure_url")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error occurred while uploading book cover: " + str(e))


async def upload_book_pdf(pdf_file: UploadFile) -> str:
    """
    Upload a book PDF to Cloudinary/S3 and returns book url
    """
    try:
        book_pdf_details = cloudinary.uploader.upload(pdf_file.file)
        return book_pdf_details.get("secure_url")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error occurred while uploading book pdf: " + str(e))


async def upload_epub(book_id, epub_bytes: bytes) -> str:
    """
    Upload a generated EPUB file to Cloudinary and return its secure_url.

    Matches the style of upload_book_cover/upload_book_pdf/upload_embedded_image:
    resource_type="raw" since an .epub is a binary archive, not an image.
    Filename is built from book_id (UUID, server-generated) only -- never
    from user-supplied strings like book_name/author_name -- to avoid path
    collisions or weird characters breaking the storage key.
    """
    try:
        result = cloudinary.uploader.upload(
            io.BytesIO(epub_bytes),
            resource_type="raw",
            folder=f"books/{book_id}",
            public_id="book",
            format="epub",
            overwrite=True,
        )
        return result.get("secure_url")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error occurred while uploading EPUB: {e}",
        )

#---------------------------*PROCCESS BOOK FUNCTIONS*--------------------
MIN_CHARS_FOR_VALID_TEXT = 20
async def process_book_pdf(book_details: dict, pdf_bytes: bytes):
    """
    Runs after the response is returned. Extracts text, detects chapters,
    persists chapters/pages, and stores a structure JSON in S3.
 
    Uses its own DB session since BackgroundTasks run outside the original
    request's dependency-injected session lifecycle.
    """
    try:
        #extracting pdf
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name
 
            try:
                pages = extract_pdf_text(tmp_path)
                embedded_images = extract_embedded_images(tmp_path);
                # print(embedded_images)
            finally:
                os.unlink(tmp_path) 

            #save pages in json file:
       

            
            #get book divisions using LLM: 
            book_divisions_structure = await divide_into_chapters(pages, book_details["book_division_type"])
            print("successfully got book separation")
            # 1. Parse the string into a real Python dictionary
            parsed_structure = json.loads(book_divisions_structure)

            # 2. Access the key safely
            book_divisions = parsed_structure["book_structure"]

            epub_bytes = build_epub(book_details['book_id'], book_details['book_title'], book_details['author_name'], pages, book_divisions)
            print('converted pdf to epub')
            await upload_epub(book_details['book_id'], epub_bytes)
            print('epub uploaded successfully')
        
        return
        def chapter_for_page(page_number: int):
            """
            Given a page number, find which chapter it falls into and
            return that chapter's DB id (or None if no chapter's
            start/end range covers it -- shouldn't normally happen since
            chapters are validated to cover every page, but we stay
            defensive here rather than assuming that invariant always
            holds).
            """
            for chapter in book_divisions:
                if chapter.get("start_page") <= page_number <= chapter.get("end_page"):
                    return chapter.get("chapter_number")
            return None

        #save array of image links and indexes
        pdf_images = []
        #save extracted images in storage
        for image in embedded_images:
            image_key = (
                f"books/{book_details['book_id']}/images/page_{image.page_number}_{image.image_index}.{image.ext}"
            )
            try:
                image_url = await upload_embedded_image(book_details['book_id'], image)
                print(f"Embedded image URL for page {image.page_number}: {image_url}")
                    
            except Exception as e:
                # Log and continue -- one failed image upload shouldn't
                # fail the entire book processing run.
                logger.exception(
                    "Failed to upload embedded image page=%s index=%s book_id=%s",
                    image.page_number, image.image_index, book_details['book_id'],
                )
                continue
            
            
            pdf_images.append({
                # "session": session,
                # "book_id": book_details['book_id'],
                "chapter_id": chapter_for_page(image.page_number),
                "page_number": image.page_number,
                "image_index": image.image_index,
                # "s3_key": image_key,
                "image_url": image_url,
                "width": image.width,
                "height": image.height,
                "bbox_x0": image.bbox_x0,
                "bbox_y0": image.bbox_y0,
                "bbox_x1": image.bbox_x1,
                "bbox_y1": image.bbox_y1,
                "bbox_x0_norm": image.bbox_x0_norm,
                "bbox_y0_norm": image.bbox_y0_norm,
                "bbox_x1_norm": image.bbox_x1_norm,
                "bbox_y1_norm": image.bbox_y1_norm,

            })
        #saving book divisions and pdf image indexes
        print(pdf_images)
        updated = await update_book_file(book_details["book_file_id"],book_divisions,pdf_images);
        print(updated)
        # if not updated:
            # logger.error(f"Failed to update book divisions for book_file_id: {book_details['book_file_id']}")

           
    except Exception as e:
        logger.exception(f"Error occurred while converting book pdf: {str(e)}")

from ebooklib import epub


def build_epub(book_id, book_title: str, author_name: str, pages:dict, book_divisions: list) -> bytes:
    """
    Assembles an EPUB file from the already-extracted book structure
    (chapters + per-page text) and returns the raw .epub file bytes,
    ready to be uploaded to Cloudinary/S3/wherever.

    NOTE: `book_id` was referenced in the original snippet but not part of
    the function signature -- added here as a parameter since
    set_identifier() needs *some* stable unique string, and pulling it from
    an outer scope/global would be fragile. Pass the book's actual UUID in.
    """

    # --- Create the EPUB "container" object ---
    # EpubBook is ebooklib's in-memory representation of the whole file --
    # metadata, chapters, images, table of contents, and reading order all
    # get attached to this one object before it's written out at the end.
    book = epub.EpubBook()

    # Every EPUB needs a unique identifier (this is what e-readers/libraries
    # use to distinguish one book from another, similar to an ISBN). Using
    # the book's own UUID guarantees uniqueness without needing to generate
    # a separate ID just for the EPUB.
    book.set_identifier(str(book_id))

    # Human-readable metadata shown in e-reader libraries (Kindle, Apple
    # Books, etc.) -- title, language (ISO 639-1 code, "en" = English), and
    # author. None of this affects rendering, only how the book is listed.
    book.set_title(book_title)
    book.set_language("en")
    book.add_author(author_name)

    # Will collect one EpubHtml object per chapter as we build them, so we
    # can reference the same list twice below (once for the table of
    # contents, once for the reading order/spine).
    epub_chapters = []

    # --- Build one XHTML "page" per chapter ---
    for chapter in book_divisions:
        # Pull out just the pages that fall within this chapter's page
        # range (start_page/end_page were already determined by the
        # chapter-detection step, whether regex or LLM-based).
        pages_in_chapter = [
            p for p in pages
            if chapter.get('start_page') <= p.page_number <= chapter.get('end_page')
        ]
        

        # Concatenate every page's text into one HTML body for the chapter,
        # each page wrapped in its own <p> tag. NOTE: this does not escape
        # HTML special characters (<, >, &) -- if extracted PDF text ever
        # contains those literally, this will produce broken/invalid XHTML
        # or, if ever rendered elsewhere, an XSS risk. Should be
        # `html.escape(p.text)` before interpolating (see caveat below).
        html_body = "".join(f"<p>{p.text}</p>" for p in pages_in_chapter)

        # EpubHtml represents ONE content file inside the EPUB (i.e. one
        # chapter = one XHTML file in the final zip). `file_name` is the
        # internal path this chapter will be saved at inside the EPUB
        # archive -- it must be unique across all chapters, hence keying it
        # off chapter_number.
        c = epub.EpubHtml(
            title=chapter.get('title') or f"{chapter.get('type') or 'Chapter'} {chapter.get('chapter_number')}",
            file_name=f"chap_{chapter.get('chapter_number')}.xhtml",
            content=f"<h1>{chapter.get('title') or ''}</h1>{html_body}",
        )

        # Registers this chapter's XHTML file into the book's internal
        # manifest (the master list of every file bundled inside the EPUB).
        # Without this, the chapter's content would exist as a Python
        # object but never actually get written into the final archive.
        book.add_item(c)
        epub_chapters.append(c)

    # --- Table of contents ---
    # `book.toc` defines the EPUB's navigable table of contents -- what
    # shows up when a reader taps "Contents" in their e-reader app. Passing
    # the flat list of chapters here means each chapter appears as one
    # top-level TOC entry (no nested sub-sections).
    book.toc = epub_chapters

    # --- Reading order (the "spine") ---
    # The spine defines the order pages are presented when someone reads
    # straight through the book (as opposed to the TOC, which is for
    # jumping around). "nav" refers to the auto-generated navigation
    # document added below -- placing it first means the reader sees/uses
    # it before diving into chapter 1.
    book.spine = ["nav"] + epub_chapters

    # EpubNcx: generates the legacy EPUB2-style table-of-contents file.
    # Still included for backward compatibility with older e-readers that
    # don't understand the newer EPUB3 nav format.
    book.add_item(epub.EpubNcx())

    # EpubNav: generates the modern EPUB3 navigation document (an XHTML
    # file with the actual clickable TOC links). Most current e-readers
    # rely on this rather than the NCX file.
    book.add_item(epub.EpubNav())

    # --- Write the finished EPUB to disk ---
    # write_epub() is where all the actual file-format work happens: it
    # zips every registered item (chapters, nav, ncx) into a single .epub
    # archive with the correct manifest, spine, and the mandatory
    # uncompressed "mimetype" entry the EPUB spec requires. Everything
    # built above is just describing what SHOULD go in the file; this line
    # is what actually produces it.
    tmp_path = "/tmp/output.epub"
    epub.write_epub(tmp_path, book)

    # Read the just-written file back into memory as bytes, so the caller
    # gets a portable value they can upload (to Cloudinary/S3/etc.) without
    # needing to know or care about the temp file path. The temp file
    # itself is left on disk here -- worth adding an os.remove(tmp_path)
    # (or using tempfile.NamedTemporaryFile) after this read to avoid
    # leaking files into /tmp on repeated calls.
    with open(tmp_path, "rb") as f:
        return f.read()

@dataclass
class PageContent:
    page_number: int  # 1-indexed
    text: str
    is_ocr: bool = False

def _extract_with_pymupdf(pdf_path: str) -> List[str]:
    texts = []
    doc = fitz.open(pdf_path)
    toc = doc.get_toc()
    # print("TOC ---------", toc)
    try:
        for page in doc:
            texts.append(page.get_text("text") or "")
    finally:
        doc.close()
    return texts

def _extract_with_pdfplumber(pdf_path: str, page_index: int) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        if page_index >= len(pdf.pages):
            return ""
        page = pdf.pages[page_index]
        return page.extract_text() or ""
 
 
def _extract_with_ocr(pdf_path: str, page_index: int, dpi: int = 300) -> str:
    """Rasterize a single page and run tesseract OCR on it."""
    doc = fitz.open(pdf_path)
    try:
        if page_index >= len(doc):
            return ""
        page = doc[page_index]
        zoom = dpi / 72
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        return pytesseract.image_to_string(img) or ""
    finally:
        doc.close()
 


def extract_pdf_text(pdf_path: str) -> List[PageContent]:
    """
    Extract text for every page in the PDF, trying PyMuPDF first,
    then pdfplumber, then OCR as a last resort for image-only pages.
    """
    pages: List[PageContent] = []
 
    pymupdf_texts = _extract_with_pymupdf(pdf_path)
 
    for idx, raw_text in enumerate(pymupdf_texts):
        page_number = idx + 1
        text = raw_text.strip()
        is_ocr = False
 
        if len(text) < MIN_CHARS_FOR_VALID_TEXT:
            try:
                fallback_text = _extract_with_pdfplumber(pdf_path, idx).strip()
            except Exception:
                logger.exception("pdfplumber failed on page %s", page_number)
                fallback_text = ""
 
            if len(fallback_text) >= MIN_CHARS_FOR_VALID_TEXT:
                text = fallback_text
            else:
                try:
                    ocr_text = _extract_with_ocr(pdf_path, idx).strip()
                    if ocr_text:
                        text = ocr_text
                        is_ocr = True
                except Exception:
                    logger.exception("OCR failed on page %s", page_number)
 
        pages.append(PageContent(page_number=page_number, text=text, is_ocr=is_ocr))
 
    return pages

#---------------------------------- *DATABASE QUERIES* --------------------------------------------------
async def create_book(
    admin_id: Optional[uuid.UUID],
    uploaded_by: str,
    author_name: str,
    book_name: str,
    category: Optional[str],
    published_date,
    subscription_price,
    book_division_type: str,
    # book_url: str,
    book_cover_url: Optional[str] = None
) -> UUID:
    try:
        async with get_connection() as conn:
            new_book = await conn.fetch(
                "INSERT INTO books (admin_id, uploaded_by, author_name, book_name,book_cover_url, category, published_date, subscription_price, book_division_type, status) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) RETURNING book_id",
                admin_id,
                uploaded_by,
                author_name,
                book_name,
                book_cover_url,
                category,
                published_date,
                subscription_price,
                book_division_type,
                "pending"
            )  
            new_book_file = await conn.fetch(
                "INSERT INTO book_files (book_id) VALUES ($1) RETURNING book_file_id",
                new_book[0]["book_id"]
            )
            print(new_book_file[0]["book_file_id"])
            return new_book[0]["book_id"] , new_book_file[0]["book_file_id"]    
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error occurred while creating book row: " + str(e))


async def update_book_file(
    book_file_id : UUID,
    book_divisions: List[Dict[str, any]],
    image_details: List[Dict[str, any]]
) -> UUID:
    try:
        async with get_connection() as conn:
            row = await conn.fetch(
                "UPDATE book_files SET book_divisions = $1, images_details = $2 WHERE book_file_id = $3",
                json.dumps(book_divisions),
                json.dumps(image_details),
                book_file_id
            )

            return row        
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error occurred while updating book file row: " + str(e))

#-------------------------------------------- *CHAPTER DIVISION* ---------------------------------------------------
api_key = os.getenv("OPENROUTER_API_KEY")
model = os.getenv("OPENROUTER_MODEL")

def _extract_text(page_obj) -> str:
    """Coerce a page object into plain string text."""
    if isinstance(page_obj, str):
        return page_obj
    if isinstance(page_obj, dict):
        return page_obj.get("text") or page_obj.get("content") or ""
    if hasattr(page_obj, "text"):
        val = page_obj.text
        return val if isinstance(val, str) else str(val)
    return str(page_obj)


def _extract_page_number(page_obj, fallback_index: int):
    if isinstance(page_obj, dict):
        return page_obj.get("page_number", fallback_index)
    if hasattr(page_obj, "page_number"):
        return page_obj.page_number
    return fallback_index


def estimate_tokens(text) -> int:
    if not isinstance(text, str):
        text = str(text)
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return len(text) // 4


def build_page_chunks(pages, max_tokens=180_000, overlap_pages=2):
    normalized = []
    for i, p in enumerate(pages):
        page_num = _extract_page_number(p, i + 1)
        text = _extract_text(p)
        normalized.append((page_num, text))

    chunks = []
    current_chunk = []
    current_tokens = 0

    i = 0
    while i < len(normalized):
        page_num, text = normalized[i]
        page_tokens = estimate_tokens(text)

        if current_chunk and current_tokens + page_tokens > max_tokens:
            chunks.append(current_chunk)
            overlap_start = max(0, len(current_chunk) - overlap_pages)
            current_chunk = current_chunk[overlap_start:]
            current_tokens = sum(estimate_tokens(t) for _, t in current_chunk)

        current_chunk.append((page_num, text))
        current_tokens += page_tokens
        i += 1

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


# --- call the model on a single chunk, with retry-on-overflow ---------------
async def _call_model_on_chunk(client, chunk, book_division_type):
    pages_payload = "\n".join(f"[PAGE {num}]\n{text}" for num, text in chunk)

    system_prompt = """
You are a structural text parsing engine for a book-reading application.
You will be given a CONTIGUOUS EXCERPT of pages from a larger book (not necessarily the whole book).
Your task is to identify any logical structural divisions (Chapters, Sections, Modules, etc.) that BEGIN within this excerpt, and extract their titles and exact starting page numbers.

### Operational Guidelines:
1. Review the excerpt sequentially to locate structural headings.
2. Ignore header/footer noise, page numbers embedded in the text body, and PDF-to-text conversion artifacts.
3. Attribute each division to the exact page number (given in [PAGE N] markers) where its heading appears.
4. Keep the exact naming convention used in the book (e.g., "Chapter 1: The Beginning" or "Module A - Introduction").
5. If no new division starts in this excerpt, return an empty list.

### Output Format:
Respond exclusively with a valid JSON object:
{
  "book_structure": [
    {"type": "chapter/section etc.","chapter_number": Integer, "title": "String", "start_page": Integer, "end_page": Integer}
  ]
}
No conversational text, no markdown wrapping.
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"The book division type is {book_division_type}. Here is the excerpt:\n{pages_payload}",
        },
    ]

    try:
        response = client.chat.send(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        msg = str(e)
        if "maximum context length" in msg and len(chunk) > 4:
            # split chunk in half and retry recursively
            mid = len(chunk) // 2
            first = await _call_model_on_chunk(client, chunk[:mid], book_division_type)
            second = await _call_model_on_chunk(client, chunk[mid:], book_division_type)
            merged = (first.get("book_structure", []) if first else []) + \
                     (second.get("book_structure", []) if second else [])
            return {"book_structure": merged}
        raise


# --- main entry point ---------------------------------------------------------
async def divide_into_chapters(pages, book_division_type):
    chunks = build_page_chunks(pages, max_tokens=180_000, overlap_pages=2)

    with OpenRouter(api_key=api_key) as client:
        results = []
        for chunk in chunks:
            result = await _call_model_on_chunk(client, chunk, book_division_type)
            results.extend(result.get("book_structure", []))

    # dedupe divisions found twice due to overlap (same title + page_number)
    seen = set()
    merged = []
    for division in sorted(results, key=lambda d: d.get("page_number", 0)):
        key = (division.get("title", "").strip().lower(), division.get("page_number"))
        if key not in seen:
            seen.add(key)
            merged.append(division)

    return json.dumps({"book_structure": merged})



#---------------------------------- *IMAGE EXTRACTION* ----------------------------------
MIN_IMAGE_DIMENSION = 80  # px; filters out tiny bullets/icons/decorative dividers
 
 
@dataclass
class ExtractedImage:
    page_number: int       # 1-indexed, matches PageContent.page_number
    image_index: int       # position of this image within its page (0-indexed)
    image_bytes: bytes
    ext: str                # "png", "jpeg", etc. -- from PyMuPDF, used for content-type/format hints
    width: int
    height: int
    # Bounding box of where this image is actually placed on the page, in PDF
    # point-space (fitz.Rect coordinates, origin at top-left of the page as
    # PyMuPDF reports it). None if PyMuPDF couldn't resolve a placement for
    # this xref (rare, but possible for some malformed/unusual PDFs).
    bbox_x0: Optional[float] = None
    bbox_y0: Optional[float] = None
    bbox_x1: Optional[float] = None
    bbox_y1: Optional[float] = None
    # Same box normalized to 0..1 relative to the page's own width/height,
    # so position is comparable across pages of different sizes without
    # needing to know each page's absolute dimensions.
    bbox_x0_norm: Optional[float] = None
    bbox_y0_norm: Optional[float] = None
    bbox_x1_norm: Optional[float] = None
    bbox_y1_norm: Optional[float] = None

 
 
def extract_embedded_images(pdf_path: str) -> List[ExtractedImage]:
    """
    Walks every page and pulls out embedded raster images via their xref,
    skipping tiny images (icons, bullets, decorative rules) that aren't
    meaningful book content. Also records each image's bounding box (both
    in raw PDF points and normalized 0..1 page-relative coordinates) so
    downstream consumers can place images in their correct position rather
    than just knowing "this image came from this page."
    """
    results: List[ExtractedImage] = []
    doc = fitz.open(pdf_path)
 
    try:
        for page_index, page in enumerate(doc):
            page_number = page_index + 1
            page_width = page.rect.width
            page_height = page.rect.height
            image_list = page.get_images(full=True)
 
            for image_index, img in enumerate(image_list):
                xref = img[0]
                try:
                    base_image = doc.extract_image(xref)
                except Exception:
                    logger.exception(
                        "Failed to extract image xref=%s on page %s", xref, page_number
                    )
                    continue
 
                width = base_image.get("width", 0)
                height = base_image.get("height", 0)
                if width < MIN_IMAGE_DIMENSION or height < MIN_IMAGE_DIMENSION:
                    continue  # skip tiny decorative assets
 
                # Resolve where this image is actually drawn on the page.
                # An xref can technically be placed more than once on a
                # page (e.g. a repeated logo) -- we take the first
                # placement, which covers the overwhelming majority of
                # real-world book PDFs (one image, one spot).
                bbox_x0 = bbox_y0 = bbox_x1 = bbox_y1 = None
                bbox_x0_norm = bbox_y0_norm = bbox_x1_norm = bbox_y1_norm = None
                try:
                    rects = page.get_image_rects(xref)
                except Exception:
                    logger.exception(
                        "Failed to resolve position for image xref=%s on page %s", xref, page_number
                    )
                    rects = []
 
                if rects:
                    rect = rects[0]
                    bbox_x0, bbox_y0, bbox_x1, bbox_y1 = rect.x0, rect.y0, rect.x1, rect.y1
                    if page_width and page_height:
                        bbox_x0_norm = bbox_x0 / page_width
                        bbox_y0_norm = bbox_y0 / page_height
                        bbox_x1_norm = bbox_x1 / page_width
                        bbox_y1_norm = bbox_y1 / page_height
 
                results.append(
                    ExtractedImage(
                        page_number=page_number,
                        image_index=image_index,
                        image_bytes=base_image["image"],
                        ext=base_image.get("ext", "png"),
                        width=width,
                        height=height,
                        bbox_x0=bbox_x0,
                        bbox_y0=bbox_y0,
                        bbox_x1=bbox_x1,
                        bbox_y1=bbox_y1,
                        bbox_x0_norm=bbox_x0_norm,
                        bbox_y0_norm=bbox_y0_norm,
                        bbox_x1_norm=bbox_x1_norm,
                        bbox_y1_norm=bbox_y1_norm,
                    )
                )
    finally:
        doc.close()
 
    return results


async def upload_embedded_image(book_id, image: ExtractedImage) -> str:
    """
    Upload one extracted embedded image to Cloudinary and return its secure_url.
 
    Matches the style of `upload_book_cover`/`upload_book_pdf` (both call
    `cloudinary.uploader.upload(...)` directly), but takes raw bytes instead
    of an UploadFile since these images never came from a client upload --
    they were pulled out of the PDF in-memory.
 
    Raises HTTPException on failure -- callers running this inside a
    background task (e.g. process_book_pdf) should catch and log/skip rather
    than let it propagate, since HTTPException has no effect once the
    original HTTP response has already been sent.
    """
    try:
        result = cloudinary.uploader.upload(
            io.BytesIO(image.image_bytes),
            resource_type="image",
            folder=f"books/{book_id}/images",
            public_id=f"page_{image.page_number}_{image.image_index}",
            format=image.ext,
            overwrite=True,
        )
        return result.get("secure_url")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error occurred while uploading embedded image (page {image.page_number}): {e}",
        )
 
