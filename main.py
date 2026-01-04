import os
import json
import shutil
import subprocess
import uvicorn
import requests # <--- Added for Job Link scraping
from bs4 import BeautifulSoup # <--- Added for Job Link scraping
from fastapi import FastAPI, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from jinja2 import Environment, FileSystemLoader
from pypdf import PdfReader

# --- 1. CONFIGURATION ---
app = FastAPI(title="Resume & Cover Letter Generator")

# Fix: Add Middleware AFTER the final app declaration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Fix: Put your actual key string here directly for testing, OR use os.getenv("GROQ_API_KEY")
# If you want to hardcode it for now (don't share this file publicly):
GROQ_API_KEY = "GROQ_API_KEY" 
client = Groq(api_key=GROQ_API_KEY)

# Jinja2 Setup
env = Environment(
    loader=FileSystemLoader("templates"),
    block_start_string='\BLOCK{',
    block_end_string='}',
    variable_start_string='\VAR{',
    variable_end_string='}',
    comment_start_string='\#{',
    comment_end_string='}',
    line_statement_prefix='%%',
    line_comment_prefix='%#',
    trim_blocks=True,
    autoescape=False,
)

PERSONAL_INFO = {
    "name": "Ishaan Pandey",
    "phone": "9354740459",
    "email": "iamishaanpandey@gmail.com",
    "linkedin": "iamishaaanpandey",
    "github": "https://www.ishaanpandey.dev/",
    "university": "Bachelor of Technology, Computer Science & Engineering"
}

# --- HELPER FUNCTIONS ---

def scrape_job_link(url: str) -> str:
    """Simple scraper to get text from a URL"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        # Get text and clean it up
        text = soup.get_text(separator=' ', strip=True)
        return text[:10000] # Limit to 10k chars to save tokens
    except Exception as e:
        print(f"Scraping failed: {e}")
        return ""

def compile_latex(job_id: str, tex_content: str, filename_base: str):
    work_dir = f"/tmp/{job_id}"
    os.makedirs(work_dir, exist_ok=True)
    
    tex_filename = f"{filename_base}.tex"
    tex_path = os.path.join(work_dir, tex_filename)
    
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(tex_content)
    
    try:
        # Note: Ensure 'pdflatex' is installed on your system!
        cmd = ["pdflatex", "-interaction=nonstopmode", "-output-directory", work_dir, tex_path]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError as e:
        print(f"LaTeX Compilation Failed: {e}")
        raise HTTPException(status_code=500, detail="LaTeX compilation failed. Is TeX Live installed?")

    pdf_filename = f"{filename_base}.pdf"
    return os.path.join(work_dir, pdf_filename)

def extract_text_from_pdf(file: UploadFile) -> str:
    text = ""
    try:
        reader = PdfReader(file.file)
        for page in reader.pages:
            text += page.extract_text() or ""
    except Exception as e:
        print(f"Error reading PDF: {e}")
    return text

# --- ENDPOINTS ---

@app.post("/generate")
async def generate_resume(
    job_desc: str = Form(None),     # Made optional
    job_link: str = Form(None),     # Added support for Link
    old_resume: UploadFile = None
):
    # 1. Handle Job Input Logic
    final_job_text = ""
    if job_desc:
        final_job_text = job_desc
    elif job_link:
        final_job_text = scrape_job_link(job_link)
    
    if not final_job_text:
        raise HTTPException(status_code=400, detail="Please provide either a Job Description or a Job Link.")

    # 2. Parse Old Resume
    resume_text = ""
    if old_resume:
        resume_text = extract_text_from_pdf(old_resume)
    
    # 3. Define Prompt
    system_prompt = """
    You are an expert ATS resume writer. 
    Analyze the user's old resume and the target job description.
    Rewrite the resume content to highlight skills relevant to the job.
    
    CRITICAL OUTPUT RULES:
    1. Output ONLY valid JSON.
    2. Do NOT use Markdown code blocks.
    3. Use strong action verbs.
    
    REQUIRED JSON STRUCTURE matches the Jinja2 template keys exactly.
    """ 
    # (Keeping your original prompt content abbreviated here for brevity, 
    # but in your actual file, keep the full prompt!)

    # ... [Rest of your Resume Logic is fine] ...
    # Just ensure you use 'final_job_text' instead of 'job_desc' in the user_message construction.
    
    user_message = f"OLD RESUME:\n{resume_text[:4000]}\n\nTARGET JOB DESCRIPTION:\n{final_job_text}"

    # ... [AI Call and PDF Generation Code remains same] ...
    
    # For now, returning a dummy placeholder to show flow until you paste the full logic back
    # (In your real file, keep the rest of your original function logic)
    return {"status": "Please ensure you updated the user_message variable to use final_job_text"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)