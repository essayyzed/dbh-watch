from functools import lru_cache
import logging
import smtplib
import ssl
from typing import List, Dict, Any, Sequence
import os
import json
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(env_path)

# Debug environment variables
logger.debug("Environment variables loaded from: %s", env_path)
logger.debug("SMTP_USERNAME present: %s", bool(os.getenv("SMTP_USERNAME")))
logger.debug("SMTP_PASSWORD present: %s", bool(os.getenv("SMTP_PASSWORD")))
logger.debug("RECIPIENT_EMAIL present: %s", bool(os.getenv("RECIPIENT_EMAIL")))

from langchain_community.document_loaders import BSHTMLLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.embeddings import GPT4AllEmbeddings
from langchain_ollama import ChatOllama
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv

# Define your data structure
class DatabaseAnalysis(BaseModel):
    health_status: str = Field(
        description="Overall database health status: 'Critical', 'Warning', or 'Good'"
    )
    summary: Dict[str, str] = Field(
        description="Contains 'direct_answer' and 'assessment' of the database state"
    )
    key_metrics: Dict[str, Any] = Field(
        description="Key metrics with their current values and trends"
    )
    performance_impact: Dict[str, Any] = Field(
        description="Current impact on database performance and resource utilization"
    )
    recommendations: List[Dict[str, str]] = Field(
        description="List of recommendations with expected benefits"
    )

# Initialize core components
try:
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
    #llm = ChatOllama(model="llama3.1:8b", temperature=0)
    llm = ChatOpenAI(model="gpt-4", temperature=0)

except Exception as e:
    logger.critical(f"Failed to initialize core components: {str(e)}")
    raise

class AWRAnalyzer:
    def __init__(self, file_paths: Sequence[str]):
        self.file_paths = file_paths
        self.vectorstore = None
        self.initialized = False
        
        # Set up parser and prompt template
        self.parser = JsonOutputParser(pydantic_object=DatabaseAnalysis)
        self.prompt = PromptTemplate(
            template="""Oracle AWR Analysis

Input:
- Report: {context}
- Question: {query}

{format_instructions}

Required Fields:

1. health_status (str):
   - Overall database health status
   - Must be one of: 'Critical', 'Warning', or 'Good'

2. summary (dict):
   - direct_answer: Brief, specific answer to the question
   - assessment: Technical analysis of the database state

3. key_metrics (dict):
   - Include relevant metrics with their values and trends
   - Example: {{"buffer_cache_hit_ratio": "95.2%", "disk_reads": "1.2K/s"}}

4. performance_impact (dict):
   - Current impact on database performance
   - Include resource utilization metrics
   - Example: {{"cpu_usage": "85%", "memory_pressure": "Medium"}}

5. recommendations (list):
   - List of dicts with 'fix' and 'benefit' keys
   - Example: [{{"fix": "Increase SGA size", "benefit": "Improved cache hit ratio"}}]

Guidelines:
• Format large numbers with K/M suffix (1.2K, 1.5M)
• Include units in all metric values
• Make recommendations specific and actionable""",
            input_variables=["context", "query"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()},
        )

    def initialize(self) -> None:
        """Initialize the analyzer by processing AWR report files"""
        if self.initialized:
            return

        try:
            docs = []
            for path in self.file_paths:
                docs.extend(self._load_and_split_document(path))
            
            self.vectorstore = FAISS.from_documents(docs, embeddings)
            self.initialized = True
            logger.info(f"Initialized analyzer with {len(docs)} document chunks")

        except Exception as e:
            logger.error(f"Initialization failed: {str(e)}")
            raise

    def _load_and_split_document(self, file_path: str) -> List:
        try:
            loader = BSHTMLLoader(file_path)
            documents = loader.load()

            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                separators=["\n\n", "\n", ". ", " ", ""]
            )
            return text_splitter.split_documents(documents)
        except Exception as e:
            logger.error(f"Failed to process document {file_path}: {str(e)}")
            raise

    def analyze(self, question: str) -> Dict[str, Any]:
        """Analyze the AWR report based on the question"""
        if not self.initialized:
            self.initialize()

        try:
            # Get relevant documents
            docs = self.vectorstore.similarity_search(question, k=3)
            context = "\n\n".join(doc.page_content for doc in docs)

            # Create the chain and invoke
            chain = self.prompt | llm | self.parser
            
            result = chain.invoke({
                "context": context,
                "query": question
            })
            
            # Validate the result is a DatabaseAnalysis instance
            if isinstance(result, dict):
                # Convert dict to DatabaseAnalysis object
                result = DatabaseAnalysis(**result)
            
            if not isinstance(result, DatabaseAnalysis):
                logger.error(f"Invalid result type: {type(result)}")
                return DatabaseAnalysis(
                    health_status="Medium",
                    summary={
                        "direct_answer": "Error in analysis",
                        "assessment": "The analysis produced an invalid response format."
                    },
                    key_metrics={
                        "error": "Analysis failed",
                        "status": "Invalid format"
                    },
                    performance_impact={
                        "status": "Unknown",
                        "details": "Analysis error"
                    },
                    recommendations=[{
                        "fix": "Retry the analysis",
                        "benefit": "Get valid analysis results"
                    }]
                ).model_dump()
                
            # Convert to dict for API response
            return result.model_dump()

        except Exception as e:
            error_msg = f"Error analyzing question: {str(e)}"
            logger.error(error_msg)
            return DatabaseAnalysis(
                health_status="Medium",
                summary={
                    "direct_answer": "Error in analysis",
                    "assessment": error_msg
                },
                key_metrics={
                    "error": "Analysis failed",
                    "status": str(e)
                },
                performance_impact={
                    "status": "Unknown",
                    "details": "Analysis error"
                },
                recommendations=[{
                    "fix": "Check logs and retry",
                    "benefit": "Resolve the analysis error"
                }]
            ).model_dump()

def create_ticket(health_status, analysis_result):
    logger.info('Attempting to create a ticket for health status: %s', health_status)
    logger.debug('Analysis result received: %s', json.dumps(analysis_result, indent=2))
    
    # Skip ticket creation for unknown health status
    if health_status.lower() == 'unknown':
        logger.info('No ticket created for health status: %s', health_status)
        return
        
    # Email configuration
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    sender_email = os.getenv("SMTP_USERNAME")
    receiver_email = os.getenv("RECIPIENT_EMAIL")
    password = os.getenv("SMTP_PASSWORD")

    # Debug email configuration
    logger.debug('Email Configuration:')
    logger.debug('- SMTP Server: %s', smtp_server)
    logger.debug('- Port: %s', port)
    logger.debug('- Sender Email: %s', sender_email)
    logger.debug('- Receiver Email: %s', receiver_email)
    logger.debug('- Password Present: %s', 'Yes' if password else 'No')

    if not all([smtp_server, port, sender_email, receiver_email, password]):
        logger.error('Missing email configuration:')
        logger.error('- SMTP Server present: %s', bool(smtp_server))
        logger.error('- Port present: %s', bool(port))
        logger.error('- Sender Email present: %s', bool(sender_email))
        logger.error('- Receiver Email present: %s', bool(receiver_email))
        logger.error('- Password present: %s', bool(password))
        return

    # Create message
    try:
        subject = f"Ticket Created: Health Status - {health_status}"
        message = f"Subject: {subject}\n\n"  
        message += f"A ticket has been created due to {health_status} health status.\n\n"
        
        # Safely access nested dictionary values with detailed logging
        try:
            logger.debug('Building email message content...')
            
            # Summary section
            summary = analysis_result.get('summary', {})
            direct_answer = summary.get('direct_answer', 'N/A')
            assessment = summary.get('assessment', 'N/A')
            logger.debug('Summary found - Direct Answer: %s, Assessment present: %s', 
                        bool(direct_answer != 'N/A'), bool(assessment != 'N/A'))
            
            # Key metrics section
            key_metrics = analysis_result.get('key_metrics', {})
            logger.debug('Key metrics found: %s', list(key_metrics.keys()))
            
            # Recommendations section
            recommendations = analysis_result.get('recommendations', [])
            logger.debug('Number of recommendations found: %d', len(recommendations))
            
            # Performance impact section
            performance_impact = analysis_result.get('performance_impact', {})
            logger.debug('Performance impact metrics found: %s', list(performance_impact.keys()))
            
            # Build message
            message += f"Summary: {direct_answer}\n"
            message += f"Key Metrics: {json.dumps(key_metrics, indent=2)}\n"
            message += f"Recommendations: {', '.join(rec.get('fix', 'N/A') for rec in recommendations)}\n"
            message += f"Performance Impact: {json.dumps(performance_impact, indent=2)}\n"
            message += f"Assessment: {assessment}\n"
            
            logger.debug('Email message built successfully')
            logger.debug('Message length: %d characters', len(message))
            
        except Exception as e:
            logger.error('Error formatting ticket message: %s', str(e))
            logger.error('Error details:', exc_info=True)
            message += "Error formatting complete analysis details.\n"

        # Send email with detailed logging
        logger.info('Attempting to send email...')
        try:
            context = ssl.create_default_context()
            logger.debug('SSL context created')
            
            with smtplib.SMTP(smtp_server, port) as server:
                logger.debug('SMTP connection established')
                
                server.starttls(context=context)
                logger.debug('TLS started successfully')
                
                server.login(sender_email, password)
                logger.debug('Login successful')
                
                server.sendmail(sender_email, receiver_email, message)
                logger.info('Email sent successfully to %s', receiver_email)
                
        except smtplib.SMTPAuthenticationError as e:
            logger.error('SMTP Authentication failed: %s', str(e))
            logger.error('Please check email credentials')
        except smtplib.SMTPException as e:
            logger.error('SMTP error occurred: %s', str(e))
            logger.error('Error details:', exc_info=True)
        except Exception as e:
            logger.error('Unexpected error during email sending: %s', str(e))
            logger.error('Error details:', exc_info=True)
            
    except Exception as e:
        logger.error('Failed to create ticket: %s', str(e))
        logger.error('Error details:', exc_info=True)

def create_analyzer(report_path: str) -> AWRAnalyzer:
    """Create an instance of AWRAnalyzer with the specified report path."""
    return AWRAnalyzer([report_path])

analyzer = create_analyzer("/Users/essayyzed/temp/dba-assistant/src/awr_reports/DB_SIZE_AWR_93.60/awrrpt_1_30954_30955.html")
