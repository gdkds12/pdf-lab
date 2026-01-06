import argparse
import sys
import logging
from src.phase1 import ingest_pipeline
from src.phase2 import signal_extraction
from src.phase3 import retrieval_pipeline
from src.phase4 import reasoning_pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Project Thunder Cloud Run Job Dispatcher")
    parser.add_argument("--phase", type=str, required=True, choices=["1", "2", "3", "4"], help="Phase to execute")
    parser.add_argument("--job-payload", type=str, help="JSON string with job arguments")
    
    # Arguments for specific phases can be added here or parsed from job-payload environment variable
    # Cloud Run Jobs often pass environment variables rather than CLI args for complex JSON, 
    # but we will support basic CLI args for testing.
    
    args, unknown = parser.parse_known_args()
    
    logger.info(f"Starting Project Thunder Worker - Phase {args.phase}")
    
    try:
        if args.phase == "1":
            ingest_pipeline.run(args.job_payload)
        elif args.phase == "2":
            signal_extraction.run(args.job_payload)
        elif args.phase == "3":
            retrieval_pipeline.run(args.job_payload)
        elif args.phase == "4":
            reasoning_pipeline.run(args.job_payload)
    except Exception as e:
        logger.error(f"Phase {args.phase} failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
