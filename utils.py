import os
import logging
from werkzeug.utils import secure_filename
from app import app, db
from models import Document
from langchain_utils import create_vectorstore_from_documents

# List of allowed file extensions
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'doc', 'docx', 'csv', 'md'}

def allowed_file(filename):
    """Check if the file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_document(document_id):
    """Process the uploaded document and update its status"""
    document = Document.query.get(document_id)
    
    if not document:
        logging.error(f"Document with ID {document_id} not found")
        return
    
    try:
        # Get file content based on the file type
        logging.debug(f"Processing document: {document.filename} ({document.content_type})")
        content = get_file_content(document.file_path)
        
        # Create or update the vector store with this document
        create_vectorstore_from_documents(content, document.filename)
        
        # Mark the document as processed
        document.processed = True
        db.session.commit()
        
        logging.debug(f"Document processed successfully: {document.filename}")
    except Exception as e:
        logging.error(f"Error processing document {document.filename}: {str(e)}")
        raise

def get_file_content(file_path):
    """Extract content from a file based on its extension"""
    _, extension = os.path.splitext(file_path)
    extension = extension.lower()
    
    try:
        if extension == '.pdf':
            from langchain.document_loaders import PyPDFLoader
            loader = PyPDFLoader(file_path)
            return loader.load()
        elif extension in ['.doc', '.docx']:
            from langchain.document_loaders import Docx2txtLoader
            loader = Docx2txtLoader(file_path)
            return loader.load()
        elif extension == '.csv':
            from langchain.document_loaders import CSVLoader
            loader = CSVLoader(file_path)
            return loader.load()
        elif extension in ['.txt', '.md']:
            from langchain.document_loaders import TextLoader
            loader = TextLoader(file_path)
            return loader.load()
        else:
            raise ValueError(f"Unsupported file type: {extension}")
    except Exception as e:
        logging.error(f"Error loading file {file_path}: {str(e)}")
        raise
