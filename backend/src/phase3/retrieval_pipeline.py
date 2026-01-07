import logging
import json
import concurrent.futures
import sys
from typing import List, Dict, Any, Tuple
from collections import defaultdict
import hashlib

from vertexai.language_models import TextEmbeddingModel

from src.shared.config import Config
from src.shared.db import get_supabase_client

logger = logging.getLogger(__name__)

# Constants
VECTOR_K = 30
KEYWORD_K = 30
FINAL_K = 50
RRF_C = 60

class RetrievalPipeline:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.supabase = get_supabase_client()
        self.embedding_model = TextEmbeddingModel.from_pretrained(Config.EMBEDDING_MODEL_NAME)

    def run(self):
        try:
            # 1. Update Session Status
            self.supabase.table("sessions").update({"status": "gathering"}).eq("session_id", self.session_id).execute()
            
            # 2. Fetch Signals with Queries
            signals = self._fetch_signals()
            logger.info(f"Loaded {len(signals)} signals for session {self.session_id}")
            
            if not signals:
                logger.warning("No signals found for this session.")
                self._mark_complete()
                return

            # 3. Optimize Queries (Deduplication)
            # Map: query_text -> list of signal_ids that requested it
            query_map = defaultdict(list)
            for s in signals:
                queries = s.get("search_queries", []) or []
                for q in queries:
                    # Normalize: trim, lowercase
                    norm_q = q.strip()
                    if len(norm_q) < 2: continue # skip garbage
                    query_map[norm_q].append(s["signal_id"])
            
            unique_queries = list(query_map.keys())
            logger.info(f"Processing {len(unique_queries)} unique queries from {len(signals)} signals.")

            # 4. Generate Embeddings (Batch)
            query_embeddings = self._generate_embeddings(unique_queries)
            
            # 5. Execute Hybrid Search (Parallel)
            # We have (query_text, embedding) pairs.
            # Run DB RPC for each query.
            all_candidates = []
            
            # DB connection is HTTP (Supabase), so it handles concurrency well. 
            # But local thread limit applies.
            max_workers = 20 
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_query = {
                    executor.submit(self._search_rpc, q_text, q_vec): q_text
                    for q_text, q_vec in zip(unique_queries, query_embeddings)
                }
                
                for future in concurrent.futures.as_completed(future_to_query):
                    q_text = future_to_query[future]
                    try:
                        results = future.result()
                        # Map results back to all signal_ids that asked for this query
                        signal_ids = query_map[q_text]
                        
                        for sid in signal_ids:
                            for res in results:
                                all_candidates.append({
                                    "session_id": self.session_id,
                                    "signal_id": sid,
                                    "chunk_id": res["chunk_id"],
                                    "query_used": q_text,
                                    "retrieval_channel": "rrf", # simplified for now
                                    "rank_vector": res["rank_vector"],
                                    "rank_keyword": res["rank_keyword"],
                                    "score_vector": res["score_vector"],
                                    "score_keyword": res["score_keyword"],
                                    "rrf_score": res["rrf_score"]
                                })
                                
                    except Exception as e:
                        logger.error(f"Search failed for query '{q_text}': {e}")
            
            # 6. Bulk Insert Candidates
            logger.info(f"Inserting {len(all_candidates)} evidence candidates...")
            self._save_candidates(all_candidates)
            
            # 7. Update Session Status
            self._mark_complete()
            
        except Exception as e:
            logger.error(f"Phase 3 Failed: {e}", exc_info=True)
            self.supabase.table("sessions").update({"status": "failed"}).eq("session_id", self.session_id).execute()
            raise

    def _fetch_signals(self) -> List[Dict]:
        # Fetch all signals for the session that have search_queries (not empty)
        # Assuming DB has index on session_id
        response = self.supabase.table("signals")\
            .select("signal_id, search_queries")\
            .eq("session_id", self.session_id)\
            .execute()
        return response.data

    def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        # Vertex AI Embedding API supports batching
        # Batch size 8 is safe default
        batch_size = Config.EMBED_BATCH_SIZE
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i+batch_size]
            try:
                embeddings = self.embedding_model.get_embeddings(batch)
                all_embeddings.extend([e.values for e in embeddings])
            except Exception as e:
                logger.error(f"Embedding generation failed batch {i}: {e}")
                # Fallback: fill with None or zeros? Better to raise or skip.
                # If we skip, indices won't match. 
                # We simply re-raise for now.
                raise e
        
        return all_embeddings

    def _search_rpc(self, query_text: str, query_embedding: List[float]) -> List[Dict]:
        # Call the Supabase RPC function 'hybrid_search_rrf'
        params = {
            "p_query_text": query_text,
            "p_query_embedding": query_embedding,
            "p_match_count": FINAL_K, # We ask for Top K final
            "p_rrf_k": RRF_C
        }
        
        # rpc call
        response = self.supabase.rpc("hybrid_search_rrf", params).execute()
        return response.data

    def _save_candidates(self, candidates: List[Dict]):
        # Batch insert
        batch_size = 500
        for i in range(0, len(candidates), batch_size):
            batch = candidates[i : i+batch_size]
            self.supabase.table("evidence_candidates").insert(batch).execute()

    def _mark_complete(self):
         self.supabase.table("sessions").update({"status": "reasoning"}).eq("session_id", self.session_id).execute()
         logger.info("Phase 3 Retrieval Pipeline Succeeded.")


def run(payload_str: str):
    logger.info("Phase 3: Retrieval Pipeline Started")
    try:
        payload = json.loads(payload_str)
        session_id = payload.get("session_id")
        
        if not session_id:
             raise ValueError("Missing session_id in payload")
             
        pipeline = RetrievalPipeline(session_id)
        pipeline.run()
        
    except Exception as e:
        logger.error(f"Pipeline Fatal Error: {e}")
        sys.exit(1)
