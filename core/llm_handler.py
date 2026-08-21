# llm_handler.py
"""
LLM Handler for ChatGPT (OpenAI GPT-5.1)
Handles SQL generation and insight generation for retail analytics system
"""
import os
from dotenv import load_dotenv
from openai import OpenAI
import json
import logging
import os
import re
import time
from pathlib import Path
print("Using OpenAI from:", OpenAI.__module__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) #set as env variable in .env file

# Model configuration
GPT_MODEL = "gpt-5.1"
MAX_TOKENS = 16384
REQUEST_TIMEOUT = 60

# Module-level caches (loaded once)
_SYSTEM_PROMPT = None
_EXAMPLES_TEXT = None


def _load_system_prompt():
    """Load and cache system prompt from file."""
    global _SYSTEM_PROMPT
    if _SYSTEM_PROMPT is None:
        try:
            prompt_path = Path("system_prompt.txt")
            with open(prompt_path, "r", encoding="utf-8") as f:
                _SYSTEM_PROMPT = f.read()
            logger.info("System prompt loaded and cached successfully")
        except Exception as e:
            logger.error(f"Failed to load system_prompt.txt: {e}")
            _SYSTEM_PROMPT = ""
    return _SYSTEM_PROMPT


def _load_and_format_examples():
    """Load and cache all examples."""
    global _EXAMPLES_TEXT
    if _EXAMPLES_TEXT is None:
        try:
            examples_path = Path("few_shot_examples.json")
            with open(examples_path, "r", encoding="utf-8") as f:
                examples = json.load(f)
            
            formatted_lines = ["=== SQL GENERATION EXAMPLES ===\n"]
            for i, ex in enumerate(examples, 1):
                formatted_lines.append(f"Example {i}:")
                formatted_lines.append(f"Query: {ex['query']}")
                formatted_lines.append(f"SQL: {ex['sql']}\n")
            
            _EXAMPLES_TEXT = "\n".join(formatted_lines)
            logger.info(f"Loaded and cached {len(examples)} SQL examples")
        except Exception as e:
            logger.error(f"Failed to load few_shot_examples.json: {e}")
            _EXAMPLES_TEXT = ""
    return _EXAMPLES_TEXT

def call_gpt(user_message, context="", use_system_prompt=True, include_examples=True):
    """
    Call OpenAI GPT for SQL or insight generation.
    """
    start_time = time.time()

    try:
        # Build system prompt
        system_content = None
        if use_system_prompt:
            system_content = _load_system_prompt()
            if not system_content:
                logger.warning("System prompt is empty")

        # Build user message
        message_parts = []

        if context:
            message_parts.append(context)
            message_parts.append("\n---\n")

        if include_examples:
            examples_text = _load_and_format_examples()
            if examples_text:
                message_parts.append(examples_text)
                message_parts.append("\n---\n")

        message_parts.append(user_message)
        final_message = "".join(message_parts)

        # Construct messages list
        messages = []
        if system_content:
            messages.append({"role": "system", "content": system_content})
        messages.append({"role": "user", "content": final_message})

        logger.info(f"Calling OpenAI model: {GPT_MODEL}")

        # NEW OpenAI SDK call
        response = client.responses.create(
            model=GPT_MODEL,
            input=messages,
            max_output_tokens=MAX_TOKENS,
            timeout=REQUEST_TIMEOUT
        )

        duration = time.time() - start_time

        # Log usage if present
        if hasattr(response, "usage"):
            logger.info(
                f"GPT call successful - "
                f"Prompt tokens: {response.usage.input_tokens}, "
                f"Output tokens: {response.usage.output_tokens}, "
                f"Duration: {duration:.2f}s"
            )

        # Extract output
        # Always extract text safely
            response_text = getattr(response, "output_text", None)

            # Case 1: If the model returned output_text, use it
            if response_text:
                return response_text.strip()

            # Fallback: If no output_text, use response.response_text or raw string
            response_text = getattr(response, "response_text", "") or str(response)

            # Case 2: Validate SQL only if query contains SELECT
            if "SELECT" in response_text.upper():
                response_text = _validate_sql_metrics(response_text, user_message)

            return response_text

        logger.warning("GPT API returned empty output")
        return "API call failed: Empty response"

    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"API call failed: {str(e)}"
        logger.error(
            f"GPT API error - "
            f"Error: {error_msg}, "
            f"Duration: {duration:.2f}s"
        )
        return error_msg
    
def _validate_sql_metrics(sql: str, user_query: str) -> str:
    """
    Validate that SQL doesn't add unnecessary metrics
    """
    user_lower = user_query.lower()
    
    # If user said "compare sales" or "show me sales", ensure no avg_sale or transaction_count
    if any(phrase in user_lower for phrase in ["compare sales", "show me sales", "sales by", "sales for"]):
        if "average" not in user_lower and "transaction" not in user_lower:
            # Remove avg_sale and transaction_count from SQL
            sql = re.sub(r',\s*ROUND\([^)]+\)\s+AS\s+avg_\w+', '', sql, flags=re.IGNORECASE)
            sql = re.sub(r',\s*COUNT\(DISTINCT\s+BILL_No\)\s+AS\s+transaction_count', '', sql, flags=re.IGNORECASE)
            logger.info("[VALIDATION] Removed unnecessary metrics from SQL")
    
    return sql