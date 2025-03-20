import os
import re
import json
import base64
import PyPDF2
import docx
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify

# Load environment variables
load_dotenv()

HF_API_KEY = os.getenv("HF_API_KEY")
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")

# Define model settings
model_id = "mistralai/Mistral-7B-Instruct-v0.3"
API_URL = f"https://api-inference.huggingface.co/models/{model_id}"
headers = {"Authorization": f"Bearer {HF_API_KEY}"}

app = Flask(__name__)
app.secret_key = os.urandom(24)

class JobApplicationAssistant:
    def __init__(self):
        self.resume_text = ""
        self.job_description = ""
        self.company_info = ""
        self.email_content = ""
        
    def extract_text_from_pdf(self, pdf_file):
        """Extract text from PDF file object"""
        text = ""
        try:
            reader = PyPDF2.PdfReader(pdf_file)
            for page in reader.pages:
                text += page.extract_text()
            return text
        except Exception as e:
            print(f"Error extracting PDF: {e}")
            return None

    def extract_text_from_docx(self, docx_file):
        """Extract text from DOCX file object"""
        try:
            doc = docx.Document(docx_file)
            return "\n".join([paragraph.text for paragraph in doc.paragraphs])
        except Exception as e:
            print(f"Error extracting DOCX: {e}")
            return None
    
    def load_resume(self, file):
        """Process uploaded resume file"""
        filename = file.filename.lower()
        
        if filename.endswith('.pdf'):
            self.resume_text = self.extract_text_from_pdf(file)
        elif filename.endswith('.docx'):
            self.resume_text = self.extract_text_from_docx(file)
        else:
            return False
            
        return bool(self.resume_text)
    
    def search_job_description(self, job_url):
        """Extract job description from URL"""
        try:
            response = requests.get(job_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.extract()
                
            # Extract text
            text = soup.get_text()
            
            # Clean text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            page_text = '\n'.join(chunk for chunk in chunks if chunk)
            
            # Prepare prompt for extraction
            prompt_text = (
                "Extract the job description from the provided webpage content. "
                "Focus only on the job title, requirements, responsibilities, and qualifications. "
                "Ignore navigation elements, footers, headers, and other irrelevant content.\n\n"
                f"{page_text[:15000]}"
            )

            payload = {
                "inputs": prompt_text,
                "parameters": {
                    "max_new_tokens": 1000,
                    "return_full_text": False
                }
            }

            response = requests.post(API_URL, headers=headers, json=payload)
            
            self.job_description = response.json()[0]["generated_text"]
            return True
            
        except Exception as e:
            print(f"Error fetching job description: {e}")
            return False
    
    def get_company_info(self, company_name):
        """Get company information"""
        try:
            # Use SerpAPI for company information
            search_params = {
                "engine": "google",
                "q": f"{company_name} company information about us",
                "api_key": SERPAPI_API_KEY
            }
            
            response = requests.get("https://serpapi.com/search", params=search_params)
            response.raise_for_status()
            search_results = response.json()
            
            organic_results = search_results.get("organic_results", [])
            
            company_data = []
            for result in organic_results[:3]:
                if "snippet" in result:
                    company_data.append(result["snippet"])
                    
                    if "link" in result:
                        try:
                            page_response = requests.get(result["link"], timeout=5)
                            if page_response.status_code == 200:
                                page_soup = BeautifulSoup(page_response.text, 'html.parser')
                                
                                about_section = page_soup.find(lambda tag: tag.name == "div" and 
                                                           ("about" in tag.get("class", [""])[0].lower() if tag.get("class") else False))
                                if about_section:
                                    company_data.append(about_section.get_text())
                        except:
                            pass
            
            system_prompt = """
            Synthesize the provided information into a concise summary about the company.
            Focus on the company's mission, values, products/services, and any unique aspects.
            The information will be used to personalize a job application email.
            """

            prompt_text = (
                f"{system_prompt}\n\nHere is information about {company_name} from various sources. "
                f"Please synthesize it into a concise summary:\n\n{' '.join(company_data)}"
            )

            payload = {
                "inputs": prompt_text,
                "parameters": {"max_new_tokens": 1000, "return_full_text": False}
            }

            response = requests.post(API_URL, headers=headers, json=payload)
            self.company_info = response.json()[0]["generated_text"]
            return True
            
        except Exception as e:
            print(f"Error fetching company info: {e}")
            self.company_info = f"Information about {company_name}"
            return False
    
    def generate_personalized_email(self, recipient_name, job_title):
        """Generate personalized application email"""
        try:
            system_prompt = """
            You are an expert job application assistant. Your task is to create a highly personalized, professional 
            email for a job application based on the applicant's resume and the job description.
            
            The email should:
            1. Be addressed to the recipient by name
            2. Mention specific qualifications from the resume that match the job requirements
            3. Show knowledge of the company based on the company information provided
            4. Be concise (200-300 words)
            5. Have a professional tone
            6. Include a brief introduction, 2-3 paragraphs highlighting relevant experience, and a closing paragraph
            7. End with a professional signature
            
            Do not include attachments in the email - assume the resume will be attached separately.
            """
            
            user_prompt = f"""
            Please create a personalized job application email based on the following:
            
            RECIPIENT NAME: {recipient_name}
            JOB TITLE: {job_title}
            
            MY RESUME:
            {self.resume_text[:3000]}
            
            JOB DESCRIPTION:
            {self.job_description[:3000]}
            
            COMPANY INFORMATION:
            {self.company_info[:1000]}
            
            Please write the complete email that I can send directly.
            """
            
            conversation = (
                f"{system_prompt}\n"
                f"User: {user_prompt}\n"
                "Assistant:"
            )

            payload = {
                "inputs": conversation,
                "parameters": {"max_new_tokens": 1000, "return_full_text": False}
            }

            response = requests.post(API_URL, headers=headers, json=payload)
            self.email_content = response.json()[0]["generated_text"]
            return True
            
        except Exception as e:
            print(f"Error generating email: {e}")
            return False


# Flask routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload_resume', methods=['POST'])
def upload_resume():
    if 'resume' not in request.files:
        flash('No file part')
        return redirect(request.url)
        
    file = request.files['resume']
    
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
        
    assistant = JobApplicationAssistant()
    if assistant.load_resume(file):
        session['resume_text'] = assistant.resume_text
        return redirect(url_for('job_details'))
    else:
        flash('Error processing resume. Please upload a PDF or DOCX file.')
        return redirect(url_for('index'))

@app.route('/job_details')
def job_details():
    if 'resume_text' not in session:
        flash('Please upload your resume first')
        return redirect(url_for('index'))
    return render_template('job_details.html')

@app.route('/process_job', methods=['POST'])
def process_job():
    job_url = request.form.get('job_url', '')
    job_description = request.form.get('job_description', '')
    company_name = request.form.get('company_name', '')
    recipient_name = request.form.get('recipient_name', 'Hiring Manager')
    job_title = request.form.get('job_title', '')
    
    assistant = JobApplicationAssistant()
    assistant.resume_text = session.get('resume_text', '')
    
    # Process job details based on URL or manual entry
    if job_url and not job_description:
        success = assistant.search_job_description(job_url)
        if not success:
            flash('Could not extract job description from URL. Please paste it manually.')
            return redirect(url_for('job_details'))
    else:
        assistant.job_description = job_description
    
    # Get company info
    assistant.get_company_info(company_name)
    
    # Generate email
    assistant.generate_personalized_email(recipient_name, job_title)
    
    # Store results in session
    session['job_description'] = assistant.job_description
    session['company_info'] = assistant.company_info
    session['email_content'] = assistant.email_content
    
    return redirect(url_for('email_preview'))

@app.route('/email_preview')
def email_preview():
    if 'email_content' not in session:
        flash('Please complete all previous steps')
        return redirect(url_for('index'))
        
    email_content = session.get('email_content', '')
    return render_template('email_preview.html', email_content=email_content)

@app.route('/edit_email', methods=['POST'])
def edit_email():
    session['email_content'] = request.form.get('email_content', '')
    return redirect(url_for('email_preview'))

@app.route('/save_email', methods=['POST'])
def save_email():
    email_content = session.get('email_content', '')
    response = {
        'email_content': email_content
    }
    return jsonify(response)

if __name__ == '__main__':
    app.run(debug=True)