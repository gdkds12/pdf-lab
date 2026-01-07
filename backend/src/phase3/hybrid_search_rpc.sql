-- Hybrid Search RPC (RRF based)
-- This function combines Vector Search (pgvector) and Keyword Search (pg_trgm) using Reciprocal Rank Fusion.
-- It is designed to work with the 'halfvec' type for embeddings.

CREATE OR REPLACE FUNCTION hybrid_search_rrf(
  p_query_text TEXT,
  p_query_embedding halfvec(768),
  p_match_count INT,
  p_rrf_k INT DEFAULT 60,
  p_full_text_weight FLOAT DEFAULT 1.0, -- Reserved for Weighted Sum if needed, unused in pure RRF
  p_semantic_weight FLOAT DEFAULT 1.0   -- Reserved
)
RETURNS TABLE (
  chunk_id UUID,
  content_text TEXT,
  page_start INT,
  page_end INT,
  anchor_path TEXT[],
  score_vector FLOAT,
  rank_vector BIGINT,
  score_keyword FLOAT,
  rank_keyword BIGINT,
  rrf_score FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  WITH 
  -- 1. Vector Search (Semantic)
  vector_search AS (
    SELECT 
      c.chunk_id,
      c.content_text,
      c.page_start,
      c.page_end,
      c.anchor_path,
      -- Negative inner product distance (higher is better for cosine similarity if normalized, but <-> is L2 usually)
      -- For cosine distance <=> : 1 - distance is similarity.
      -- Here assumes <=> (cosine distance) operator. 
      (1 - (c.embedding <=> p_query_embedding))::float as score_v
    FROM chunks c
    ORDER BY c.embedding <=> p_query_embedding
    LIMIT p_match_count * 2 -- Fetch more candidates for RRF intersection
  ),
  ranked_vector AS (
    SELECT *,
           RANK() OVER (ORDER BY score_v DESC) as rank_v
    FROM vector_search
    LIMIT p_match_count
  ),

  -- 2. Keyword Search (Syntactic)
  keyword_search AS (
    SELECT 
      c.chunk_id,
      c.content_text,
      c.page_start,
      c.page_end,
      c.anchor_path,
      similarity(c.content_text, p_query_text)::float as score_k
    FROM chunks c
    WHERE c.content_text % p_query_text -- uses pg_trgm index
    ORDER BY similarity(c.content_text, p_query_text) DESC
    LIMIT p_match_count
  ),
  ranked_keyword AS (
    SELECT *,
           RANK() OVER (ORDER BY score_k DESC) as rank_k
    FROM keyword_search
  ),

  -- 3. Merge & RRF
  merged AS (
    SELECT 
      COALESCE(v.chunk_id, k.chunk_id) as chunk_id,
      COALESCE(v.content_text, k.content_text) as content_text,
      COALESCE(v.page_start, k.page_start) as page_start,
      COALESCE(v.page_end, k.page_end) as page_end,
      COALESCE(v.anchor_path, k.anchor_path) as anchor_path,
      v.score_v as score_vector,
      v.rank_v as rank_vector,
      k.score_k as score_keyword,
      k.rank_k as rank_keyword
    FROM ranked_vector v
    FULL OUTER JOIN ranked_keyword k ON v.chunk_id = k.chunk_id
  )

  SELECT 
    m.chunk_id,
    m.content_text,
    m.page_start,
    m.page_end,
    m.anchor_path,
    m.score_vector,
    m.rank_vector,
    m.score_keyword,
    m.rank_keyword,
    (
      COALESCE(1.0 / (p_rrf_k + m.rank_vector), 0.0) +
      COALESCE(1.0 / (p_rrf_k + m.rank_keyword), 0.0)
    )::float as rrf_score
  FROM merged m
  ORDER BY rrf_score DESC
  LIMIT p_match_count;
END;
$$;
