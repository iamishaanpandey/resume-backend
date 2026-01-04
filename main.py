import os
import json
import subprocess
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from jinja2 import Environment, FileSystemLoader
from pypdf import PdfReader

# --- 1. CONFIGURATION ---
app = FastAPI(title="Resume & Cover Letter Generator")

# Allow Frontend to talk to Backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Groq Client
# It will read the key you passed in the 'docker run' command
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Setup Jinja2 for LaTeX
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

# --- 2. HELPER FUNCTIONS ---

def scrape_job_link(url: str) -> str:
    """Scrapes text from a job posting URL."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        text = soup.get_text(separator=' ', strip=True)
        return text[:10000]  # Limit to 10k chars
    except Exception as e:
        print(f"Scraping failed: {e}")
        return ""

def escape_latex(text: str) -> str:
    """Escapes special LaTeX characters to prevent PDF crashes."""
    if not isinstance(text, str):
        return text
    replacements = {
        '%': '\\%',
        '$': '\\$',
        '#': '\\#',
        '_': '\\_',
        '&': '\\&',
        '{': '\\{',
        '}': '\\}',
        '~': '\\textasciitilde{}',
        '^': '\\textasciicircum{}'
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text

def clean_json_data(data):
    """Recursively escapes LaTeX characters in the JSON data."""
    if isinstance(data, dict):
        return {k: clean_json_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_json_data(item) for item in data]
    elif isinstance(data, str):
        return escape_latex(data)
    else:
        return data

def compile_latex(job_id: str, tex_content: str, filename_base: str):
    """Compiles LaTeX to PDF."""
    work_dir = f"/tmp/{job_id}"
    os.makedirs(work_dir, exist_ok=True)
    
    tex_filename = f"{filename_base}.tex"
    tex_path = os.path.join(work_dir, tex_filename)
    
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(tex_content)
    
    try:
        # Run pdflatex twice for formatting
        cmd = ["pdflatex", "-interaction=nonstopmode", "-output-directory", work_dir, tex_path]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError as e:
        print(f"LaTeX Compilation Failed: {e}")
        raise HTTPException(status_code=500, detail="LaTeX compilation failed on the server.")

    return os.path.join(work_dir, f"{filename_base}.pdf")

def extract_text_from_pdf(file: UploadFile) -> str:
    text = ""
    try:
        reader = PdfReader(file.file)
        for page in reader.pages:
            text += page.extract_text() or ""
    except Exception as e:
        print(f"Error reading PDF: {e}")
    return text

# --- 3. ENDPOINTS ---

@app.post("/generate")
async def generate_resume(
    job_desc: str = Form(None),
    job_link: str = Form(None),
    old_resume: UploadFile = None
):
    # 1. Handle Inputs
    final_job_text = ""
    if job_desc and len(job_desc.strip()) > 0:
        final_job_text = job_desc
    elif job_link:
        final_job_text = scrape_job_link(job_link)
    
    if not final_job_text:
        raise HTTPException(status_code=400, detail="Please provide Job Description or Job Link")
    
    resume_text = ""
    if old_resume:
        resume_text = extract_text_from_pdf(old_resume)

    # 2. Define Prompt
    system_prompt = """
    You are an expert ATS resume writer. 
    Analyze the user's old resume and the target job description.
    Rewrite the resume content to highlight skills relevant to the job.
    
    CRITICAL RULES:
    1. Output ONLY valid JSON.
    2. Do NOT use Markdown blocks.
    3. Do NOT use special characters like % or $ or & in the text values (spell them out: percent, USD, and).
    
    REQUIRED JSON STRUCTURE:
    {
        "summary": "Professional summary...",
        "experience": [
            {
                "company": "Company Name",
                "location": "City, Country",
                "role": "Role Title",
                "duration": "Dates",
                "points": ["Action bullet 1", "Action bullet 2"]
            }
        ],
        "projects": [
            {
                "title": "Project Name",
                "technologies": "Tools used",
                "points": ["Bullet 1", "Bullet 2"]
            }
        ],
        "skills": {
            "analytics": "Analytics tools",
            "ml_ai": "AI tools",
            "languages": "Programming languages",
            "web": "Web technologies",
            "tools": "Other tools"
        },
        "education": [
            {"institution": "Uni Name", "year": "2022-2026", "degree": "Degree", "score": "CGPA"}
        ]
    }
    """

    user_message = f"OLD RESUME:\n{resume_text[:4000]}\n\nTARGET JOB:\n{final_job_text[:4000]}"

    # 3. Call AI
    try:
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            response_format={"type": "json_object"},
            temperature=0.4
        )
        ai_data = json.loads(response.choices[0].message.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Error: {str(e)}")

    # 4. Clean Data & Render
    clean_data = clean_json_data(ai_data)
    full_data = {"personal_info": PERSONAL_INFO, **clean_data}

    try:
        template = env.get_template("resume_template.tex")
        rendered_tex = template.render(**full_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Template Error: {str(e)}")

    # 5. Compile & Return
    company_name = "Resume"
    if clean_data.get("experience"):
        company_name = clean_data["experience"][0]["company"].split()[0]
    
    safe_name = "".join(x for x in company_name if x.isalnum())
    job_id = f"res_{safe_name}"
    
    pdf_path = compile_latex(job_id, rendered_tex, "resume")

    return FileResponse(pdf_path, media_type="application/pdf", filename=f"Ishaan_Resume_{safe_name}.pdf")


@app.post("/generate_cover_letter")
async def generate_cover_letter_pdf(
    job_desc: str = Form(None),
    job_link: str = Form(None),
    old_resume: UploadFile = None
):
    # 1. Handle Inputs
    final_job_text = ""
    if job_desc and len(job_desc.strip()) > 0:
        final_job_text = job_desc
    elif job_link:
        final_job_text = scrape_job_link(job_link)

    resume_text = ""
    if old_resume:
        resume_text = extract_text_from_pdf(old_resume)

    # 2. Prompt
    system_prompt = """
    Write a persuasive cover letter based on the Resume and Job.
    OUTPUT JSON ONLY:
    {
        "company_name": "Company Name",
        "job_role": "Job Title",
        "job_location": "Location",
        "letter_body": "Full body text. Use double newlines \\n\\n for paragraphs."
    }
    """
    
    user_message = f"RESUME: {resume_text[:3000]}... \n JOB: {final_job_text[:3000]}"

    # 3. Call AI
    try:
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            response_format={"type": "json_object"},
            temperature=0.7
        )
        ai_data = json.loads(response.choices[0].message.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Error: {str(e)}")

    # 4. Render
    clean_data = clean_json_data(ai_data)
    full_data = {"personal_info": PERSONAL_INFO, **clean_data}

    template = env.get_template("cover_letter_template.tex")
    rendered_tex = template.render(**full_data)

    # 5. Compile
    safe_company = "".join(x for x in clean_data['company_name'] if x.isalnum())
    job_id = f"cl_{safe_company}"
    
    pdf_path = compile_latex(job_id, rendered_tex, "cover_letter")

    return FileResponse(pdf_path, media_type="application/pdf", filename=f"Ishaan_CL_{safe_company}.pdf")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)