from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from main import JobApplicationAssistant
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

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

@app.route('/fetch_job_description', methods=['POST'])
def fetch_job_description():
    """API endpoint for fetching job description from URL via AJAX"""
    job_url = request.form.get('job_url', '')
    
    if not job_url:
        return jsonify({'success': False, 'message': 'No URL provided'})
    
    try:
        assistant = JobApplicationAssistant()
        success = assistant.search_job_description(job_url)
        
        if success:
            # Return the extracted job description and other data
            return jsonify({
                'success': True,
                'job_description': assistant.job_description,
                'company_name': assistant.company_name if hasattr(assistant, 'company_name') else '',
                'job_title': assistant.job_title if hasattr(assistant, 'job_title') else ''
            })
        else:
            return jsonify({'success': False, 'message': 'Could not extract job description'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/process_job', methods=['POST'])
def process_job():
    job_url = request.form.get('job_url', '')
    job_description = request.form.get('job_description', '')
    company_name = request.form.get('company_name', '')
    recipient_name = request.form.get('recipient_name', 'Hiring Manager')
    job_title = request.form.get('job_title', '')
    
    assistant = JobApplicationAssistant()
    assistant.resume_text = session.get('resume_text', '')
    
    # Process job details - we now rely more on manual entry
    # since auto-extraction happened earlier via AJAX
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