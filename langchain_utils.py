import os
import logging
from typing import List, Dict, Any
import tempfile

from langchain.vectorstores import Chroma
from langchain.embeddings import OpenAIEmbeddings
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.document_loaders import TextLoader
from langchain.chat_models import ChatOpenAI

# the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user
MODEL_NAME = "gpt-4o"
# Directory to store the vector database
PERSIST_DIRECTORY = "chroma_db"

def initialize_llm():
    """Initialize the LLM with API key from environment"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    
    return ChatOpenAI(
        openai_api_key=api_key,
        model=MODEL_NAME,
        temperature=0.1
    )

def get_embeddings():
    """Get OpenAI embeddings"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    
    return OpenAIEmbeddings(openai_api_key=api_key)

def get_or_create_vectorstore():
    """Get the vector store or create it if it doesn't exist"""
    embeddings = get_embeddings()
    
    # Create the persist directory if it doesn't exist
    os.makedirs(PERSIST_DIRECTORY, exist_ok=True)
    
    # Check if the vector store already exists
    if os.path.exists(PERSIST_DIRECTORY) and len(os.listdir(PERSIST_DIRECTORY)) > 0:
        # Load existing vector store
        return Chroma(persist_directory=PERSIST_DIRECTORY, embedding_function=embeddings)
    else:
        # Create a new vector store
        return Chroma(persist_directory=PERSIST_DIRECTORY, embedding_function=embeddings)

def create_vectorstore_from_documents(documents, source):
    """Create or update a vector store from documents"""
    embeddings = get_embeddings()
    
    # Split documents into chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )
    
    # Add source metadata to each document
    for doc in documents:
        if doc.metadata is None:
            doc.metadata = {}
        doc.metadata["source"] = source
    
    chunks = text_splitter.split_documents(documents)
    
    # Get or create vector store
    vectorstore = get_or_create_vectorstore()
    
    # Add documents to vector store
    vectorstore.add_documents(chunks)
    vectorstore.persist()
    
    return vectorstore

def query_vectorstore(query, k=4):
    """Query the vector store for relevant documents"""
    vectorstore = get_or_create_vectorstore()
    
    # Query for similar documents
    docs = vectorstore.similarity_search(query, k=k)
    
    # Format the context from the documents
    context = "\n\n".join([doc.page_content for doc in docs])
    
    return context

def get_conversation_chain(llm, context):
    """Create a conversation chain with the LLM and context"""
    # Create the prompt template
    prompt_template = """
    You are a helpful customer support AI assistant. Use the following context from the company's documents to answer the user's question.
    If you don't know the answer based on the context, just say that you don't know, don't try to make up an answer.
    
    Context:
    {context}
    
    Question: {question}
    
    Provide a helpful, accurate, and concise answer based only on the given context.
    """
    
    # Create the prompt from the template
    prompt = PromptTemplate(
        template=prompt_template,
        input_variables=["context", "question"]
    )
    
    # Chain type will use the prompt, LLM, and format the input docs as the context
    chain = prompt | llm
    
    return chain
