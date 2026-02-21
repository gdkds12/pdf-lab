import logging
import os
import re
import sys
import time
import tempfile
import threading
import fitz  # PyMuPDF
from google.genai import types
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
        self.slice_semaphore = threading.BoundedSemaphore(max(1, Config.PHASE1_SLICE_MAX_INFLIGHT))
        
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
            # Step 6.5: Learning-object index (toc/problem/strategy/summary)
            self._save_learning_objects(chunks_with_embeddings)

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
            max_workers = max(
                1,
                min(
                    len(tasks),
                    Config.PHASE1_SCANNED_MAX_WORKERS,
                    Config.PHASE1_API_MAX_CONCURRENCY,
                    Config.PHASE1_EFFECTIVE_MAX_WORKERS,
                ),
            )
            logger.info(f"Starting parallel OCR with {max_workers} workers for {len(tasks)} batches.")

            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_meta = {}
                task_iter = iter(tasks)
                task_state: Dict[int, Dict[str, Any]] = {}

                def submit_batch(batch: Dict[str, int], is_hedge: bool = False) -> None:
                    start_p = batch["start_page"]
                    state = task_state.setdefault(start_p, {"hedges": 0})
                    shard_suffix = None
                    if is_hedge:
                        state["hedges"] += 1
                        shard_suffix = f"hedge-{state['hedges']}"
                    future = executor.submit(
                        self._call_gemini_ocr_for_range,
                        batch["start_page"],
                        batch["end_page"],
                        shard_suffix,
                    )
                    future_to_meta[future] = {
                        "batch": batch,
                        "submitted_at": time.monotonic(),
                        "is_hedge": is_hedge,
                    }

                # Prime worker pool.
                for _ in range(max_workers):
                    try:
                        batch = next(task_iter)
                    except StopIteration:
                        break
                    submit_batch(batch)

                results_map = {}  # start_page -> list of pages
                total_batches = len(tasks)
                completed_batches = 0
                while future_to_meta:
                    done, _ = concurrent.futures.wait(
                        list(future_to_meta.keys()),
                        timeout=1.0,
                        return_when=concurrent.futures.FIRST_COMPLETED
                    )

                    if not done:
                        # Hedge only tail stragglers to cut p99 latency.
                        remaining = total_batches - completed_batches
                        if (
                            Config.PHASE1_STRAGGLER_HEDGE_ENABLED
                            and remaining <= max(1, Config.PHASE1_STRAGGLER_HEDGE_REMAINING_THRESHOLD)
                        ):
                            now = time.monotonic()
                            for future, meta in list(future_to_meta.items()):
                                if meta.get("is_hedge"):
                                    continue
                                batch_info = meta["batch"]
                                start_p = batch_info["start_page"]
                                if start_p in results_map:
                                    continue
                                age_sec = now - float(meta.get("submitted_at") or now)
                                state = task_state.get(start_p) or {}
                                hedges = int(state.get("hedges") or 0)
                                if (
                                    age_sec >= max(1.0, float(Config.PHASE1_STRAGGLER_HEDGE_SEC))
                                    and hedges < max(1, Config.PHASE1_STRAGGLER_MAX_HEDGES_PER_PAGE)
                                ):
                                    logger.warning(
                                        "Launching hedge OCR for pages %s-%s after %.1fs (hedges=%s/%s)",
                                        start_p + 1,
                                        batch_info["end_page"],
                                        age_sec,
                                        hedges + 1,
                                        Config.PHASE1_STRAGGLER_MAX_HEDGES_PER_PAGE,
                                    )
                                    submit_batch(batch_info, is_hedge=True)
                        continue

                    for future in done:
                        meta = future_to_meta.pop(future, None)
                        if not meta:
                            continue
                        batch_info = meta["batch"]
                        start_p = batch_info["start_page"]
                        if start_p in results_map:
                            # Duplicate (hedged) completion after winner already stored.
                            continue
                        try:
                            data = future.result()
                            results_map[start_p] = data
                            completed_batches += 1
                            logger.info(
                                f"Batch {start_p+1}-{batch_info['end_page']} completed. "
                                f"Got {len(data)} pages. Progress {completed_batches}/{total_batches}"
                            )
                            # Best-effort cancel outstanding duplicates for this page.
                            for other_future, other_meta in list(future_to_meta.items()):
                                other_batch = other_meta["batch"]
                                if other_batch["start_page"] != start_p:
                                    continue
                                if other_future.cancel():
                                    future_to_meta.pop(other_future, None)
                        except Exception as exc:
                            logger.error(f"Batch {start_p+1}-{batch_info['end_page']} generated an exception: {exc}")
                            raise exc

                        try:
                            next_batch = next(task_iter)
                        except StopIteration:
                            continue
                        submit_batch(next_batch)

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
        max_inflight = max(
            1,
            min(
                len(groups),
                Config.PHASE1_BATCH_MAX_INFLIGHT_JOBS,
                Config.PHASE1_API_MAX_CONCURRENCY,
                Config.PHASE1_EFFECTIVE_MAX_WORKERS,
            ),
        )

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
            with self.slice_semaphore:
                tmp_pdf = self._extract_pdf_temp_path_for_range(start_page, end_page)
                try:
                    pdf_bytes = self._read_file_bytes(tmp_pdf)
                finally:
                    try:
                        os.remove(tmp_pdf)
                    except OSError:
                        pass
            prompt = self._build_ocr_prompt(start_page + 1, expected_count)
            requests.append(
                types.InlinedRequest(
                    contents=[
                        types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                        types.Part.from_text(text=prompt),
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=self._phase1_ocr_response_schema(
                            start_page_offset=start_page + 1,
                            expected_count=expected_count,
                        ),
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
            pages = self._extract_ocr_pages_payload(data)
            normalized_pages, info = self._normalize_ocr_pages(
                raw_pages=pages,
                start_page_offset=start_page + 1,
                expected_count=expected_count,
            )
            if normalized_pages is None:
                in_range_pages = list(info.get("in_range_pages") or [])
                missing_page_nums = list(info.get("missing_page_nums") or [])
                if Config.PHASE1_PARTIAL_FILL_ENABLED and missing_page_nums:
                    logger.warning(
                        "OCR batch partial fill for pages %s-%s: in_range=%s missing=%s",
                        start_page + 1,
                        end_page,
                        len(in_range_pages),
                        len(missing_page_nums),
                    )
                    filled_pages = self._call_gemini_ocr_per_page(page_nums=missing_page_nums)
                    merged = in_range_pages + filled_pages
                    normalized_pages = self._build_expected_pages(
                        start_page_offset=start_page + 1,
                        expected_count=expected_count,
                        pages=merged,
                        allow_empty_fill=True,
                    )
                else:
                    normalized_pages = self._build_expected_pages(
                        start_page_offset=start_page + 1,
                        expected_count=expected_count,
                        pages=in_range_pages,
                        allow_empty_fill=True,
                    )
                    logger.warning(
                        "OCR batch incomplete pages %s-%s; proceeding with empty-fill. expected=%s raw=%s dropped_out_of_range=%s dropped_duplicate=%s",
                        start_page + 1,
                        end_page,
                        expected_count,
                        len(pages),
                        info["dropped_out_of_range"],
                        info["dropped_duplicate"],
                    )

            if len(pages) != expected_count or info["used_fallback_sequential"] or info["used_relative_page_num_remap"]:
                logger.warning(
                    "OCR batch normalization applied for pages %s-%s: raw=%s expected=%s "
                    "dropped_out_of_range=%s dropped_duplicate=%s fallback_sequential=%s relative_page_num_remap=%s",
                    start_page + 1,
                    end_page,
                    len(pages),
                    expected_count,
                    info["dropped_out_of_range"],
                    info["dropped_duplicate"],
                    info["used_fallback_sequential"],
                    info["used_relative_page_num_remap"],
                )

            group_results[start_page] = normalized_pages

        return group_results

    def _extract_pdf_temp_path_for_range(self, start_page: int, end_page: int) -> str:
        """
        Materialize a page range to a temporary PDF file.
        File-backed slicing avoids holding many in-memory buffers simultaneously
        when many OCR workers run at once.
        """
        fd, tmp_path = tempfile.mkstemp(prefix="p1-slice-", suffix=".pdf", dir="/tmp")
        os.close(fd)
        try:
            with fitz.open(self.local_pdf_path) as doc:
                new_doc = fitz.open()
                new_doc.insert_pdf(doc, from_page=start_page, to_page=end_page - 1)
                new_doc.save(tmp_path)
                new_doc.close()
            return tmp_path
        except Exception:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
            raise

    def _read_file_bytes(self, file_path: str) -> bytes:
        with open(file_path, "rb") as f:
            return f.read()

    def _build_ocr_prompt(self, start_page_offset: int, expected_count: int) -> str:
        end_page = start_page_offset + expected_count - 1
        return f"""
        You are a highly accurate OCR engine.
        Extract text from the attached PDF pages.
        RETURN JSON ONLY. No markdown fencing.

        Requirements:
        1. Output format must be: {{ "pages": [ {{ "page_num": <integer>, "markdown": "<content>" }}, ... ] }}
        2. Return exactly {expected_count} items in "pages". Never omit any page.
        3. "page_num" must be absolute and strictly in range [{start_page_offset}, {end_page}] with no duplicates.
        4. If a page is unreadable, still return that page with empty markdown "".
        5. The first page in this PDF is page {start_page_offset}.
        6. Do NOT summarize. Transcribe exactly.
        7. Preserve tables as Markdown tables.
        8. Preserve equations as LaTeX.
        9. Do not output any text outside JSON.
        """

    def _phase1_ocr_response_schema(self, start_page_offset: int, expected_count: int) -> Dict[str, Any]:
        end_page = start_page_offset + expected_count - 1
        return {
            "type": "object",
            "required": ["pages"],
            "properties": {
                "pages": {
                    "type": "array",
                    "minItems": expected_count,
                    "maxItems": expected_count,
                    "items": {
                        "type": "object",
                        "required": ["page_num", "markdown"],
                        "properties": {
                            "page_num": {
                                "type": "integer",
                                "minimum": start_page_offset,
                                "maximum": end_page,
                            },
                            "markdown": {"type": "string"},
                        },
                    },
                }
            },
        }

    def _extract_ocr_pages_payload(self, payload: Any) -> List[Dict[str, Any]]:
        if isinstance(payload, dict):
            pages = payload.get("pages")
            if isinstance(pages, list):
                return pages
            data_pages = payload.get("data")
            if isinstance(data_pages, list):
                return data_pages
            return []
        if isinstance(payload, list):
            return payload
        return []

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
        info: Dict[str, Any] = {
            "input_count": len(raw_pages),
            "dropped_out_of_range": 0,
            "dropped_duplicate": 0,
            "used_fallback_sequential": False,
            "used_relative_page_num_remap": False,
            "in_range_count": 0,
            "missing_page_nums": [],
            "in_range_pages": [],
        }

        by_page_num: Dict[int, Dict[str, Any]] = {}
        parsed_in_order: List[Dict[str, Any]] = []
        relative_numbered_pages: List[Dict[str, Any]] = []

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

            if page_num is not None and 1 <= page_num <= expected_count:
                # Some OCR responses ignore absolute numbering and return relative 1..N.
                relative_numbered_pages.append({
                    "page_num": start_page_offset + (page_num - 1),
                    "markdown": markdown,
                })

            if page_num is None:
                continue
            if page_num not in expected_set:
                info["dropped_out_of_range"] += 1
                continue
            if page_num in by_page_num:
                info["dropped_duplicate"] += 1
                continue
            by_page_num[page_num] = {"page_num": page_num, "markdown": markdown}

        in_range_pages = [by_page_num[num] for num in expected_nums if num in by_page_num]
        missing_page_nums = [num for num in expected_nums if num not in by_page_num]
        info["in_range_count"] = len(in_range_pages)
        info["missing_page_nums"] = missing_page_nums
        info["in_range_pages"] = in_range_pages

        # Preferred: exact expected range by page number.
        if all(num in by_page_num for num in expected_nums):
            normalized = [by_page_num[num] for num in expected_nums]
            return normalized, info

        # Heuristic: OCR sometimes returns relative page numbers (1..N) for each sub-PDF.
        # Remap those to absolute range and accept when complete.
        if relative_numbered_pages:
            rel_map: Dict[int, Dict[str, Any]] = {}
            for row in relative_numbered_pages:
                rel_num = int(row["page_num"])
                if rel_num not in rel_map:
                    rel_map[rel_num] = row
            if all(num in rel_map for num in expected_nums):
                info["used_relative_page_num_remap"] = True
                normalized = [rel_map[num] for num in expected_nums]
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

    def _build_expected_pages(
        self,
        start_page_offset: int,
        expected_count: int,
        pages: List[Dict[str, Any]],
        allow_empty_fill: bool,
    ) -> List[Dict[str, Any]]:
        expected_nums = list(range(start_page_offset, start_page_offset + expected_count))
        by_page_num: Dict[int, Dict[str, Any]] = {}
        for page in pages:
            if not isinstance(page, dict):
                continue
            try:
                page_num = int(page.get("page_num"))
            except (TypeError, ValueError):
                continue
            markdown = page.get("markdown")
            if markdown is None:
                markdown = ""
            if not isinstance(markdown, str):
                markdown = str(markdown)
            if page_num not in by_page_num:
                by_page_num[page_num] = {"page_num": page_num, "markdown": markdown}

        normalized: List[Dict[str, Any]] = []
        for num in expected_nums:
            if num in by_page_num:
                normalized.append(by_page_num[num])
            elif allow_empty_fill:
                normalized.append({"page_num": num, "markdown": ""})
        return normalized

    def _call_gemini_ocr_for_range(
        self,
        start_page: int,
        end_page: int,
        shard_suffix: Optional[str] = None,
    ) -> List[Dict]:
        expected_count = end_page - start_page
        with self.slice_semaphore:
            tmp_pdf = self._extract_pdf_temp_path_for_range(start_page, end_page)
            try:
                pdf_bytes = self._read_file_bytes(tmp_pdf)
            finally:
                try:
                    os.remove(tmp_pdf)
                except OSError:
                    pass
        try:
            return self._call_gemini_ocr(
                pdf_bytes,
                start_page + 1,
                expected_count,
                shard_suffix=shard_suffix,
            )
        except Exception as e:
            if (
                Config.PHASE1_ADAPTIVE_SPLIT_ON_FAILURE
                and expected_count > max(1, Config.PHASE1_ADAPTIVE_MIN_BATCH_PAGES)
            ):
                split_size = max(Config.PHASE1_ADAPTIVE_MIN_BATCH_PAGES, expected_count // 2)
                if split_size < expected_count:
                    logger.warning(
                        "Range OCR failed for pages %s-%s. Splitting into subranges of %s pages. Reason: %s: %s",
                        start_page + 1,
                        end_page,
                        split_size,
                        type(e).__name__,
                        e,
                    )
                    merged: List[Dict] = []
                    cursor = start_page
                    while cursor < end_page:
                        next_end = min(cursor + split_size, end_page)
                        merged.extend(
                            self._call_gemini_ocr_for_range(
                                cursor,
                                next_end,
                                shard_suffix=shard_suffix,
                            )
                        )
                        cursor = next_end
                    return merged

            logger.warning(
                f"Range OCR failed for pages {start_page+1}-{end_page}. "
                f"Falling back to per-page OCR. Reason: {type(e).__name__}: {e}"
            )
            return self._call_gemini_ocr_per_page(start_page=start_page, end_page=end_page)

    def _call_gemini_ocr_per_page(
        self,
        start_page: Optional[int] = None,
        end_page: Optional[int] = None,
        page_nums: Optional[List[int]] = None,
    ) -> List[Dict]:
        recovered: List[Dict] = []
        failed_pages: List[str] = []

        if page_nums is not None:
            targets = sorted(set(int(p) for p in page_nums))
        else:
            if start_page is None or end_page is None:
                raise ValueError("start_page/end_page or page_nums is required for per-page OCR.")
            targets = list(range(start_page + 1, end_page + 1))

        for page_num in targets:
            try:
                page_idx = page_num - 1
                with self.slice_semaphore:
                    tmp_pdf = self._extract_pdf_temp_path_for_range(page_idx, page_idx + 1)
                    try:
                        single_pdf = self._read_file_bytes(tmp_pdf)
                    finally:
                        try:
                            os.remove(tmp_pdf)
                        except OSError:
                            pass
                page_result = self._call_gemini_ocr(single_pdf, page_num, 1, allow_missing_fill=False)
                if not page_result:
                    raise ValueError("Empty page OCR result")
                first = page_result[0] if isinstance(page_result[0], dict) else {}
                markdown = first.get("markdown", "")
                if markdown is None:
                    markdown = ""
                if not isinstance(markdown, str):
                    markdown = str(markdown)
                recovered.append({"page_num": page_num, "markdown": markdown})
            except Exception as e:
                failed_pages.append(f"{page_num}:{type(e).__name__}")
                logger.error(f"Per-page OCR failed for page {page_num}: {e}")
                if Config.PHASE1_PER_PAGE_ALLOW_EMPTY_FILL:
                    recovered.append({"page_num": page_num, "markdown": ""})
                    logger.warning(f"Per-page OCR empty-fill applied for page {page_num}.")

        if failed_pages:
            if Config.PHASE1_PER_PAGE_ALLOW_EMPTY_FILL:
                logger.warning(
                    "Per-page OCR completed with empty-fill. failed_pages=%s",
                    ",".join(failed_pages[:5]),
                )
            else:
                if targets:
                    target_range = f"{targets[0]}-{targets[-1]}"
                else:
                    target_range = "empty"
                raise RuntimeError(
                    f"Per-page OCR fallback failed for range {target_range}. "
                    f"failed_pages={','.join(failed_pages[:5])}"
                )

        recovered.sort(key=lambda x: int(x.get("page_num", 0)))
        return recovered

    def _is_retryable_generation_error(self, error: Exception) -> bool:
        text = str(error).lower()
        retry_tokens = (
            "429",
            "resource exhausted",
            "rate limit",
            "quota",
            "deadline exceeded",
            "timeout",
            "service unavailable",
            "temporarily unavailable",
            "internal",
            "503",
            "502",
            "500",
            # OCR response-shape problems that often recover on retry
            "batch incomplete",
            "json",
            "unterminated",
            "expecting value",
            "no such key",
        )
        return any(token in text for token in retry_tokens)

    def _call_gemini_ocr(
        self,
        pdf_bytes: bytes,
        start_page_offset: int,
        expected_count: int,
        allow_missing_fill: bool = True,
        shard_suffix: Optional[str] = None,
    ) -> List[Dict]:
        # Enforce up to 3 retries for OCR calls (1 initial + 3 retries = 4 attempts).
        # This keeps behavior aligned with operational SLO while avoiding unbounded loops.
        max_attempts = max(4, max(1, Config.PHASE1_OCR_MAX_ATTEMPTS))
        for attempt in range(1, max_attempts + 1):
            logger.info(
                f"Thread started for batch starting at page {start_page_offset} requesting {expected_count} pages. "
                f"(attempt {attempt}/{max_attempts})"
            )
            shard_key = f"p1-sync:{self.source_id}:{start_page_offset}"
            if shard_suffix:
                shard_key = f"{shard_key}:{shard_suffix}"
            client = get_gemini_api_client(shard_key=shard_key, timeout_sec=Config.PHASE1_OCR_TIMEOUT_SEC)
            model_name = normalize_model_name(Config.GEMINI_MODEL_NAME)
            prompt = self._build_ocr_prompt(start_page_offset, expected_count)
            part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
            text = ""
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[part, prompt],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=self._phase1_ocr_response_schema(
                            start_page_offset=start_page_offset,
                            expected_count=expected_count,
                        ),
                        max_output_tokens=64000,
                        temperature=0.0,
                    ),
                )
                text = response.text or extract_generate_content_text(response)
                logger.info(f"Gemini Raw Response (Page {start_page_offset}+):\\n{text[:1000]}...[truncated]")
                
                # Use json_repair to handle potential truncated JSON or formatting issues
                data = json_repair.loads(text)
                pages = self._extract_ocr_pages_payload(data)
                normalized_pages, info = self._normalize_ocr_pages(
                    raw_pages=pages,
                    start_page_offset=start_page_offset,
                    expected_count=expected_count,
                )
                if normalized_pages is None:
                    in_range_pages = list(info.get("in_range_pages") or [])
                    missing_page_nums = list(info.get("missing_page_nums") or [])
                    if allow_missing_fill and Config.PHASE1_PARTIAL_FILL_ENABLED and missing_page_nums:
                        logger.warning(
                            "Partial OCR accepted for pages %s+: in_range=%s missing=%s. Filling missing pages per-page.",
                            start_page_offset,
                            len(in_range_pages),
                            len(missing_page_nums),
                        )
                        filled_pages = self._call_gemini_ocr_per_page(page_nums=missing_page_nums)
                        merged = in_range_pages + filled_pages
                        normalized_pages = self._build_expected_pages(
                            start_page_offset=start_page_offset,
                            expected_count=expected_count,
                            pages=merged,
                            allow_empty_fill=True,
                        )
                    elif allow_missing_fill:
                        normalized_pages = self._build_expected_pages(
                            start_page_offset=start_page_offset,
                            expected_count=expected_count,
                            pages=in_range_pages,
                            allow_empty_fill=True,
                        )
                        logger.warning(
                            "Batch incomplete after normalization for pages %s+. Proceeding with empty-fill: expected=%s raw=%s dropped_out_of_range=%s dropped_duplicate=%s",
                            start_page_offset,
                            expected_count,
                            len(pages),
                            info["dropped_out_of_range"],
                            info["dropped_duplicate"],
                        )
                    else:
                        raise ValueError(
                            f"Batch incomplete after normalization: expected={expected_count}, "
                            f"raw={len(pages)}, dropped_out_of_range={info['dropped_out_of_range']}, "
                            f"dropped_duplicate={info['dropped_duplicate']}"
                        )

                if len(pages) != expected_count or info["used_fallback_sequential"] or info["used_relative_page_num_remap"]:
                    logger.warning(
                        "OCR normalization applied for pages %s+: raw=%s expected=%s "
                        "dropped_out_of_range=%s dropped_duplicate=%s fallback_sequential=%s relative_page_num_remap=%s",
                        start_page_offset,
                        len(pages),
                        expected_count,
                        info["dropped_out_of_range"],
                        info["dropped_duplicate"],
                        info["used_fallback_sequential"],
                        info["used_relative_page_num_remap"],
                    )

                return normalized_pages
            except Exception as e:
                if attempt < max_attempts and self._is_retryable_generation_error(e):
                    sleep_sec = min(4.0, 0.8 * (2 ** (attempt - 1)))
                    logger.warning(
                        "Transient OCR error for pages %s-%s; retrying in %.1fs (attempt %s/%s): %s",
                        start_page_offset,
                        start_page_offset + expected_count - 1,
                        sleep_sec,
                        attempt,
                        max_attempts,
                        e,
                    )
                    time.sleep(sleep_sec)
                    continue

                logger.error(
                    "OCR attempt failed for pages %s-%s (attempt %s/%s): %s. Raw: %s...",
                    start_page_offset,
                    start_page_offset + expected_count - 1,
                    attempt,
                    max_attempts,
                    e,
                    text[:100],
                )
                if attempt >= max_attempts:
                    logger.error(
                        "OCR exhausted retries for pages %s-%s after %s attempts.",
                        start_page_offset,
                        start_page_offset + expected_count - 1,
                        max_attempts,
                    )
                raise

        raise RuntimeError(f"OCR failed after max attempts for pages {start_page_offset}+")

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
                    config=types.EmbedContentConfig(
                        task_type="RETRIEVAL_DOCUMENT",
                        output_dimensionality=Config.EMBEDDING_DIMENSIONS,
                    ),
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

        batch_size = 100
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            self.supabase.table("chunks").insert(batch).execute()

    def _extract_learning_objects(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract textbook objects with stricter, problem-centric rules.

        Goals:
        - Avoid ToC/preface false positives (e.g., "연습문제" mentioned in prose)
        - Require number-bearing labels for problem objects
        - Deduplicate repeated OCR chunks (same label + page)
        """
        objects: List[Dict[str, Any]] = []
        seen_keys = set()

        # Noise sections frequently matching keywords but not actual problems.
        noise_pattern = re.compile(r"(차례|contents|머리말|preface|감사의\s*글|역자\s*서문)", re.IGNORECASE)

        # NOTE: order matters. first match wins.
        patterns = [
            # Problem-centric (number required)
            ("assessment", re.compile(r"(학습\s*평가\s*[A-Z]?\d+(?:[\.-]\d+)?)", re.IGNORECASE)),
            ("example", re.compile(r"(응용예제\s*\d+(?:[\.-]\d+)?)", re.IGNORECASE)),
            ("example", re.compile(r"(설계예제\s*\d+(?:[\.-]\d+)?)", re.IGNORECASE)),
            ("example", re.compile(r"(예\s*제\s*\d+(?:[\.-]\d+)?)", re.IGNORECASE)),
            ("example", re.compile(r"(example\s*\d+(?:[\.-]\d+)?)", re.IGNORECASE)),
            ("exercise", re.compile(r"(연습\s*문제\s*\d+(?:[\.-]\d+)?)", re.IGNORECASE)),
            ("exercise", re.compile(r"(exercise\s*\d+(?:[\.-]\d+)?)", re.IGNORECASE)),
            # Non-problem companion objects (kept for future ranking/context)
            ("strategy", re.compile(r"(문제\s*풀이\s*전략|풀이\s*전략|힌트)", re.IGNORECASE)),
            ("summary", re.compile(r"(요약|핵심\s*정리|summary)", re.IGNORECASE)),
        ]

        for chunk in chunks:
            text = (chunk.get("content_text") or "").strip()
            if not text:
                continue

            page_start = chunk.get("page_start")

            # Skip front matter where false positives are very common.
            if isinstance(page_start, int) and page_start < 20:
                continue
            if noise_pattern.search(text):
                continue

            for obj_type, pattern in patterns:
                m = pattern.search(text)
                if not m:
                    continue

                label = m.group(1).strip()[:80]
                label_norm = re.sub(r"\s+", "", label).lower()
                dedup_key = (label_norm, page_start)
                if dedup_key in seen_keys:
                    break
                seen_keys.add(dedup_key)

                snippet = text[:260]
                objects.append({
                    "source_id": self.source_id,
                    "chunk_id": chunk.get("chunk_id"),
                    "object_type": obj_type,
                    "label": label,
                    "title": label,
                    "snippet": snippet,
                    "page_start": page_start,
                    "page_end": chunk.get("page_end"),
                    "anchor_path": chunk.get("anchor_path"),
                })
                break

        return objects

    def _save_learning_objects(self, chunks: List[Dict[str, Any]]):
        objects = self._extract_learning_objects(chunks)
        try:
            # Idempotent-by-source behavior: avoid piling duplicates across re-ingest runs.
            self.supabase.table("textbook_objects").delete().eq("source_id", self.source_id).execute()

            if not objects:
                logger.info("No textbook learning objects extracted (existing rows cleared).")
                return

            batch_size = 200
            for i in range(0, len(objects), batch_size):
                self.supabase.table("textbook_objects").insert(objects[i:i+batch_size]).execute()
            logger.info(f"Saved {len(objects)} textbook learning objects.")
        except Exception as e:
            logger.warning(f"textbook_objects save skipped/failure: {e}")

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
