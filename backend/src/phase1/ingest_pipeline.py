import logging
import os
import sys
import fitz  # PyMuPDF
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential
from typing import List, Dict, Any, Optional, Tuple
import uuid
import concurrent.futures
import json_repair  # Import json_repair

from src.shared.config import Config
from src.shared.db import get_supabase_client
from src.shared.gemini_api import (
    chunked,
    extract_generate_content_text,
    get_gemini_api_client,
    normalize_model_name,
    wait_for_batch_completion,
)
from src.shared.storage import StorageClient
from src.shared.validation import parse_payload, require_gcs_uri, require_uuid

logger = logging.getLogger(__name__)

class IngestPipeline:
    def __init__(self, source_id: str, gcs_url: str):
        self.source_id = source_id
        self.gcs_url = gcs_url
        self.local_pdf_path = f"/tmp/{uuid.uuid4()}.pdf"
        self.storage_client = StorageClient()
        self.supabase = get_supabase_client()
        
    def run(self):
        try:
            # Step 1: Download
            self._download_pdf()
            
            # Security Check: File Size Limit (700MB)
            file_size_mb = os.path.getsize(self.local_pdf_path) / (1024 * 1024)
            if file_size_mb > 700:
                raise ValueError(f"File size {file_size_mb:.2f}MB exceeds limit of 700MB.")
            
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
                # Security Check: Page Count Limit for Scanned PDF (2000 pages)
                doc = fitz.open(self.local_pdf_path)
                page_count = len(doc)
                doc.close()
                if page_count > 2000:
                    raise ValueError(f"Scanned PDF has {page_count} pages, exceeding limit of 2000 pages.")
                    
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
            # Explicitly log the data being sent
            logger.info(f"Updating source {self.source_id} to succeeded status. Page count: {len(pages_data)}")
            
            response = self.supabase.table("sources").update({
                "ingest_status": "succeeded",
                "page_count": len(pages_data)
            }).eq("source_id", self.source_id).execute()

            # Optional compliance mode: remove original source asset after successful ingest.
            # The knowledge chunks remain for retrieval, but raw source file can be purged.
            if Config.DELETE_SOURCE_ASSETS_ON_SUCCESS:
                try:
                    self.storage_client.delete_file(self.gcs_url)
                    logger.info(f"Deleted original source asset: {self.gcs_url}")
                except Exception as delete_err:
                    logger.warning(f"Failed to delete original source asset {self.gcs_url}: {delete_err}")
            
            logger.info(f"Successfully updated source {self.source_id} status to succeeded.")
            
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
        logger.info("Step 3B: Processing Scanned PDF (Gemini Parallel)...")
        try:
            doc = fitz.open(self.local_pdf_path)
            total_pages = len(doc)
            batch_size = Config.INGEST_BATCH_PAGES
            tasks = []
            for start_page in range(0, total_pages, batch_size):
                end_page = min(start_page + batch_size, total_pages)
                tasks.append({
                    "start_page": start_page,
                    "end_page": end_page
                })

            doc.close()

            if Config.PHASE1_USE_BATCH_API:
                logger.info("Using Gemini Batch API for scanned OCR.")
                return self._process_scanned_batch(tasks)

            # Execute in bounded parallelism.
            all_pages_data = []
            max_workers = max(1, min(len(tasks), Config.PHASE1_SCANNED_MAX_WORKERS))
            logger.info(f"Starting parallel OCR with {max_workers} workers for {len(tasks)} batches.")

            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_batch = {}
                task_iter = iter(tasks)

                # Prime worker pool.
                for _ in range(max_workers):
                    try:
                        batch = next(task_iter)
                    except StopIteration:
                        break
                    future = executor.submit(
                        self._call_gemini_ocr_for_range,
                        batch["start_page"],
                        batch["end_page"]
                    )
                    future_to_batch[future] = batch

                results_map = {}  # start_page -> list of pages
                while future_to_batch:
                    done, _ = concurrent.futures.wait(
                        list(future_to_batch.keys()),
                        return_when=concurrent.futures.FIRST_COMPLETED
                    )

                    for future in done:
                        batch_info = future_to_batch.pop(future)
                        start_p = batch_info["start_page"]
                        try:
                            data = future.result()
                            results_map[start_p] = data
                            logger.info(f"Batch {start_p+1}-{batch_info['end_page']} completed. Got {len(data)} pages.")
                        except Exception as exc:
                            logger.error(f"Batch {start_p+1}-{batch_info['end_page']} generated an exception: {exc}")
                            raise exc

                        try:
                            next_batch = next(task_iter)
                        except StopIteration:
                            continue
                        next_future = executor.submit(
                            self._call_gemini_ocr_for_range,
                            next_batch["start_page"],
                            next_batch["end_page"]
                        )
                        future_to_batch[next_future] = next_batch

            # Reassemble in order
            sorted_start_pages = sorted(results_map.keys())
            for sp in sorted_start_pages:
                all_pages_data.extend(results_map[sp])
                
            return all_pages_data

        except Exception as e:
            logger.error(f"Scanned processing failed: {e}")
            raise

    def _process_scanned_batch(self, tasks: List[Dict[str, int]]) -> List[Dict]:
        if not tasks:
            return []

        model_name = normalize_model_name(Config.GEMINI_MODEL_NAME)
        results_map: Dict[int, List[Dict]] = {}
        group_size = max(1, Config.PHASE1_BATCH_REQUESTS_PER_JOB)
        groups = list(chunked(tasks, group_size))
        max_inflight = max(1, min(len(groups), Config.PHASE1_BATCH_MAX_INFLIGHT_JOBS))

        logger.info(
            f"OCR batch mode: groups={len(groups)}, group_size={group_size}, max_inflight={max_inflight}"
        )
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_inflight) as executor:
            future_to_group = {
                executor.submit(self._run_ocr_batch_group, group, model_name): group
                for group in groups
            }
            for future in concurrent.futures.as_completed(future_to_group):
                group_results = future.result()
                results_map.update(group_results)

        all_pages_data: List[Dict] = []
        for sp in sorted(results_map.keys()):
            all_pages_data.extend(results_map[sp])
        return all_pages_data

    def _run_ocr_batch_group(self, group: List[Dict[str, int]], model_name: str) -> Dict[int, List[Dict]]:
        shard = f"p1:{self.source_id}:{group[0]['start_page'] if group else 0}"
        client = get_gemini_api_client(shard_key=shard)
        requests: List[types.InlinedRequest] = []
        metas: List[Dict[str, int]] = []

        for task in group:
            start_page = task["start_page"]
            end_page = task["end_page"]
            expected_count = end_page - start_page
            pdf_bytes = self._extract_pdf_bytes_for_range(start_page, end_page)
            prompt = self._build_ocr_prompt(start_page + 1, expected_count)
            requests.append(
                types.InlinedRequest(
                    contents=[
                        types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                        types.Part.from_text(text=prompt),
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        max_output_tokens=64000,
                        temperature=0.0,
                    ),
                )
            )
            metas.append(
                {
                    "start_page": start_page,
                    "end_page": end_page,
                    "expected_count": expected_count,
                }
            )

        batch_job = client.batches.create(
            model=model_name,
            src=requests,
            config=types.CreateBatchJobConfig(
                display_name=f"p1-ocr-{self.source_id[:8]}-{uuid.uuid4().hex[:6]}"
            ),
        )
        logger.info(f"Created OCR batch job: {batch_job.name}")
        completed = wait_for_batch_completion(
            client=client,
            batch_name=batch_job.name,
            timeout_sec=Config.GEMINI_BATCH_TIMEOUT_SEC,
            poll_interval_sec=Config.GEMINI_BATCH_POLL_SEC,
        )

        responses = list((completed.dest and completed.dest.inlined_responses) or [])
        if len(responses) != len(metas):
            raise RuntimeError(
                f"OCR batch response count mismatch. expected={len(metas)}, got={len(responses)}"
            )

        group_results: Dict[int, List[Dict]] = {}
        for idx, inlined_response in enumerate(responses):
            meta = metas[idx]
            start_page = meta["start_page"]
            end_page = meta["end_page"]
            expected_count = meta["expected_count"]

            if getattr(inlined_response, "error", None):
                err = getattr(inlined_response.error, "message", None) or str(inlined_response.error)
                raise RuntimeError(f"OCR batch request failed for pages {start_page+1}-{end_page}: {err}")

            text = extract_generate_content_text(getattr(inlined_response, "response", None))
            logger.info(
                f"OCR batch response pages {start_page+1}-{end_page}: "
                f"{(text or '')[:300]}..."
            )
            if not text:
                raise RuntimeError(f"Empty OCR response for pages {start_page+1}-{end_page}")

            data = json_repair.loads(text)
            pages = data.get("pages", [])
            normalized_pages, info = self._normalize_ocr_pages(
                raw_pages=pages,
                start_page_offset=start_page + 1,
                expected_count=expected_count,
            )
            if normalized_pages is None:
                raise ValueError(
                    f"OCR batch incomplete pages {start_page+1}-{end_page}: expected={expected_count}, "
                    f"raw={len(pages)}, dropped_out_of_range={info['dropped_out_of_range']}, "
                    f"dropped_duplicate={info['dropped_duplicate']}"
                )

            if len(pages) != expected_count or info["used_fallback_sequential"]:
                logger.warning(
                    "OCR batch normalization applied for pages %s-%s: raw=%s expected=%s "
                    "dropped_out_of_range=%s dropped_duplicate=%s fallback_sequential=%s",
                    start_page + 1,
                    end_page,
                    len(pages),
                    expected_count,
                    info["dropped_out_of_range"],
                    info["dropped_duplicate"],
                    info["used_fallback_sequential"],
                )

            group_results[start_page] = normalized_pages

        return group_results

    def _extract_pdf_bytes_for_range(self, start_page: int, end_page: int) -> bytes:
        with fitz.open(self.local_pdf_path) as doc:
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=start_page, to_page=end_page - 1)
            pdf_bytes = new_doc.tobytes()
            new_doc.close()
        return pdf_bytes

    def _build_ocr_prompt(self, start_page_offset: int, expected_count: int) -> str:
        return f"""
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
        6. Do not miss any page. Return exactly {expected_count} pages.
        """

    def _normalize_ocr_pages(
        self,
        raw_pages: List[Dict[str, Any]],
        start_page_offset: int,
        expected_count: int,
    ) -> Tuple[Optional[List[Dict[str, Any]]], Dict[str, Any]]:
        """
        Normalize OCR page outputs.
        - Accept extra pages by selecting expected page range only.
        - Retry only when pages are insufficient after normalization.
        """
        expected_nums = list(range(start_page_offset, start_page_offset + expected_count))
        expected_set = set(expected_nums)
        info = {
            "input_count": len(raw_pages),
            "dropped_out_of_range": 0,
            "dropped_duplicate": 0,
            "used_fallback_sequential": False,
        }

        by_page_num: Dict[int, Dict[str, Any]] = {}
        parsed_in_order: List[Dict[str, Any]] = []

        for idx, page in enumerate(raw_pages):
            if not isinstance(page, dict):
                continue
            markdown = page.get("markdown")
            if markdown is None:
                markdown = ""
            if not isinstance(markdown, str):
                markdown = str(markdown)

            page_num_raw = page.get("page_num")
            page_num: Optional[int] = None
            try:
                page_num = int(page_num_raw)
            except (TypeError, ValueError):
                page_num = None

            parsed = {"index": idx, "page_num": page_num, "markdown": markdown}
            parsed_in_order.append(parsed)

            if page_num is None:
                continue
            if page_num not in expected_set:
                info["dropped_out_of_range"] += 1
                continue
            if page_num in by_page_num:
                info["dropped_duplicate"] += 1
                continue
            by_page_num[page_num] = {"page_num": page_num, "markdown": markdown}

        # Preferred: exact expected range by page number.
        if all(num in by_page_num for num in expected_nums):
            normalized = [by_page_num[num] for num in expected_nums]
            return normalized, info

        # Fallback: use first N parsed entries and remap sequential page numbers.
        if len(parsed_in_order) >= expected_count:
            normalized: List[Dict[str, Any]] = []
            for i in range(expected_count):
                normalized.append(
                    {
                        "page_num": expected_nums[i],
                        "markdown": parsed_in_order[i]["markdown"],
                    }
                )
            info["used_fallback_sequential"] = True
            return normalized, info

        # Insufficient pages after normalization -> retry path.
        return None, info

    def _call_gemini_ocr_for_range(self, start_page: int, end_page: int) -> List[Dict]:
        expected_count = end_page - start_page
        pdf_bytes = self._extract_pdf_bytes_for_range(start_page, end_page)
        return self._call_gemini_ocr(pdf_bytes, start_page + 1, expected_count)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    def _call_gemini_ocr(self, pdf_bytes: bytes, start_page_offset: int, expected_count: int) -> List[Dict]:
        logger.info(f"Thread started for batch starting at page {start_page_offset} requesting {expected_count} pages.")
        client = get_gemini_api_client(shard_key=f"p1-sync:{self.source_id}:{start_page_offset}")
        model_name = normalize_model_name(Config.GEMINI_MODEL_NAME)
        prompt = self._build_ocr_prompt(start_page_offset, expected_count)
        part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
        
        # Wrapper to enforce timeout around sync API call.
        def _generate():
            return client.models.generate_content(
                model=model_name,
                contents=[part, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    max_output_tokens=64000,
                    temperature=0.0,
                ),
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as request_executor:
            future = request_executor.submit(_generate)
            try:
                response = future.result(timeout=Config.PHASE1_OCR_TIMEOUT_SEC)
            except concurrent.futures.TimeoutError:
                raise TimeoutError(f"Gemini API call timed out after {Config.PHASE1_OCR_TIMEOUT_SEC} seconds for batch {start_page_offset}")
        
        try:
            text = response.text or extract_generate_content_text(response)
            logger.info(f"Gemini Raw Response (Page {start_page_offset}+):\\n{text[:1000]}...[truncated]")
            
            # Use json_repair to handle potential truncated JSON or formatting issues
            data = json_repair.loads(text)
            pages = data.get("pages", [])
            normalized_pages, info = self._normalize_ocr_pages(
                raw_pages=pages,
                start_page_offset=start_page_offset,
                expected_count=expected_count,
            )
            if normalized_pages is None:
                raise ValueError(
                    f"Batch incomplete after normalization: expected={expected_count}, "
                    f"raw={len(pages)}, dropped_out_of_range={info['dropped_out_of_range']}, "
                    f"dropped_duplicate={info['dropped_duplicate']}. Retrying..."
                )

            if len(pages) != expected_count or info["used_fallback_sequential"]:
                logger.warning(
                    "OCR normalization applied for pages %s+: raw=%s expected=%s "
                    "dropped_out_of_range=%s dropped_duplicate=%s fallback_sequential=%s",
                    start_page_offset,
                    len(pages),
                    expected_count,
                    info["dropped_out_of_range"],
                    info["dropped_duplicate"],
                    info["used_fallback_sequential"],
                )

            return normalized_pages
        except Exception as e:
            logger.error(f"Failed to parse Gemini response or incomplete batch: {e}. Raw: {response.text[:100]}...")
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

        batch_size = Config.EMBED_BATCH_SIZE

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            texts = [c["content_text"] for c in batch]

            try:
                client = get_gemini_api_client(shard_key=f"p1-embed:{self.source_id}:{i // max(1, batch_size)}")
                response = client.models.embed_content(
                    model=Config.EMBEDDING_MODEL_NAME,
                    contents=texts,
                    config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
                )
                embeddings = list(getattr(response, "embeddings", None) or [])
                if len(embeddings) != len(batch):
                    raise RuntimeError(
                        f"Embedding count mismatch at batch {i}: expected={len(batch)}, got={len(embeddings)}"
                    )
                for j, embedding in enumerate(embeddings):
                    batch[j]["embedding"] = list(embedding.values)
            except Exception as e:
                logger.error(f"Embedding failed for batch {i}: {e}")
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
        payload = parse_payload(payload_str)
        source_id = require_uuid(payload, "source_id")
        gcs_url = require_gcs_uri(payload, "gcs_pdf_url")
             
        pipeline = IngestPipeline(source_id, gcs_url)
        pipeline.run()
        
    except Exception as e:
        logger.error(f"Pipeline Fatal Error: {e}")
        sys.exit(1)
