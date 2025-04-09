# Database Health Analyzer

A Python-based tool for analyzing Oracle Automatic Workload Repository (AWR) reports using LangChain and AI to provide intelligent database health assessments and recommendations.

## Features

- Automated analysis of Oracle AWR reports
- AI-powered database health assessment
- Key metrics extraction and trend analysis
- Performance impact evaluation
- Actionable recommendations
- Email notification system for critical issues

## Requirements

- Python 3.x
- OpenAI API key
- Required Python packages (install via `pip`):
  - langchain
  - langchain-openai
  - pydantic
  - python-dotenv
  - faiss-cpu
  - beautifulsoup4

## Setup

1. Clone the repository
2. Create a `.env` file in the project root with the following variables:
   ```
   OPENAI_API_KEY=your_api_key
   SMTP_USERNAME=your_smtp_username
   SMTP_PASSWORD=your_smtp_password
   RECIPIENT_EMAIL=your_email
   ```

## Usage

```python
from main import create_analyzer

# Initialize the analyzer with an AWR report
analyzer = create_analyzer("path/to/your/awr_report.html")

# Analyze the database health
analysis = analyzer.analyze("What is the overall database health status?")
```

## Output Format

The analysis results include:
- Overall health status (Critical/Warning/Good)
- Summary with direct answers and technical assessment
- Key database metrics and trends
- Performance impact analysis
- Actionable recommendations

## Features

- **Intelligent Analysis**: Uses LangChain and GPT-4 for comprehensive AWR report analysis
- **Vector Search**: Implements FAISS for efficient document searching
- **Automated Alerts**: Email notifications for critical database issues
- **Detailed Logging**: Comprehensive logging system for troubleshooting

## Contributing

Feel free to submit issues and pull requests.

## License

[Add your license information here]
