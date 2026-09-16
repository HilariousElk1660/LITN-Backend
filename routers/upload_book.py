from decimal import Decimal
from email import message
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
# import fitz  # PyMuPDF
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
import mimetypes
import time
# from IDRSolutions import IDRCloudClient
import supabase
from supabase import create_client, Client
from datalab_sdk import DatalabClient, ConvertOptions, AsyncDatalabClient


from core.database import get_connection
from pathlib import Path
router = APIRouter()

import cloudinary
import cloudinary.uploader
import cloudinary.api
load_dotenv()


url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
print(url)

supabase: Client = create_client(url, key)

SUPABASE_BUCKET="Book_App"

cloudinary.config( 
  cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"), 
  api_key = os.getenv("CLOUDINARY_API_KEY"),  
  api_secret = os.getenv("CLOUDINARY_SECRET_KEY"),
  secure=True,
)

client = DatalabClient(api_key=os.getenv("DATALAB_API_KEY"))

ALLOWED_BOOK_CONTENT_TYPES = {"application/pdf", "application/octet-stream"}
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
    pdf_file: UploadFile = File(...),
    translate_to: str = Form(...),
    translate_from: str = Form(...),
):
    """ 
    From routers import auth, admin, upload_book
    Create a new book. can only be accessed by admins
    """
    try:
        print("Creating new book...",pdf_file.content_type) 
        #checking doc type
        if pdf_file.content_type not in ALLOWED_BOOK_CONTENT_TYPES:
            raise HTTPException(status_code=400, detail="Only PDF uploads are supported")


        book_pdf_file = pdf_file
       
        pdf_url = uuid.uuid4()
        
        book_pdf_url = await upload_book_pdf(pdf_file, pdf_url)
        await pdf_file.seek(0)
        pdf_bytes = await book_pdf_file.read()
        print("here?")
        [new_book_id, new_book_file_id] = await create_book(
            admin_id,
            uploaded_by,
            author_name,
            book_name,
            category,
            published_date, 

            price,
            book_division_type
        )

        book_details = {
            "book_id": new_book_id,
            "book_file_id": new_book_file_id,
            "book_division_type": book_division_type,
            "book_title": book_name,
            "author_name": author_name,
            "translate_to": translate_to,
            "translate_from": translate_from,
            "book_pdf_url": book_pdf_url
        }
        
        background_tasks.add_task(process_book_pdf,book_details, pdf_bytes)
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
        book_cover_details = supabase.storage.from_('bucket_name').upload('file_path', book_cover.file)
        return book_cover_details.get("fullPath")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error occurred while uploading book cover: " + str(e))


async def upload_book_pdf(pdf_file: UploadFile, book_id: str) -> str:
    """
    Upload a book PDF to Supabase Storage and return the file's path/URL
    """
    try:
        file_bytes = await pdf_file.read()
        file_path = f"books/{book_id}.pdf"
        print(f"[DEBUG] bucket=Book_App, path={file_path}, book_id={book_id}")
        buckets = supabase.storage.list_buckets()
        print("buckets",[b.name for b in buckets])

        supabase.storage.from_("Book_App").upload(
            path=file_path,
            file=file_bytes,
            file_options={"content-type": "application/pdf", "upsert": "true"},
        )
        public_url = supabase.storage.from_("Book_App").get_public_url(file_path)
        return public_url

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error occurred while uploading book pdf: {str(e)}"
        )

def upload_to_supabase(local_path: Path, storage_path: str, content_type: str) -> str:
    with open(local_path, "rb") as f:
        supabase.storage.from_(SUPABASE_BUCKET).upload(
            path=storage_path,
            file=f,
            file_options={"content-type": content_type, "upsert": "true"},
        )
    return supabase.storage.from_(SUPABASE_BUCKET).get_public_url(storage_path)

#---------------------------*PROCCESS BOOK FUNCTIONS*--------------------
MIN_CHARS_FOR_VALID_TEXT = 20
async def process_book_pdf(book_details: dict, pdf_bytes: bytes):
    """
    Runs after the response is returned. Extracts text, detects chapters,
    persists chapters/pages, and stores a structure JSON in S3.
 
    Uses its own DB session since BackgroundTasks run outside the original
    request's dependency-injected session lifecycle.
    """
    status = "pending"
    try:
        #extracting pdf
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name
 
            try:
                result = await convert_pdf_to_html(tmp_path)
                pages = extract_pdf_text(tmp_path)
            finally:
                try:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                except Exception: 

                    pass 
            print(result)
            if result.get("status") == "success":
                print("successfully converted pdf to html")

            #get book divisions using LLM: 
            book_divisions_structure = await divide_into_chapters(pages, book_details["book_division_type"])
            print("successfully got book separation!")

            book_divisions_structure = json.loads(book_divisions_structure)
           

        
            #translate pdf
            translation_url = translate_pdf(result.get("html_url"),book_details["translate_to"], book_details["translate_from"], result.get("job_id"))
            
            print("successfully translated pdf")
        
            translation_details = {
                book_details["translate_from"]: result.get("html_url"),
                book_details["translate_to"]: translation_url
            }
            
            book_cover_url = None
            
            updated = await update_book_file(book_details["book_file_id"],book_divisions_structure["book_structure"], translation_details, book_cover_url,len(pages));
            print("successfully updated book file")
            status = "completed" 
    except Exception as e:
        status="failed"
        logger.exception(f"Error occurred while converting book pdf: {str(e)}")
    finally:
        await update_book_status(status, book_details['book_id'])
        # pass

@dataclass
class PageContent:
    page_number: int  # 1-indexed
    text: str
    is_ocr: bool = False

def _extract_with_pymupdf(pdf_path: str) -> List[str]:
    import fitz
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
    import fitz
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


UPLOAD_DIR = Path("new2")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
import shutil

def content_type_for(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    if ext in ("jpg", "jpeg"):
        return "image/jpeg"
    if ext in ("png", "webp", "gif", "svg"):
        return f"image/{ext}" if ext != "svg" else "image/svg+xml"
    if ext == "html":
        return "text/html"
    return "application/octet-stream"

async def convert_pdf_to_html(file_path: str) -> dict:
    """
    Converts pdf to html using the datalab api and returns the supabase secure url 
    of the uploaded converted html file, job id and status
    """
    
    # Create a dedicated directory for this request job
    job_id = str(uuid.uuid4())
    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
 
    try:
        # If file_path is already a path, use it directly; otherwise copy to job directory
        if isinstance(file_path, str) and os.path.exists(file_path):
            upload_path = Path(file_path)
        else:
            upload_path = job_dir / Path(file_path).name
            with upload_path.open("wb") as f:
                with open(file_path, "rb") as src:
                    shutil.copyfileobj(src, f)

        client = AsyncDatalabClient()
        options = ConvertOptions(
            output_format="html",
            mode="fast",
            paginate=True,
            disable_image_captions=True,
        )
        result = await client.convert(upload_path, options=options)
      

        html = getattr(result, "html", "") or ""

        # Let the client write everything (including images) into the job directory
        
        result.save_output(job_dir, save_images=True)

        image_url_map: dict[str, str] = {}
        image_extensions = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}



        # Fallback / catch-all: any image files the client wrote that we haven't mapped yet
        for local_file in UPLOAD_DIR.rglob("*"):
            print(local_file)
            if not local_file.is_file():
                continue
            if local_file.suffix.lower() not in image_extensions:
                continue
            if local_file == upload_path:          # skip the original upload
                continue

            name = local_file.name

            storage_path = f"{job_id}/{name}"
            public_url = upload_to_supabase(local_file, storage_path, content_type_for(local_file))
        
            image_url_map[name] = public_url

        # Replace references – longest keys first to avoid partial matches
        for src in sorted(image_url_map, key=len, reverse=True):
            html = html.replace(src, image_url_map[src])

        # write & upload the HTML as before
        html_path = job_dir / "output.html"
        html_path.write_text(html, encoding="utf-8")
        html_url = upload_to_supabase(html_path, f"{job_id}/output.html", "text/html")

        return {
            "status": "success",
            "html_url": html_url,
            "job_id": job_id
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Conversion failed: {str(e)}"
        )
    finally:
        # Safely remove only this job's temporary files
        shutil.rmtree(job_dir, ignore_errors=True)
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
) -> UUID:
    try:
        async with get_connection() as conn:
            new_book = await conn.fetch(
                "INSERT INTO books (admin_id, uploaded_by, author_name, book_name, category, published_date, subscription_price, book_division_type, status) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING book_id",
                admin_id,
                uploaded_by,
                author_name,
                book_name,
                category,
                published_date,
                subscription_price,
                book_division_type,
                "pending"
            )  
            new_book_file = await conn.fetch(
                "INSERT INTO book_files (book_id) VALUES ($1) RETURNING book_file_id",
                new_book[0]["book_id"],
            )
            return new_book[0]["book_id"] , new_book_file[0]["book_file_id"]    
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error occurred while creating book row: " + str(e))


async def update_book_file(
    book_file_id : UUID,
    book_divisions: List[Dict[str, any]],
    translation_details: Dict[str, any],
    book_cover_url: Optional[str] = None,
    total_pages: int = 0
) -> UUID:
    try:
        async with get_connection() as conn:
            row = await conn.fetch(
                "UPDATE book_files SET book_divisions = $1,pdf_file_url = $2 WHERE book_file_id = $3 RETURNING book_id",
                json.dumps(book_divisions),
                json.dumps(translation_details),
                book_file_id
            )
            book_id = row[0]["book_id"]
            row2 = await conn.fetch(
                "UPDATE books SET book_cover_url = $1,pages = $2,chapters = $3 WHERE book_id = $4",
                book_cover_url,
                total_pages,
                len(book_divisions),
                book_id
            )
        return row        
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error occurred while updating book file row: " + str(e))


async def update_book_pdf_url(book_file_id: UUID, pdf_file_url: str):
    try:
        async with get_connection() as conn:
            await conn.execute(
                "UPDATE book_files SET pdf_file_url = $1 WHERE book_file_id = $2",
                pdf_file_url,
                book_file_id
            )
    except Exception as e:
        logger.error(f"Error updating book pdf url in DB: {e}")

async def update_book_status(status:str,book_id: UUID):
    try:
        async with get_connection() as conn:
            await conn.execute(
                "UPDATE books SET status = $1 WHERE book_id = $2",
                status,
                book_id
            )
    except Exception as e:
        logger.error(f"Error updating book status in DB: {e}")

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


def _clean_and_parse_json(content: str) -> dict:
    if not content or not content.strip():
        logger.warning("Empty content received from model response.")
        return {"book_structure": []}
    
    text = content.strip()
    
    # Remove markdown codeblock fences if present (e.g. ```json ... ```)
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
        
    # Try parsing directly
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
        
    # Fallback: search for JSON object between outermost braces
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    logger.warning(f"Failed to parse JSON from model output: {text[:200]!r}")
    return {"book_structure": []}


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
    {"type": "chapter", "title": "String", "page_number": 1}
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
        if not response or not getattr(response, "choices", None):
            logger.warning("OpenRouter API returned no choices.")
            return {"book_structure": []}

        choice = response.choices[0]
        message_obj = getattr(choice, "message", None)
        raw_content = getattr(message_obj, "content", None)

        if not raw_content or not raw_content.strip():
            finish_reason = getattr(choice, "finish_reason", "unknown")
            logger.warning(f"Model returned empty content. Finish reason: {finish_reason}")
            return {"book_structure": []}

        return _clean_and_parse_json(raw_content)

    except Exception as e:
        msg = str(e)
        if "maximum context length" in msg and len(chunk) > 4:
            # split chunk in half and retry recursively
            mid = len(chunk) // 2
            first = await _call_model_on_chunk(client, chunk[:mid], book_division_type)
            second = await _call_model_on_chunk(client, chunk[mid:], book_division_type)
            merged = (first.get("book_structure", []) if isinstance(first, dict) else []) + \
                     (second.get("book_structure", []) if isinstance(second, dict) else [])
            return {"book_structure": merged}
        logger.error(f"Error calling model on chunk: {e}")
        return {"book_structure": []}


# --- main entry point ---------------------------------------------------------
async def divide_into_chapters(pages, book_division_type):
    chunks = build_page_chunks(pages, max_tokens=180_000, overlap_pages=2)

    with OpenRouter(api_key=api_key) as client:
        results = []
        for chunk in chunks:
            result = await _call_model_on_chunk(client, chunk, book_division_type)
            if isinstance(result, dict):
                results.extend(result.get("book_structure", []))

    # dedupe divisions found twice due to overlap (same title + page_number)
    seen = set()
    merged = []

    normalized_results = []
    for d in results:
        if not isinstance(d, dict):
            continue
        page_num = d.get("page_number")
        if page_num is None:
            page_num = d.get("start_page")
        if page_num is None:
            page_num = d.get("page")
        if page_num is None:
            page_num = 1

        try:
            page_num = int(page_num)
        except (ValueError, TypeError):
            page_num = 1

        title = str(d.get("title") or "").strip()
        div_type = str(d.get("type") or book_division_type or "chapter").strip()

        normalized_d = dict(d)
        normalized_d["page_number"] = page_num
        normalized_d["title"] = title
        normalized_d["type"] = div_type
        normalized_results.append(normalized_d)

    for division in sorted(normalized_results, key=lambda d: d["page_number"]):
        key = (division["title"].lower(), division["page_number"])
        if key not in seen:
            seen.add(key)
            merged.append(division)

    return json.dumps({"book_structure": merged})



LANG_CODE_MAP = {
    "english": "EN",
    "french": "FR",
    "german": "DE",
    "chinese": "ZH",
    "spanish": "ES",
    "portuguese": "PT-PT",
    "italian": "IT",
    "japanese": "JA",
}


def normalize_lang(lang: str) -> str:
    key = lang.strip().lower()
    return LANG_CODE_MAP.get(key, lang.upper())


import deepl

def translate_pdf(
    html: str,
    lang_out: str,
    lang_in: str,
    job_id: str 
) -> str:
    """
    Translate a single HTML document via DeepL, upload the translated file to Supabase,
    and return the supabase secure URL.
    """

    deepl_api_key = os.getenv("DEEPL_API_KEY")
    if not deepl_api_key:
        raise RuntimeError("DEEPL_API_KEY environment variable not set")

    base_url = (
        "https://api-free.deepl.com"
        if deepl_api_key.endswith(":fx")
        else "https://api.deepl.com"
    )

    # Unique per-request filenames to avoid collisions on concurrent requests
    job_id = str(uuid.uuid4())
    local_filename = f"{job_id}_source.html"
    translated_local_path = f"{job_id}_translated.html"

    try:
        # Download source HTML
        res = requests.get(html)
        res.raise_for_status()
        with open(local_filename, "wb") as f:
            f.write(res.content)

        headers = {"Authorization": f"DeepL-Auth-Key {deepl_api_key}"}
        mime_type, _ = mimetypes.guess_type(local_filename)

        # 1. Upload document to DeepL
        with open(local_filename, "rb") as f:
            files = {"file": (local_filename, f, mime_type or "text/html")}
            data = {
                "target_lang": normalize_lang(lang_out),
                "tag_handling": "html",
                "source_lang": normalize_lang(lang_in),
            }
            resp = requests.post(
                f"{base_url}/v2/document", headers=headers, data=data, files=files
            )

        if not resp.ok:
            print("DeepL error response:", resp.text)
        resp.raise_for_status()

        job = resp.json()
        document_id = job["document_id"]
        document_key = job["document_key"]

        # 2. Poll for completion
        status_url = f"{base_url}/v2/document/{document_id}"
        max_wait_seconds = 300  # avoid an infinite loop if DeepL never finishes
        waited = 0

        while True:
            status_resp = requests.post(
                status_url, headers=headers, data={"document_key": document_key}
            )
            status_resp.raise_for_status()
            status = status_resp.json()

            if status["status"] == "done":
                break
            if status["status"] == "error":
                raise RuntimeError(f"DeepL translation failed: {status}")

            wait_time = status.get("seconds_remaining", 5)
            time.sleep(wait_time)
            waited += wait_time
            if waited > max_wait_seconds:
                raise TimeoutError("DeepL translation timed out")

        # 3. Download translated result
        result_url = f"{base_url}/v2/document/{document_id}/result"
        result_resp = requests.post(
            result_url, headers=headers, data={"document_key": document_key}
        )
        result_resp.raise_for_status()

        with open(translated_local_path, "wb") as f:
            f.write(result_resp.content)

        # 4. Upload translated file to Cloudinary
        upload_result = upload_to_supabase(translated_local_path, f"{job_id}/translated_html", "text/html")
        print("TRANSLATED URL",upload_result)
        return upload_result

    finally:
        # Clean up temp files regardless of success/failure
        for path in (local_filename, translated_local_path):
            if os.path.exists(path):
                os.remove(path)

# translate_pdf("https://res.cloudinary.com/dcvpbxqob/image/upload/v1784389820/books/3fef4149-53e2-45fc-bf95-d488dad11e67/id1p2tddjbzkkay3fein.pdf","EN","FR")

