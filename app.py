import os
from flask import Flask, render_template, request, make_response
from werkzeug.utils import secure_filename
import google.generativeai as palm

import PyPDF2
import docx
import re
import ast

import pandas as pd

import pymongo
# import json

#######################################################################
#connecting to MongoDb
try:
    mongo=pymongo.MongoClient(host="localhost",
                              port=27017,
                              serverSelectionTimeoutMS=1000
                              )
    db=mongo.resume #name of the database
    collection=db['students']
    mongo.server_info() #triggers an exception if we cannot connect to db
    print("connection succesful")
except:
    print("cannot connect to db")

app = Flask(__name__)
palm.configure(api_key="AIzaSyDR3fQbK7mG4Rvowdr3kyzAiWAjaobtIIY")

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'docx', 'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

import re

def remove_unwanted_symbols(text):
  """Removes unwanted symbols from text.

  Args:
    text: The input text.

  Returns:
    A string containing the preprocessed text.
  """

  # Remove unwanted symbols
  

  text = re.sub(r"[^\w\s\.\,\/\@]", "", text)
  text = text.replace("'", "")
  # # text = re.sub(r'[^\w\s.]+', '', text)
  text=" ".join(text.split())

  return text


def extract_text_from_pdf(pdf_file):
    """Extracts text from a PDF file.

    Args:
        pdf_file: The path to the PDF file.

    Returns:
        A string containing the extracted text.
    """

    pdf_reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() 
    return text

def extract_text_from_docx(docx_file):
    """Extracts text from a DOCX file.

    Args:
        docx_file: The path to the DOCX file.

    Returns:
        A string containing the extracted text.
    """

    docx_reader = docx.Document(docx_file)
    text = ""
    for paragraph in docx_reader.paragraphs:
        text += paragraph.text
    return text

def extract_text_from_resume(resume_file):
    """Extracts text from a resume file.

    Args:
        resume_file: The path to the resume file.

    Returns:
        A string containing the extracted text.
    """

    if resume_file.endswith(".pdf"):
        return extract_text_from_pdf(resume_file)
    elif resume_file.endswith(".docx"):
        return extract_text_from_docx(resume_file)
    else:
        raise ValueError("Unsupported resume file format")
    


@app.route('/', methods=['GET', 'POST'])
def upload_file():
    global df2
    df2=pd.DataFrame(columns=['Filename',
    'Name',
    'Phone',
    'Email',
    'Skills',
    'Education',
    'Work Experience'])

    if request.method == 'POST':
        uploaded_files = request.files.getlist('file')
        extracted_text = []
        errored_files = []
        count=0

        for file in uploaded_files:
            # if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    
            text=extract_text_from_resume(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            text=remove_unwanted_symbols(text)

            print(text)

            models = [m for m in palm.list_models() if 'generateText' in m.supported_generation_methods]
            model = models[0].name

            prompt = f"""
            You are an expert resume parser. For the given resume data, parse the resume and return only the List of details in the following format: [Name, phone number, email, [list of skills], [list of education], [list of experience (years-company-role)]]. The output should start and end with square brackets of the list only.
            
            resume data : {text} 


            """
            
            print(filename, "ongoing")

            completion = palm.generate_text(
                model=model,
                prompt=prompt,
                temperature=0,
                # The maximum length of the response
                max_output_tokens=800,
            )
            # print(i, " done")
            op_text=completion.result
            print("I am here ------->>>>",op_text)

            try:
                converted_text=ast.literal_eval(op_text)
                print(converted_text)
                extracted_text.append([filename,converted_text])
                count+=1
            except Exception as e:
                print(e)
                errored_files.append(filename)



        # print(extracted_text)

        #creating a dataframe
        for i in extracted_text:# Extract data from the nested structure
            filename = i[0]
            personal_info = i[1]
            name=personal_info[0]
            phone=personal_info[1]
            email=personal_info[2]
            skills = personal_info[3]
            education = personal_info[4]
            work_experience = personal_info[5]
            print(f"Name : {name}, phone:{phone},edu: {education}")

        # Create a DataFrame
        # Extract the job positions and join them with commas
            job_positions = [', '.join(info) for info in work_experience]

            # 'Work Experience' will be a string containing all the job positions separated by commas
            

            new_row={
            'Filename': filename,
            'Name': name,
            'Phone': phone,
            'Email': email,
            'Skills': ', '.join(skills),
            'Education': ', '.join(education),
            'Work Experience': ', '.join(job_positions)
        }
            
            # print(new_row)
            

            df2=pd.concat([df2, pd.DataFrame([new_row])], ignore_index=True)


       

        df2.to_csv('resume2.csv')

        try:
            records = df2.to_dict(orient='records')
            collection.insert_many(records)
        except Exception as e:
            print(e)
            print("----------------------")

        return render_template('index.html',extracted_text=extracted_text, errored_files=errored_files)

        

    return render_template('index.html')


@app.route('/export-csv', methods=['POST'])
def export_csv():
    print("clicked export csv")
    # df = create_dataframe()  # Replace with your existing DataFrame
    
    csv_data = df2.to_csv(index=False)
    response = make_response(csv_data)
    response.headers["Content-Disposition"] = "attachment; filename=data.csv"
    response.headers["Content-type"] = "text/csv"
    return response

if __name__ == '__main__':
    app.run(debug=True)
