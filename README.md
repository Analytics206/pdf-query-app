# PDF Query Application

This application allows uploading PDF files and querying their content using natural language. It uses FastAPI, Langchain, Sentence Transformers, and ChromaDB, all running inside Docker containers managed by Docker Compose.

## Project Structure


## Setup and Running

1.  **Prerequisites:**
    *   Docker: [https://docs.docker.com/get-docker/](https://docs.docker.com/get-docker/)
    *   Docker Compose: Usually included with Docker Desktop, or install separately [https://docs.docker.com/compose/install/](https://docs.docker.com/compose/install/)

2.  **Clone the Repository (or create the files):**
    ```bash
    # git clone <your-repo-url> # If you put it in git
    cd pdf-query-app
    ```
    Make sure you have created all the files (`Dockerfile`, `docker-compose.yml`, `requirements.txt`, `app/main.py`, `.dockerignore`) and the directories (`app`, `data`, `uploads`). The `data` and `uploads` directories can be initially empty.

3.  **Build and Start the Services:**
    ```bash
    docker compose build
    docker compose up -d # -d runs in detached mode
    ```
    The first time you run `up`, it might take a while to download the Python base image and install dependencies, including the embedding model.

4.  **Check Logs (Optional):**
    ```bash
    docker compose logs -f pdf_query_app
    ```
    Look for lines indicating the embedding model is loaded and the vector store is initialized. Press `Ctrl+C` to stop following logs.

## Usage

The API is available at `http://localhost:8000`.

1.  **API Documentation:**
    Open your browser to `http://localhost:8000/docs` for interactive API documentation (Swagger UI).

2.  **Upload a PDF:**
    Use the `/upload/` endpoint (e.g., via the `/docs` page or `curl`):
    ```bash
    curl -X POST -F "file=@/path/to/your/document.pdf" http://localhost:8000/upload/
    ```
    Replace `/path/to/your/document.pdf` with the actual path to a PDF file.

3.  **Query the Content:**
    Use the `/query/` endpoint:
    ```bash
    curl -X POST -H "Content-Type: application/json" -d '{"query": "What is the main topic of the document?"}' http://localhost:8000/query/
    ```
    Replace the query string with your question.

## Persistence

The ChromaDB vector data is stored in a Docker named volume (`pdf_query_data` by default). This means:

*   If you stop (`docker compose down`) and restart (`docker compose up`) the containers, the data will still be there.
*   If you remove the container (`docker compose down`) but *not* the volume, the data persists.
*   To completely remove the data, you need to remove the volume:
    ```bash
    docker compose down # Stop containers
    docker volume rm pdf-query-app_pdf_query_data # Remove the named volume
    ```

## Stopping the Application

```bash
docker compose down