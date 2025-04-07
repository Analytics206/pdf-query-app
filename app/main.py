import os
import shutil
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from pydantic import BaseModel
import uvicorn
import logging
import time # Added for potential timing logs

from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

# --- Configuration ---
UPLOAD_DIR = Path("uploads") # Directory for API uploads AND pre-loading
DB_DIR = Path("data")
DB_PERSIST_DIR = str(DB_DIR / "chroma_db")
MODEL_NAME = "all-MiniLM-L6-v2"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100
TARGET_SOURCE_CHUNKS = 4

# --- Initialize ---
# Ensure directories exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DB_DIR.mkdir(parents=True, exist_ok=True)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="PDF Query API")

# Initialize Embeddings
logger.info(f"Loading embedding model: {MODEL_NAME}")
embeddings = HuggingFaceEmbeddings(model_name=MODEL_NAME)
logger.info("Embedding model loaded.")

# Initialize Vector Store (ChromaDB)
logger.info(f"Initializing vector store from: {DB_PERSIST_DIR}")
vector_store = Chroma(
    persist_directory=DB_PERSIST_DIR,
    embedding_function=embeddings
)
logger.info("Vector store initialized.")

# Initialize Text Splitter
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP
)

# --- Helper Functions ---
def process_pdf(file_path: Path):
    """Loads, splits, and adds a PDF document to the vector store."""
    if not file_path.exists() or not file_path.is_file():
        logger.warning(f"process_pdf called with invalid path: {file_path}")
        return False

    try:
        logger.info(f"Processing PDF: {file_path.name}")
        loader = PyPDFLoader(str(file_path))
        documents = loader.load()

        if not documents:
            logger.warning(f"No content loaded from PDF: {file_path.name}")
            return False # Indicate failure but don't delete yet if needed below

        logger.info(f"Splitting {len(documents)} document pages into chunks...")
        docs_split = text_splitter.split_documents(documents)

        if not docs_split:
            logger.warning(f"Text splitting resulted in zero chunks for: {file_path.name}")
            return False # Indicate failure

        logger.info(f"Adding {len(docs_split)} chunks to vector store...")
        vector_store.add_documents(docs_split)

        logger.info(f"Successfully processed and added {file_path.name} to vector store.")
        return True # Indicate success

    except Exception as e:
        logger.error(f"Error processing PDF {file_path.name}: {e}", exc_info=True)
        return False # Indicate failure
    # ---- IMPORTANT: REMOVAL LOGIC MOVED ----
    # Removal is now handled by the caller (preload or upload endpoint)
    # based on the success status.


# --- Pre-loading Logic (Runs on Application Startup) ---
def preload_pdfs_from_directory(directory: Path):
    """Scans a directory for PDFs and processes them."""
    logger.info(f"Scanning directory for pre-loading: {directory}")
    processed_count = 0
    failed_count = 0
    start_time = time.time()

    for item in directory.iterdir():
        if item.is_file() and item.suffix.lower() == '.pdf':
            logger.info(f"Found PDF for pre-loading: {item.name}")
            success = process_pdf(item)
            if success:
                processed_count += 1
                # Optionally delete the file after successful processing
                try:
                    os.remove(item)
                    logger.info(f"Removed pre-loaded file: {item.name}")
                except OSError as e:
                    logger.error(f"Error removing pre-loaded file {item}: {e}")
            else:
                failed_count += 1
                logger.warning(f"Failed to pre-load {item.name}. File left in place.")
        elif item.is_dir():
             logger.debug(f"Skipping sub-directory: {item.name}")
        elif item.is_file():
             logger.debug(f"Skipping non-PDF file: {item.name}")


    end_time = time.time()
    logger.info(f"Pre-loading finished in {end_time - start_time:.2f} seconds. "
                f"Processed: {processed_count}, Failed: {failed_count}.")

# --- Run Pre-loading ---
# This code runs when the module is first imported (i.e., on app startup)
preload_pdfs_from_directory(UPLOAD_DIR)
# -----------------------


# --- API Models ---
class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    query: str
    relevant_chunks: list[dict]

class UploadResponse(BaseModel):
    filename: str
    message: str
    success: bool

# --- API Endpoints ---
@app.post("/upload/", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    """
    Receives a PDF file, saves it temporarily, processes it,
    and adds its content to the vector database.
    """
    if file.content_type != 'application/pdf':
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDFs are allowed.")

    # Use the same UPLOAD_DIR for temporary storage
    temp_file_path = UPLOAD_DIR / f"api_{file.filename}" # Add prefix to avoid name clashes maybe?
    logger.info(f"Receiving file via API: {file.filename}")

    try:
        # Save the uploaded file temporarily
        with temp_file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"File saved temporarily to: {temp_file_path}")

        # Process the PDF
        success = process_pdf(temp_file_path)

        if success:
            # ---- ADDED: Remove file after successful processing ----
            try:
                os.remove(temp_file_path)
                logger.info(f"Removed temporary API file: {temp_file_path}")
            except OSError as e:
                logger.error(f"Error removing temporary API file {temp_file_path}: {e}")
            # ------------------------------------------------------
            return UploadResponse(filename=file.filename, message="PDF processed and added to store.", success=True)
        else:
             # If processing failed, leave the file for debugging? Or remove? Let's remove.
             if temp_file_path.exists():
                try:
                    os.remove(temp_file_path)
                    logger.info(f"Removed failed temporary API file: {temp_file_path}")
                except OSError as e:
                    logger.error(f"Error removing failed temporary API file {temp_file_path}: {e}")
             raise HTTPException(status_code=500, detail=f"Failed to process PDF: {file.filename}")

    except HTTPException as http_exc:
        if temp_file_path.exists(): # Clean up if error before processing finishes
             try: os.remove(temp_file_path)
             except OSError: pass
        raise http_exc
    except Exception as e:
        logger.error(f"Error during file upload/processing for {file.filename}: {e}", exc_info=True)
        if temp_file_path.exists():
             try: os.remove(temp_file_path)
             except OSError: pass
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")
    finally:
         await file.close()


@app.post("/query/", response_model=QueryResponse)
async def query_vectors(request: QueryRequest = Body(...)):
    """
    Receives a query string, finds relevant document chunks
    from the vector store, and returns them.
    """
    # ... (query endpoint remains the same) ...
    query = request.query
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    logger.info(f"Received query: {query}")

    try:
        # Perform similarity search
        results = vector_store.similarity_search_with_score(
            query,
            k=TARGET_SOURCE_CHUNKS
        )

        logger.info(f"Found {len(results)} relevant chunks.")

        # Format results
        relevant_chunks = []
        for doc, score in results:
            relevant_chunks.append({
                "source": doc.metadata.get("source", "Unknown source") + (f" page {doc.metadata.get('page', '?')}" if 'page' in doc.metadata else ""),
                "content": doc.page_content,
                "score": float(score) # Ensure score is JSON serializable
            })

        return QueryResponse(query=query, relevant_chunks=relevant_chunks)

    except Exception as e:
        logger.error(f"Error during query processing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing query: {e}")


@app.get("/")
def read_root():
    return {"message": "PDF Query API is running. Use /docs for API documentation."}

# --- Main Execution (for local dev without Docker) ---
# if __name__ == "__main__":
#     uvicorn.run(app, host="0.0.0.0", port=8000)