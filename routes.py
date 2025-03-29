import os
import uuid
import logging
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.utils import secure_filename

from app import app, db
from models import Document, ChatSession, ChatMessage
from utils import allowed_file, process_document, get_file_content
from langchain_utils import (
    create_vectorstore_from_documents,
    get_conversation_chain,
    query_vectorstore,
    initialize_llm
)

# Ensure a session ID is set for the user
@app.before_request
def ensure_session():
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())

@app.route('/')
def index():
    documents = Document.query.all()
    return render_template('index.html', documents=documents)

@app.route('/chat')
def chat():
    # Get or create a chat session
    session_id = session.get('session_id')
    chat_session = ChatSession.query.filter_by(session_id=session_id).first()
    
    if not chat_session:
        chat_session = ChatSession(session_id=session_id)
        db.session.add(chat_session)
        db.session.commit()
    
    # Get chat history
    messages = ChatMessage.query.filter_by(session_id=chat_session.id).order_by(ChatMessage.timestamp).all()
    
    # Check if we have processed documents
    has_documents = Document.query.filter_by(processed=True).first() is not None
    
    return render_template('chat.html', messages=messages, has_documents=has_documents)

@app.route('/upload', methods=['POST'])
def upload_file():
    # Check if a file was uploaded
    if 'file' not in request.files:
        flash('No file part', 'danger')
        return redirect(request.url)
    
    file = request.files['file']
    
    # If the user does not select a file
    if file.filename == '':
        flash('No file selected', 'danger')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        # Secure the filename and generate a unique path
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{uuid.uuid4()}_{filename}")
        
        # Save the file
        file.save(file_path)
        
        # Create a new document record
        document = Document(
            filename=filename,
            file_path=file_path,
            content_type=file.content_type
        )
        
        db.session.add(document)
        db.session.commit()
        
        # Process the document in the background
        try:
            process_document(document.id)
            flash('File uploaded successfully and is being processed.', 'success')
        except Exception as e:
            logging.error(f"Error processing document: {str(e)}")
            flash(f'Error processing document: {str(e)}', 'danger')
        
        return redirect(url_for('index'))
    else:
        flash('File type not allowed', 'danger')
        return redirect(request.url)

@app.route('/documents/<int:document_id>/delete', methods=['POST'])
def delete_document(document_id):
    document = Document.query.get_or_404(document_id)
    
    # Delete the file from the file system
    if os.path.exists(document.file_path):
        os.remove(document.file_path)
    
    # Delete the document from the database
    db.session.delete(document)
    db.session.commit()
    
    flash('Document deleted successfully', 'success')
    return redirect(url_for('index'))

@app.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.json
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({'error': 'Message is required'}), 400
    
    # Get the user's chat session
    session_id = session.get('session_id')
    chat_session = ChatSession.query.filter_by(session_id=session_id).first()
    
    if not chat_session:
        chat_session = ChatSession(session_id=session_id)
        db.session.add(chat_session)
        db.session.commit()
    
    # Save user message
    user_chat_message = ChatMessage(
        session_id=chat_session.id,
        role='user',
        content=user_message
    )
    db.session.add(user_chat_message)
    db.session.commit()
    
    try:
        # Check if we have processed documents
        if Document.query.filter_by(processed=True).count() == 0:
            response = "I don't have any company data to reference yet. Please upload some documents first."
        else:
            # Get answer from LLM
            llm = initialize_llm()
            
            # Get relevant context from the vector store
            context = query_vectorstore(user_message)
            
            # Get chat chain with context
            chain = get_conversation_chain(llm, context)
            
            # Get previous messages for context (limited to last 5 for simplicity)
            previous_messages = ChatMessage.query.filter_by(session_id=chat_session.id).order_by(
                ChatMessage.timestamp.desc()).limit(10).all()
            previous_messages.reverse()
            
            # Format previous messages for the chain
            chat_history_items = []
            for msg in previous_messages:
                if msg.id != user_chat_message.id:  # Don't include the current message
                    chat_history_items.append(f"{msg.role.capitalize()}: {msg.content}")
            
            # Format chat history as a string for the prompt
            chat_history = "\n".join(chat_history_items) if chat_history_items else "No previous messages"
            
            # Get response from the chain
            response = chain.invoke({
                "question": user_message,
                "context": context,
                "chat_history": chat_history
            })
    except Exception as e:
        logging.error(f"Error getting response from LLM: {str(e)}")
        response = f"I'm sorry, I encountered an error: {str(e)}"
    
    # Extract content if it's an AIMessage object (from LangChain)
    if hasattr(response, 'content'):
        response_content = response.content
    else:
        response_content = str(response)
    
    # Save the assistant's response
    assistant_message = ChatMessage(
        session_id=chat_session.id,
        role='assistant',
        content=response_content
    )
    db.session.add(assistant_message)
    db.session.commit()
    
    return jsonify({
        'response': response_content,
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/api/clear-chat', methods=['POST'])
def clear_chat():
    # Get the user's chat session
    session_id = session.get('session_id')
    chat_session = ChatSession.query.filter_by(session_id=session_id).first()
    
    if chat_session:
        # Delete all messages in the session
        ChatMessage.query.filter_by(session_id=chat_session.id).delete()
        db.session.commit()
    
    return jsonify({'success': True})
