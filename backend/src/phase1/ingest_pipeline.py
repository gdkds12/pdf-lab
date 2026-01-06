import logging
import json
import os
import sys
import fitz  # PyMuPDF
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from vertexai.language_models import TextEmbeddingModel
from tenacity import retry, stop_after_attempt, wait_exponential
from typing import List, Dict, Any, Optional
import uuid

from src.shared.config import Config
from src.shared.db import get_supabase_client
from src.shared.storage import StorageClient

logger = logging.getLogger(__name__)

class IngestPipeline:
    def __init__(self, source_id: str, gcs_url: str):
        self.source_id = source_id
        self.gcs_url = gcs_url
        self.local_pdf_path = f"/tmp/{uuid.uuid4()}.pdf"
        self.storage_client = StorageClient()
        self.supabase = get_supabase_client()
        
        # Init Vertex AI
        vertexai.init(project=Config.GCP_PROJECT, location=Config.VERTEX_LOCATION)
        
    def run(self):
        try:
            # Step 1: Download
            self._download_pdf()
            
            # Step 2: Router
            is_scanned = self._router_check()
            logger.info(f"Router Result: {'SCANNED' if is_scanned else 'DIGITAL'}")
            
            # Update Ingest Status
            self.supabase.table("sources").update({
                "ingest_status": "running"
            }).eq("source_id", self.source_id).execute()

            # Step 3: Extract Text
            pages_data = []
            if is_scanned:
                pages_data = self._process_scanned()
            else:
                pages_data = self._process_digital()
                
            # Step 4: Chunking
            chunks = self._chunk_text(pages_data)
            logger.info(f"Created {len(chunks)} chunks.")
            
            # Step 5: Embedding
            chunks_with_embeddings = self._embed_chunks(chunks)
            
            # Step 6: DB Insert
            self._save_chunks(chunks_with_embeddings)
            
            # Mark Succeeded
            self.supabase.table("sources").update({
                "ingest_status": "succeeded",
                "page_count": len(pages_data) # Update page count
            }).eq("source_id", self.source_id).execute()
            
            logger.info("Ingest Pipeline Succeeded.")
            
        except Exception as e:
            logger.error(f"Ingest Pipeline Failed: {e}", exc_info=True)
            self.supabase.table("sources").update({
                "ingest_status": "failed"
            }).eq("source_id", self.source_id).execute()
            raise
        finally:
            self._cleanup()

    def _download_pdf(self):
        logger.info("Step 1: Downloading PDF...")
        # Ensure /tmp exists (sometimes needed in local dev)
        os.makedirs(os.path.dirname(self.local_pdf_path), exist_ok=True)
        self.storage_client.download_file(self.gcs_url, self.local_pdf_path)

    def _router_check(self) -> bool:
        """
        Returns True if Scanned, False if Digital.
        Logic: Load first 3 pages. If text density is low, consider it Scanned.
        """
        logger.info("Step 2: Routing (Digital vs Scanned)...")
        doc = fitz.open(self.local_pdf_path)
        page_count = len(doc)
        check_pages = min(page_count, 3)
        
        low_density_count = 0
        threshold = 50 # characters per page approx? Need to calibrate. 
                       # A blank page has 0. A scanned page with no OCR layer has 0.
                       # A digital page usually has 100s.
        
        for i in range(check_pages):
            text = doc[i].get_text().strip()
            if len(text) < threshold:
                low_density_count += 1
                
        doc.close()
        
        # Majority vote or strict? Doc suggests "majority vote"
        # If 2 out of 3 are empty/low text, it's scanned.
        if check_pages > 0 and (low_density_count / check_pages) > 0.5:
            return True
        return False

    def _process_digital(self) -> List[Dict]:
        logger.info("Step 3A: Processing Digital PDF...")
        pages = []
        try:
            doc = fitz.open(self.local_pdf_path)
            for i, page in enumerate(doc):
                text = page.get_text()
                # Basic cleanup if needed
                pages.append({
                    "page_num": i + 1,
                    "text": text
                })
            return pages
        finally:
            if 'doc' in locals():
                doc.close()

    def _process_scanned(self) -> List[Dict]:
        logger.info("Step 3B: Processing Scanned PDF (Gemini)...")
        try:
            doc = fitz.open(self.local_pdf_path)
            total_pages = len(doc)
            batch_size = Config.INGEST_BATCH_PAGES
            all_pages_data = []

            for start_page in range(0, total_pages, batch_size):
                end_page = min(start_page + batch_size, total_pages)
                logger.info(f"Processing batch: pages {start_page+1} to {end_page}")
                
                # Create sub-PDF
                new_doc = fitz.open()
                new_doc.insert_pdf(doc, from_page=start_page, to_page=end_page-1)
                pdf_bytes = new_doc.tobytes()
                new_doc.close() # Close sub-doc
                
                # Call Gemini
                batch_result = self._call_gemini_ocr(pdf_bytes, start_page + 1)
                all_pages_data.extend(batch_result)
                
            return all_pages_data
        finally:
            if 'doc' in locals():
                doc.close()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _call_gemini_ocr(self, pdf_bytes: bytes, start_page_offset: int) -> List[Dict]:
        model = GenerativeModel(Config.GEMINI_MODEL_NAME)
        
        # Prompt as per documentation
        prompt = f"""
        You are a highly accurate OCR engine. 
        Extract text from the attached PDF pages.
        RETURN JSON ONLY. No markdown fencing.
        
        Requirements:
        1. Output format must be: {{ "pages": [ {{ "page_num": <integer>, "markdown": "<content>" }}, ... ] }}
        2. "page_num" must be adjusted relative to the start page: {start_page_offset}.
           The first page in this PDF is page {start_page_offset}.
        3. Do NOT summarize. Transcribe exactly.
        4. Preserve tables as Markdown tables.
        5. Preserve equations as LaTeX.
        6. Do not miss any page.
        """
        
        # Gemini 1.5/2.5 accepts PDF parts directly
        part = Part.from_data(data=pdf_bytes, mime_type="application/pdf")
        
        response = model.generate_content(
            [part, prompt],
            generation_config={"response_mime_type": "application/json"}
        )
        
        try:
            text = response.text
            # Clean up potential markdown code blocks
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            
            data = json.loads(text)
            return data.get("pages", [])
        except Exception as e:
            logger.error(f"Failed to parse Gemini response: {e}. Raw: {response.text[:100]}...")
            raise

    def _chunk_text(self, pages_data: List[Dict]) -> List[Dict]:
        logger.info("Step 4: Chunking...")
        chunks = []
        
        # Simple Logic: Split by headers or paragraphs
        # For MVP, we will do a simpler paragraph-based chunking with overlap, 
        # but try to respect "pages". 
        
        # The doc suggests "Heading based first, then paragraph".
        # Implementing a full recursive splitter is complex.
        # We'll do a simplified version: Split by double newline, group into chunks < 1000 chars?
        # Or just keep it simple: Page-level chunking is too big.
        
        # Let's clean text and split by paragraphs
        for page in pages_data:
            text = page.get("text") or page.get("markdown") or ""
            page_num = page["page_num"]
            
            # Naive Split by paragraphs (\n\n)
            paragraphs = text.split('\n\n')
            
            current_chunk = ""
            
            for para in paragraphs:
                if len(current_chunk) + len(para) < 1000:
                    current_chunk += "\n\n" + para
                else:
                    if current_chunk.strip():
                        chunks.append({
                            "source_id": self.source_id,
                            "content_text": current_chunk.strip(),
                            "page_start": page_num,
                            "page_end": page_num,
                            "anchor_path": [f"Page {page_num}"], # Minimal anchor
                            "token_count": len(current_chunk) // 4 # Rough estimate
                        })
                    current_chunk = para
            
            # Last chunk
            if current_chunk.strip():
                 chunks.append({
                    "source_id": self.source_id,
                    "content_text": current_chunk.strip(),
                    "page_start": page_num,
                    "page_end": page_num,
                    "anchor_path": [f"Page {page_num}"],
                    "token_count": len(current_chunk) // 4
                })
                
        return chunks

    def _embed_chunks(self, chunks: List[Dict]) -> List[Dict]:
        logger.info("Step 5: Embedding...")
        model = TextEmbeddingModel.from_pretrained(Config.EMBEDDING_MODEL_NAME)
        
        batch_size = Config.EMBED_BATCH_SIZE
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            texts = [c["content_text"] for c in batch]
            
            try:
                # Vertex AI Embedding
                embeddings = model.get_embeddings(texts)
                for j, embedding in enumerate(embeddings):
                    batch[j]["embedding"] = embedding.values
            except Exception as e:
                logger.error(f"Embedding failed for batch {i}: {e}")
                # Optional: Partial retry logic could go here
                raise
                
        return chunks

    def _save_chunks(self, chunks: List[Dict]):
        logger.info(f"Step 6: Saving {len(chunks)} chunks to Supabase...")
        
        # Bulk insert in batches of 100 ? Supabase-py handles lists.
        # But for huge lists, batching is safer.
        batch_size = 100
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            self.supabase.table("chunks").insert(batch).execute()

    def _cleanup(self):
        if os.path.exists(self.local_pdf_path):
            os.remove(self.local_pdf_path)
            logger.info("Cleaned up temporary file.")


def run(payload_str: str):
    logger.info("Phase 1: PDF Ingest Pipeline Started")
    try:
        payload = json.loads(payload_str)
        source_id = payload.get("source_id")
        gcs_url = payload.get("gcs_pdf_url")
        
        if not source_id or not gcs_url:
             raise ValueError("Missing source_id or gcs_pdf_url in payload")
             
        pipeline = IngestPipeline(source_id, gcs_url)
        pipeline.run()
        
    except Exception as e:
        logger.error(f"Pipeline Fatal Error: {e}")
        sys.exit(1)

