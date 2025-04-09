from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Dict, List, Union, Optional, Any
from fastapi.middleware.cors import CORSMiddleware
import logging
import json
import os
from dotenv import load_dotenv
from main import AWRAnalyzer, DatabaseAnalysis, create_ticket as main_create_ticket

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(env_path)

# Debug environment variables
logger.debug("API: Environment variables loaded from: %s", env_path)
logger.debug("API: SMTP_USERNAME present: %s", bool(os.getenv("SMTP_USERNAME")))
logger.debug("API: SMTP_PASSWORD present: %s", bool(os.getenv("SMTP_PASSWORD")))
logger.debug("API: RECIPIENT_EMAIL present: %s", bool(os.getenv("RECIPIENT_EMAIL")))

# Initialize analyzer with AWR report files
current_dir = os.path.dirname(os.path.abspath(__file__))
awr_report_dir = os.path.join(current_dir, "awr_reports")
awr_files = []

# Walk through the awr_reports directory to find all HTML files
for root, dirs, files in os.walk(awr_report_dir):
    for file in files:
        if file.endswith('.html'):
            awr_files.append(os.path.join(root, file))

if not awr_files:
    raise RuntimeError("No AWR report files found in the awr_reports directory")

analyzer = AWRAnalyzer(file_paths=awr_files)

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QuestionRequest(BaseModel):
    question: str

class AnalysisResponse(BaseModel):
    analysis: DatabaseAnalysis

def create_ticket_background(health_status: str, analysis_result: dict):
    """Create a ticket based on health status in the background"""
    logger.info('API: Starting background ticket creation for health status: %s', health_status)
    try:
        main_create_ticket(health_status, analysis_result)
        logger.info('API: Background ticket creation completed successfully')
    except Exception as e:
        logger.error('API: Failed to create ticket in background: %s', str(e), exc_info=True)

@app.post("/analyze/", response_model=AnalysisResponse)
def analyze_question(request: QuestionRequest, background_tasks: BackgroundTasks):
    """Analyze AWR report based on the question"""
    logger.info('Received question: %s', request.question)
    try:
        result = analyzer.analyze(request.question)
        
        if not isinstance(result, dict):
            logger.error(f'Invalid result format: {type(result)}')
            raise HTTPException(
                status_code=500, 
                detail="Invalid response format from analyzer"
            )

        # Schedule ticket creation in background if needed
        health_status = result.get("health_status", "Unknown")
        logger.info('Health status received: %s', health_status)
        
        if health_status.upper() in ['WARNING', 'CRITICAL']:
            logger.info('Scheduling background ticket creation for health status: %s', health_status)
            background_tasks.add_task(create_ticket_background, health_status, result)
            logger.info('Background ticket creation scheduled')

        return {"analysis": result}
        
    except Exception as e:
        error_msg = f"Analysis failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg)

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)