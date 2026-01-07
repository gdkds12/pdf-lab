import argparse
import sys
import os
import logging
from src.phase1 import ingest_pipeline
from src.phase2 import signal_extraction, dispatcher
from src.phase3 import retrieval_pipeline
from src.phase4 import reasoning_pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Project Thunder Cloud Run Job Dispatcher")
    # Added 'split' to choices
    parser.add_argument("--phase", type=str, required=True, choices=["1", "2", "3", "4", "split"], help="Phase to execute")
    parser.add_argument("--job-payload", type=str, help="JSON string with job arguments")
    
    # Arguments for specific phases can be added here or parsed from job-payload environment variable
    # Cloud Run Jobs often pass environment variables rather than CLI args for complex JSON, 
    # but we will support basic CLI args for testing.
    
    args = parser.parse_args()
    
    # Allow passing job payload via environment variable
    job_payload = args.job_payload or os.environ.get("JOB_PAYLOAD")
    
    try:
        if args.phase == "1":
            if not job_payload:
                logger.error("Phase 1 requires --job-payload with JSON string")
                sys.exit(1)
            ingest_pipeline.run(job_payload)
        
        elif args.phase == "split":
             if not job_payload:
                logger.error("Phase split requires --job-payload")
                sys.exit(1)
             dispatcher.run(job_payload)

        elif args.phase == "2":
            # logger.info("Phase 2 not implemented yet")
            signal_extraction.run(job_payload)
            
        elif args.phase == "3":
            if not job_payload:
                logger.error("Phase 3 requires --job-payload")
                sys.exit(1)
            retrieval_pipeline.run(job_payload)
        
        elif args.phase == "4":
            if not job_payload:
                logger.error("Phase 4 requires --job-payload")
                sys.exit(1)
            reasoning_pipeline.run(job_payload)
            
    except Exception as e:
        logger.error(f"Job Failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
