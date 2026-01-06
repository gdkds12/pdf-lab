import fitz  # PyMuPDF
import os

def create_sample_pdf():
    doc = fitz.open()

    # Page 1
    page = doc.new_page()
    page.insert_text((50, 50), "Project Thunder Phase 1 Test", fontsize=24)
    page.insert_text((50, 100), "This is a generated PDF for testing the ingest pipeline.", fontsize=14)
    page.insert_text((50, 130), "1. Introduction", fontsize=18)
    page.insert_text((50, 160), "The ingest pipeline processes PDFs to text chunks and embeddings.", fontsize=12)
    
    # Page 2
    page = doc.new_page()
    page.insert_text((50, 50), "2. Technical Details", fontsize=18)
    page.insert_text((50, 80), "We use Google Cloud Vertex AI for embeddings.", fontsize=12)
    page.insert_text((50, 100), "The model used is gemini-embedding-001.", fontsize=12)
    page.insert_text((50, 140), "Supabase is used as the vector database.", fontsize=12)

    output_path = "sample.pdf"
    doc.save(output_path)
    print(f"Sample PDF created at: {os.path.abspath(output_path)}")

if __name__ == "__main__":
    create_sample_pdf()
