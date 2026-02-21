#!/usr/bin/env python3
import json
import subprocess
import sys
import requests
from pathlib import Path

API = "https://api.thunder-ai.org/rest/v1"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0"
HEADERS = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


def gcloud_execute(args):
    cmd = ["gcloud", "run", "jobs", "execute", "thunder-worker", "--region=asia-northeast3", f"--args={args}"]
    subprocess.run(cmd, check=True)


def main(dataset_path: str):
    data = json.loads(Path(dataset_path).read_text())
    subject_id = data["subject_id"]

    # 1) retry source ingest
    source_id = data["pdf"]["source_id"]
    pdf_url = data["pdf"]["gcs_pdf_url"]
    requests.patch(
        f"{API}/sources?source_id=eq.{source_id}",
        headers=HEADERS,
        data=json.dumps({"ingest_status": "queued", "page_count": None}),
        timeout=30,
    ).raise_for_status()
    payload = json.dumps({"source_id": source_id, "gcs_pdf_url": pdf_url}, ensure_ascii=False)
    gcloud_execute(f"--phase,1,--job-payload,{payload}")

    # 2) create fresh 10 sessions + split jobs
    created = []
    for row in data["audio_sessions"]:
        audio_url = row["gcs_audio_url"]
        sess = requests.post(
            f"{API}/sessions",
            headers=HEADERS,
            data=json.dumps([
                {
                    "user_id": data.get("user_id", "a3d5b0c7-7759-4ecc-9094-26b48897a10f"),
                    "subject_id": subject_id,
                    "exam_window": "midterm",
                    "gcs_audio_url": audio_url,
                    "status": "queued",
                }
            ]),
            timeout=30,
        )
        sess.raise_for_status()
        sid = sess.json()[0]["session_id"]
        created.append(sid)

        split_payload = json.dumps(
            {
                "session_id": sid,
                "gcs_audio_url": audio_url,
                "subject": "회로이론",
                "exam_window": "midterm",
            },
            ensure_ascii=False,
        )
        gcloud_execute(f"--phase,split,--job-payload,{split_payload}")

    print(json.dumps({"subject_id": subject_id, "new_session_ids": created}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: run_auto_test_cycle.py /path/to/TEST_DATASET_AUTO.json")
        sys.exit(1)
    main(sys.argv[1])
