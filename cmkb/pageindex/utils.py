try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False
import openai
import requests
import json as json_module
import logging
import os
from datetime import datetime
import time
import json
import re
import PyPDF2
import copy
import asyncio
import pymupdf
from io import BytesIO
from dotenv import load_dotenv
load_dotenv()
import logging
import yaml
from pathlib import Path
from types import SimpleNamespace as config

# Initialize logger
logger = logging.getLogger(__name__)

# Import credential management system
from pageindex.credentials import (
    get_api_key,
    set_api_key,
    get_ollama_model,
    set_ollama_model,
    CredentialValidator
)

# Import prompt loader for registry-based prompts
from pageindex.prompt_loader import format_prompt_by_use_case

# Import response handlers for provider-agnostic finish reason handling
from pageindex.response_handlers import ResponseHandler, FinishReason

# Initialize API key using credential manager
# Maintains backward compatibility with CHATGPT_API_KEY constant
CHATGPT_API_KEY = get_api_key("openai")

# Initialize Ollama model from environment
# Used for selecting which Ollama model to use (e.g., "phi3:3.8b", "qwen2.5:14b", "llama3:8b")
OLLAMA_MODEL = get_ollama_model()

# Shared ThreadPoolExecutor for async Ollama calls
# Reused across all async operations to avoid per-call thread creation overhead
from concurrent.futures import ThreadPoolExecutor
_EXECUTOR = ThreadPoolExecutor(max_workers=3, thread_name_prefix="ollama_worker")

def get_effective_ollama_model(config_model: str = None) -> str:
    """
    Get the effective Ollama model to use.
    Priority: OLLAMA_MODEL environment variable > config > default
    
    Args:
        config_model: Model from config file (optional)
    
    Returns:
        Effective model name to use
    """
    # First priority: environment variable
    env_model = OLLAMA_MODEL
    if env_model:
        return env_model
    
    # Second priority: config file
    if config_model:
        return config_model
    
    # Fallback default
    return "mistral24b-16k"

def get_model_for_provider(provider: str = "ollama", config=None) -> str:
    """
    Get the appropriate model for the specified provider.
    
    Args:
        provider: Provider name ("openai" or "ollama")
        config: Optional config object with model settings
    
    Returns:
        Model name to use
    """
    if provider == "openai":
        # Use OpenAI model from config
        if config and hasattr(config, 'model'):
            return config.model
        return "mistral24b-16k"
    
    elif provider == "ollama":
        # Use Ollama model with priority: env > config > default
        if config and hasattr(config, 'ollama_model'):
            return get_effective_ollama_model(config.ollama_model)
        return get_effective_ollama_model()
    
    else:
        raise ValueError(f"Unknown provider: {provider}")

def validate_model_config(model: str, provider: str) -> bool:
    """
    Validate that a model exists and is compatible with the provider.
    
    Args:
        model: Model name
        provider: Provider name
    
    Returns:
        True if valid or unknown (permissive), False if explicit mismatch
    """
    try:
        from pageindex.model_capabilities import get_model_capabilities
        caps = get_model_capabilities(model)
        
        # If model is unknown (caps.provider == "unknown"), be permissive
        if caps.provider == "unknown":
            return True
        
        # Otherwise, validate that provider matches
        return caps.provider == provider
    except Exception as e:
        logger.warning(f"Could not validate model {model}: {e}")
        return True  # Allow unknown models to pass through

def count_tokens(text, model=None, provider=None):
    """
    Count tokens in text using provider-appropriate tokenization.
    
    Args:
        text: Text to count tokens for
        model: Model name (optional)
        provider: Provider name ("openai", "ollama", etc.) - auto-detected if None
    
    Returns:
        Estimated token count
    """
    if not text:
        return 0
    
    # Auto-detect provider if not specified
    if provider is None:
        provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    
    # Use OpenAI's tiktoken only for OpenAI provider with recognized models
    if provider == "openai" and HAS_TIKTOKEN and model:
        try:
            # Check if model is a known OpenAI model
            if model and ("gpt-" in model.lower() or "text-" in model.lower()):
                enc = tiktoken.encoding_for_model(model)
                tokens = enc.encode(text)
                return len(tokens)
        except Exception as e:
            logger.debug(f"Could not use tiktoken for model {model}: {e}")
            # Fall through to universal fallback
    
    # Universal fallback for Ollama and other providers
    # Most LLMs use roughly 1 token per 4 characters (conservative estimate)
    return len(text) // 4

def _call_openai_with_finish_reason(model, messages, api_key):
    """Call OpenAI API and extract finish reason"""
    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
    )
    
    content = response.choices[0].message.content
    raw_finish_reason = response.choices[0].finish_reason
    
    # Normalize finish reason
    normalized = ResponseHandler.normalize_finish_reason("openai", raw_finish_reason)
    finish_reason = normalized.value
    
    return content, finish_reason


def _validate_ollama_endpoint(ollama_url):
    """Validate Ollama endpoint is reachable"""
    try:
        response = requests.get(f"{ollama_url}/api/tags", timeout=5)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Ollama endpoint {ollama_url} not reachable: {e}")
        return False


def _call_ollama_with_finish_reason(model, messages, ollama_url=None):
    """Call Ollama API and extract finish reason with optimized timeout and error handling"""
    
    if ollama_url is None:
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    
    # Validate endpoint first
    if not _validate_ollama_endpoint(ollama_url):
        raise ConnectionError(f"Cannot connect to Ollama at {ollama_url}")
    
    url = f"{ollama_url}/api/chat"
    
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.0,
        }
    }
    
    try:
        # Use MUCH longer timeout for Ollama inference
        # Connect: 30s, Read: 600s (10 minutes for model inference)
        # Mistral 24B can take 60-120 seconds per request on RTX 4090
        response = requests.post(url, json=payload, timeout=(30, 600))
        response.raise_for_status()
        result = response.json()
        
        content = result.get('message', {}).get('content', '')
        
        # Ollama doesn't provide native finish_reason
        # Infer from response structure (incomplete JSON/text indicators)
        inferred_reason = _infer_ollama_finish_reason(content, model)
        
        return content, inferred_reason
    
    except requests.Timeout as e:
        logger.error(f"Ollama request timeout after 600s: {e}")
        raise ConnectionError(f"Ollama inference timeout (model inference very slow or overloaded): {e}")
    except requests.RequestException as e:
        logger.error(f"Ollama API error: {e}")
        raise


def _infer_ollama_finish_reason(content, model):
    """
    Infer finish reason from Ollama response.
    Detects if response appears incomplete based on structural indicators.
    """
    
    if not content:
        return "finished"

    # If we can extract parseable JSON from the response, treat it as complete.
    # This avoids false "max_output_reached" caused by heuristic quote/bracket checks.
    try:
        json_slice = _extract_likely_json_slice(content)
        if json_slice:
            json.loads(json_slice)
            return "finished"
    except Exception:
        pass
    
    # Check for incomplete JSON structure
    incomplete_indicators = [
        content.endswith(('{', '[', ',')),  # Ends with opening bracket or comma
        content.count('{') > content.count('}'),  # Unmatched braces
        content.count('[') > content.count(']'),  # Unmatched brackets
    ]
    
    # Check for incomplete string literal (ends with backslash or quote imbalance)
    quote_count = content.count('"') - content.count('\\"')
    if quote_count % 2 != 0:
        incomplete_indicators.append(True)
    
    if any(incomplete_indicators):
        return "max_output_reached"
    
    return "finished"


def Ollama_API_with_finish_reason(model, prompt, api_key=None, chat_history=None):
    """
    Provider-agnostic synchronous wrapper with finish reason detection.
    Supports both OpenAI and Ollama backends.
    
    Returns:
        Tuple[str, str]: (content, finish_reason)
            - finish_reason: "finished", "max_output_reached", or "error"
    """
    
    # Determine which provider to use
    config_provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    
    # Auto-resolve model based on provider if model doesn't match provider
    # This handles cases where opt.model (OpenAI model) is passed but provider is Ollama
    if config_provider == "ollama":
        # Check if model looks like an OpenAI model
        if "gpt-" in model.lower() or model.startswith("text-"):
            # Resolve to correct Ollama model
            resolved_model = get_effective_ollama_model()
            print(f"[MODEL AUTO-RESOLVE] {model} → {resolved_model}")
            logger.debug(f"Auto-resolved OpenAI model '{model}' to Ollama model '{resolved_model}'")
            model = resolved_model
        else:
            print(f"[MODEL DIRECT] Using: {model}")
    elif config_provider == "openai":
        # Check if model looks like an Ollama model  
        if not ("gpt-" in model.lower() or model.startswith("text-")):
            # For OpenAI, we don't auto-resolve; log warning
            logger.warning(f"Using Ollama-style model '{model}' with OpenAI provider (may fail)")
    
    # Build message list
    if chat_history:
        messages = list(chat_history) if isinstance(chat_history, list) else chat_history
        messages.append({"role": "user", "content": prompt})
    else:
        messages = [{"role": "user", "content": prompt}]
    
    # Reduce retries - Ollama inference with long timeout doesn't need many retries
    max_retries = 3 if config_provider == "ollama" else 5
    
    for attempt in range(max_retries):
        try:
            if config_provider == "openai":
                if api_key is None:
                    api_key = get_api_key("openai") or os.getenv("CHATGPT_API_KEY")
                content, finish_reason = _call_openai_with_finish_reason(model, messages, api_key)
                return content, finish_reason
            
            elif config_provider == "ollama":
                ollama_url = os.getenv("OLLAMA_URL")
                content, finish_reason = _call_ollama_with_finish_reason(model, messages, ollama_url)
                return content, finish_reason
            
            else:
                # Default to Ollama if unknown provider
                logger.warning(f"Unknown provider '{config_provider}', defaulting to Ollama")
                content, finish_reason = _call_ollama_with_finish_reason(model, messages, None)
                return content, finish_reason
        
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                # Longer backoff for Ollama to avoid hammering the inference engine
                wait_time = 3 if config_provider == "ollama" else 1
                time.sleep(wait_time)
            else:
                logger.error(f"Max retries ({max_retries}) reached for {config_provider}")
                return "Error", "error"



def Ollama_API(model, prompt, api_key=None, chat_history=None):
    """
    Provider-agnostic standard synchronous wrapper.
    Returns content only (no finish reason tracking).
    Supports both OpenAI and Ollama backends.
    
    Returns:
        str: Response content or "Error" on failure
    """
    
    content, finish_reason = Ollama_API_with_finish_reason(
        model=model,
        prompt=prompt,
        api_key=api_key,
        chat_history=chat_history
    )
    
    return content
            

async def Ollama_API_async(model, prompt, api_key=None):
    """
    Provider-agnostic asynchronous wrapper.
    Supports both OpenAI and Ollama backends with async/await.
    
    Returns:
        str: Response content or "Error" on failure
    """
    
    # Determine which provider to use
    config_provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    
    # Auto-resolve model based on provider if model doesn't match provider
    if config_provider == "ollama":
        if "gpt-" in model.lower() or model.startswith("text-"):
            resolved_model = get_effective_ollama_model()
            print(f"[MODEL AUTO-RESOLVE ASYNC] {model} → {resolved_model}")
            logger.debug(f"Auto-resolved OpenAI model '{model}' to Ollama model '{resolved_model}'")
            model = resolved_model
        else:
            print(f"[MODEL DIRECT ASYNC] Using: {model}")
    elif config_provider == "openai":
        if not ("gpt-" in model.lower() or model.startswith("text-")):
            logger.warning(f"Using Ollama-style model '{model}' with OpenAI provider (may fail)")
    
    messages = [{"role": "user", "content": prompt}]
    max_retries = 10
    
    if config_provider == "openai":
        # Use OpenAI's native async client
        if api_key is None:
            api_key = get_api_key("openai") or os.getenv("CHATGPT_API_KEY")
        
        for attempt in range(max_retries):
            try:
                async with openai.AsyncOpenAI(api_key=api_key) as client:
                    response = await client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=0,
                    )
                    return response.choices[0].message.content
            except Exception as e:
                logger.warning(f"OpenAI async attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                else:
                    logger.error(f"Max retries ({max_retries}) reached")
                    return "Error"
    
    else:
        # For Ollama, use sync call via shared executor (non-blocking)
        # This allows async code to call Ollama without blocking the event loop
        # Using shared _EXECUTOR to avoid per-call thread creation overhead
        loop = asyncio.get_event_loop()
        
        # Reduce retries for Ollama to 2 (each attempt has long timeout already)
        max_retries = 2
        
        for attempt in range(max_retries):
            try:
                # Run sync Ollama call in thread pool to avoid blocking
                content = await loop.run_in_executor(
                    _EXECUTOR,  # Use shared executor
                    lambda: _call_ollama_sync(model, messages)
                )
                return content
            except Exception as e:
                logger.warning(f"Ollama async attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                else:
                    logger.error(f"Max retries ({max_retries}) reached")
                    return "Error"


def _call_ollama_sync(model, messages, ollama_url=None):
    """Synchronous Ollama call (used by async wrapper via executor) with optimized timeout"""
    
    if ollama_url is None:
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    
    url = f"{ollama_url}/api/chat"
    
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.0,
        }
    }
    
    try:
        # Use much longer timeout for Ollama inference
        # Connect: 30s, Read: 600s (10 minutes for model inference)
        response = requests.post(url, json=payload, timeout=(30, 600))
        response.raise_for_status()
        result = response.json()
        
        content = result.get('message', {}).get('content', '')
        return content
    
    except requests.Timeout as e:
        logger.error(f"Ollama sync request timeout: {e}")
        raise ConnectionError(f"Ollama timeout (inference may be slow): {e}")
    except requests.RequestException as e:
        logger.error(f"Ollama sync API error: {e}")
        raise  
            
            
def get_json_content(response):
    if not response:
        return ""

    response = response.strip()

    if "```json" in response:
        start_idx = response.find("```json") + 7
        response = response[start_idx:]
    elif "```" in response:
        start_idx = response.find("```") + 3
        response = response[start_idx:]

    end_idx = response.rfind("```")
    if end_idx != -1:
        response = response[:end_idx]

    return response.strip()


def _extract_likely_json_slice(content):
    if not content:
        return ""

    cleaned = get_json_content(content)
    if cleaned:
        content = cleaned

    first_obj = content.find('{')
    first_arr = content.find('[')

    starts = [idx for idx in [first_obj, first_arr] if idx != -1]
    if not starts:
        return content.strip()

    start_idx = min(starts)
    end_obj = content.rfind('}')
    end_arr = content.rfind(']')
    end_idx = max(end_obj, end_arr)

    if end_idx == -1 or end_idx < start_idx:
        return content[start_idx:].strip()

    return content[start_idx:end_idx + 1].strip()


def _escape_invalid_backslashes(text: str) -> str:
    """Escape stray backslashes that would break JSON parsing."""
    if not text:
        return text
    return re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', text)


def _strip_invalid_backslash_escapes(text: str) -> str:
    """Drop invalid escape backslashes (e.g., '\\x' where x is not a JSON escape)."""
    if not text:
        return text
    return re.sub(r'\\([^"\\/bfnrtu])', r'\1', text)


def _extract_toc_items_fallback(text: str):
    """Best-effort TOC extraction from malformed JSON-like text."""
    if not text:
        return []

    pattern = re.compile(
        r'"title"\s*:\s*"([^\"]*(?:\\.[^\"]*)*)"\s*,\s*"page"\s*:\s*(null|-?\d+|"[^\"]*")',
        re.DOTALL,
    )

    items = []
    for title_raw, page_raw in pattern.findall(text):
        title = title_raw.replace('\\"', '"').replace('\\\\', '\\').strip()

        if page_raw == 'null':
            page = None
        else:
            page_candidate = page_raw.strip('"').strip()
            page = int(page_candidate) if page_candidate.isdigit() else None

        items.append({"title": title, "page": page})

    return items


def extract_json(content):
    try:
        json_content = _extract_likely_json_slice(content)

        json_content = json_content.replace('None', 'null')
        json_content = json_content.replace(',]', ']').replace(',}', '}')
        json_content = _escape_invalid_backslashes(json_content)

        try:
            return json.loads(json_content)
        except json.JSONDecodeError as e:
            # Check if it's an "Extra data" error - try to extract just the first complete JSON
            if "Extra data" in str(e):
                # Find the position where the first valid JSON ends
                decoder = json.JSONDecoder()
                try:
                    obj, idx = decoder.raw_decode(json_content)
                    logging.warning(f"Extracted first valid JSON object, ignoring {len(json_content) - idx} extra chars")
                    return obj
                except:
                    pass
            # Fall through to retry with compact format
            pass

        compact_json = ' '.join(json_content.replace('\r', ' ').replace('\n', ' ').split())
        compact_json = compact_json.replace(',]', ']').replace(',}', '}')
        compact_json = _escape_invalid_backslashes(compact_json)
        
        try:
            return json.loads(compact_json)
        except json.JSONDecodeError as e:
            repaired_json = _strip_invalid_backslash_escapes(compact_json)
            try:
                return json.loads(repaired_json)
            except json.JSONDecodeError:
                pass

            # Try one more time with raw_decode to get first valid object
            if "Extra data" in str(e):
                decoder = json.JSONDecoder()
                try:
                    obj, idx = decoder.raw_decode(compact_json)
                    logging.warning(f"Extracted first valid JSON from compact, ignoring extra data")
                    return obj
                except:
                    pass
            raise

    except json.JSONDecodeError as e:
        logging.error(f"Failed to extract JSON: {e}")
        logging.error(f"Content that failed to parse: {str(content)[:300]}")
        likely = _extract_likely_json_slice(str(content))

        fallback_items = _extract_toc_items_fallback(likely)
        if fallback_items:
            logging.warning(f"Recovered {len(fallback_items)} TOC items using tolerant parser")
            return {"table_of_contents": fallback_items}

        if likely.strip().startswith('['):
            return []
        return {}
    except Exception as e:
        logging.error(f"Unexpected error while extracting JSON: {e}")
        return {}

def extract_json_with_pydantic(content: str, model_class=None):
    """
    Extract and validate JSON using Pydantic model.
    More strict than extract_json - enforces schema compliance.
    
    Args:
        content: Raw response text from model
        model_class: Pydantic BaseModel class for validation
    
    Returns:
        Validated model instance or None if invalid
    """
    if not model_class:
        return extract_json(content)
    
    try:
        from pageindex.models import validate_and_parse_json
        
        # Extract JSON slice first
        json_content = _extract_likely_json_slice(content)
        json_content = json_content.replace('None', 'null')
        json_content = json_content.replace(',]', ']').replace(',}', '}')
        json_content = _escape_invalid_backslashes(json_content)
        
        # Try direct parse with validation
        try:
            result = validate_and_parse_json(json_content, model_class)
            if result:
                logging.info(f"✓ JSON validated against {model_class.__name__}")
                return result
        except:
            pass
        
        # Try compact format
        compact_json = ' '.join(json_content.replace('\r', ' ').replace('\n', ' ').split())
        compact_json = compact_json.replace(',]', ']').replace(',}', '}')
        compact_json = _escape_invalid_backslashes(compact_json)
        
        result = validate_and_parse_json(compact_json, model_class)
        if result:
            logging.info(f"✓ JSON validated (compact) against {model_class.__name__}")
            return result

        repaired_json = _strip_invalid_backslash_escapes(compact_json)
        result = validate_and_parse_json(repaired_json, model_class)
        if result:
            logging.info(f"✓ JSON validated (repaired) against {model_class.__name__}")
            return result
        
        # Try raw_decode for partial JSON
        try:
            decoder = json.JSONDecoder()
            obj, idx = decoder.raw_decode(json_content)
            # Try to construct model from partial object
            result = validate_and_parse_json(json.dumps(obj), model_class)
            if result:
                logging.warning(f"Extracted partial JSON, validated against {model_class.__name__}")
                return result
        except:
            pass
        
        logging.error(f"Failed to validate JSON against {model_class.__name__}")
        return None
        
    except ImportError:
        # Fallback if Pydantic models not available
        return extract_json(content)
    except Exception as e:
        logging.error(f"Error in extract_json_with_pydantic: {e}")
        return None


def write_node_id(data, node_id=0):
    if isinstance(data, dict):
        data['node_id'] = str(node_id).zfill(4)
        node_id += 1
        for key in list(data.keys()):
            if 'nodes' in key:
                node_id = write_node_id(data[key], node_id)
    elif isinstance(data, list):
        for index in range(len(data)):
            node_id = write_node_id(data[index], node_id)
    return node_id

def get_nodes(structure):
    if isinstance(structure, dict):
        structure_node = copy.deepcopy(structure)
        structure_node.pop('nodes', None)
        nodes = [structure_node]
        for key in list(structure.keys()):
            if 'nodes' in key:
                nested_nodes = get_nodes(structure[key])
                if nested_nodes:  # Only extend if we got a valid list
                    nodes.extend(nested_nodes)
        return nodes
    elif isinstance(structure, list):
        nodes = []
        for item in structure:
            nested_nodes = get_nodes(item)
            if nested_nodes:  # Only extend if we got a valid list
                nodes.extend(nested_nodes)
        return nodes
    else:
        # Fallback: return empty list instead of None
        return []
    
def structure_to_list(structure):
    if isinstance(structure, dict):
        nodes = []
        nodes.append(structure)
        if 'nodes' in structure:
            nested_nodes = structure_to_list(structure['nodes'])
            if nested_nodes:  # Only extend if we got a valid list
                nodes.extend(nested_nodes)
        return nodes
    elif isinstance(structure, list):
        nodes = []
        for item in structure:
            nested_nodes = structure_to_list(item)
            if nested_nodes:  # Only extend if we got a valid list
                nodes.extend(nested_nodes)
        return nodes
    else:
        # Fallback: return empty list instead of None
        return []

    
def get_leaf_nodes(structure):
    if isinstance(structure, dict):
        if not structure.get('nodes'):
            structure_node = copy.deepcopy(structure)
            structure_node.pop('nodes', None)
            return [structure_node]
        else:
            leaf_nodes = []
            for key in list(structure.keys()):
                if 'nodes' in key:
                    nested_leaf_nodes = get_leaf_nodes(structure[key])
                    if nested_leaf_nodes:  # Only extend if we got a valid list
                        leaf_nodes.extend(nested_leaf_nodes)
            return leaf_nodes
    elif isinstance(structure, list):
        leaf_nodes = []
        for item in structure:
            nested_leaf_nodes = get_leaf_nodes(item)
            if nested_leaf_nodes:  # Only extend if we got a valid list
                leaf_nodes.extend(nested_leaf_nodes)
        return leaf_nodes
    else:
        # Fallback: return empty list instead of None
        return []

def is_leaf_node(data, node_id):
    # Helper function to find the node by its node_id
    def find_node(data, node_id):
        if isinstance(data, dict):
            if data.get('node_id') == node_id:
                return data
            for key in data.keys():
                if 'nodes' in key:
                    result = find_node(data[key], node_id)
                    if result:
                        return result
        elif isinstance(data, list):
            for item in data:
                result = find_node(item, node_id)
                if result:
                    return result
        return None

    # Find the node with the given node_id
    node = find_node(data, node_id)

    # Check if the node is a leaf node
    if node and not node.get('nodes'):
        return True
    return False

def get_last_node(structure):
    return structure[-1]


def extract_text_from_pdf(pdf_path):
    pdf_reader = PyPDF2.PdfReader(pdf_path)
    ###return text not list 
    text=""
    for page_num in range(len(pdf_reader.pages)):
        page = pdf_reader.pages[page_num]
        text+=page.extract_text()
    return text

def get_pdf_title(pdf_path):
    pdf_reader = PyPDF2.PdfReader(pdf_path)
    meta = pdf_reader.metadata
    title = meta.title if meta and meta.title else 'Untitled'
    return title

def get_text_of_pages(pdf_path, start_page, end_page, tag=True):
    pdf_reader = PyPDF2.PdfReader(pdf_path)
    text = ""
    for page_num in range(start_page-1, end_page):
        page = pdf_reader.pages[page_num]
        page_text = page.extract_text()
        if tag:
            text += f"<start_index_{page_num+1}>\n{page_text}\n<end_index_{page_num+1}>\n"
        else:
            text += page_text
    return text

def get_first_start_page_from_text(text):
    start_page = -1
    start_page_match = re.search(r'<start_index_(\d+)>', text)
    if start_page_match:
        start_page = int(start_page_match.group(1))
    return start_page

def get_last_start_page_from_text(text):
    start_page = -1
    # Find all matches of start_index tags
    start_page_matches = re.finditer(r'<start_index_(\d+)>', text)
    # Convert iterator to list and get the last match if any exist
    matches_list = list(start_page_matches)
    if matches_list:
        start_page = int(matches_list[-1].group(1))
    return start_page


def sanitize_filename(filename, replacement='-'):
    # In Linux, only '/' and '\0' (null) are invalid in filenames.
    # Null can't be represented in strings, so we only handle '/'.
    return filename.replace('/', replacement)

def get_pdf_name(pdf_path):
    # Extract PDF name
    if isinstance(pdf_path, str):
        pdf_name = os.path.basename(pdf_path)
    elif isinstance(pdf_path, BytesIO):
        pdf_reader = PyPDF2.PdfReader(pdf_path)
        meta = pdf_reader.metadata
        pdf_name = meta.title if meta and meta.title else 'Untitled'
        pdf_name = sanitize_filename(pdf_name)
    return pdf_name


class JsonLogger:
    def __init__(self, file_path):
        # Extract PDF name for logger name
        pdf_name = get_pdf_name(file_path)
            
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filename = f"{pdf_name}_{current_time}.json"
        os.makedirs("./logs", exist_ok=True)
        # Initialize empty list to store all messages
        self.log_data = []

    def log(self, level, message, **kwargs):
        if isinstance(message, dict):
            self.log_data.append(message)
        else:
            self.log_data.append({'message': message})
        # Add new message to the log data
        
        # Write entire log data to file
        with open(self._filepath(), "w") as f:
            json.dump(self.log_data, f, indent=2)

    def info(self, message, **kwargs):
        self.log("INFO", message, **kwargs)

    def error(self, message, **kwargs):
        self.log("ERROR", message, **kwargs)

    def debug(self, message, **kwargs):
        self.log("DEBUG", message, **kwargs)

    def exception(self, message, **kwargs):
        kwargs["exception"] = True
        self.log("ERROR", message, **kwargs)

    def _filepath(self):
        return os.path.join("logs", self.filename)
    



def list_to_tree(data):
    def get_parent_structure(structure):
        """Helper function to get the parent structure code"""
        if not structure:
            return None
        parts = str(structure).split('.')
        return '.'.join(parts[:-1]) if len(parts) > 1 else None
    
    # First pass: Create nodes and track parent-child relationships
    nodes = {}
    root_nodes = []
    
    for item in data:
        structure = item.get('structure')
        node = {
            'title': item.get('title'),
            'start_index': item.get('start_index'),
            'end_index': item.get('end_index'),
            'nodes': []
        }
        
        nodes[structure] = node
        
        # Find parent
        parent_structure = get_parent_structure(structure)
        
        if parent_structure:
            # Add as child to parent if parent exists
            if parent_structure in nodes:
                nodes[parent_structure]['nodes'].append(node)
            else:
                root_nodes.append(node)
        else:
            # No parent, this is a root node
            root_nodes.append(node)
    
    # Helper function to clean empty children arrays
    def clean_node(node):
        if not node['nodes']:
            del node['nodes']
        else:
            for child in node['nodes']:
                clean_node(child)
        return node
    
    # Clean and return the tree
    return [clean_node(node) for node in root_nodes]

def add_preface_if_needed(data):
    if not isinstance(data, list) or not data:
        return data

    if data[0]['physical_index'] is not None and data[0]['physical_index'] > 1:
        preface_node = {
            "structure": "0",
            "title": "Preface",
            "physical_index": 1,
        }
        data.insert(0, preface_node)
    return data



def get_page_tokens(pdf_path, model="mistral24b-16k", pdf_parser="PyPDF2"):
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    
    # Only use tiktoken for OpenAI models
    if HAS_TIKTOKEN and provider == "openai" and model and ("gpt-" in model.lower() or "text-" in model.lower()):
        try:
            enc = tiktoken.encoding_for_model(model)
            encode_fn = lambda text: len(enc.encode(text))
        except Exception as e:
            logger.debug(f"Could not use tiktoken for model {model}: {e}")
            # Fallback to estimation
            encode_fn = lambda text: len(text) // 4
    else:
        # Fallback: simple estimation for Ollama and other providers
        encode_fn = lambda text: len(text) // 4
    
    if pdf_parser == "PyPDF2":
        pdf_reader = PyPDF2.PdfReader(pdf_path)
        page_list = []
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            page_text = page.extract_text()
            token_length = encode_fn(page_text)
            page_list.append((page_text, token_length))
        return page_list
    elif pdf_parser == "PyMuPDF":
        if isinstance(pdf_path, BytesIO):
            pdf_stream = pdf_path
            doc = pymupdf.open(stream=pdf_stream, filetype="pdf")
        elif isinstance(pdf_path, str) and os.path.isfile(pdf_path) and pdf_path.lower().endswith(".pdf"):
            doc = pymupdf.open(pdf_path)
        page_list = []
        for page in doc:
            page_text = page.get_text()
            token_length = encode_fn(page_text)
            page_list.append((page_text, token_length))
        return page_list
    else:
        raise ValueError(f"Unsupported PDF parser: {pdf_parser}")

        

def get_text_of_pdf_pages(pdf_pages, start_page, end_page):
    text = ""
    # Add boundary checks
    start_page = max(1, start_page)
    end_page = min(len(pdf_pages), end_page)
    if start_page > end_page or start_page < 1:
        return ""
    for page_num in range(start_page-1, end_page):
        text += pdf_pages[page_num][0]
    return text

def get_text_of_pdf_pages_with_labels(pdf_pages, start_page, end_page):
    text = ""
    # Add boundary checks
    start_page = max(1, start_page)
    end_page = min(len(pdf_pages), end_page)
    if start_page > end_page or start_page < 1:
        return ""
    for page_num in range(start_page-1, end_page):
        text += f"<physical_index_{page_num+1}>\n{pdf_pages[page_num][0]}\n<physical_index_{page_num+1}>\n"
    return text

def get_number_of_pages(pdf_path):
    pdf_reader = PyPDF2.PdfReader(pdf_path)
    num = len(pdf_reader.pages)
    return num



def post_processing(structure, end_physical_index):
    # First convert page_number to start_index in flat list
    for i, item in enumerate(structure):
        item['start_index'] = item.get('physical_index')
        if i < len(structure) - 1:
            if structure[i + 1].get('appear_start') == 'yes':
                item['end_index'] = structure[i + 1]['physical_index']-1
            else:
                item['end_index'] = structure[i + 1]['physical_index']
        else:
            item['end_index'] = end_physical_index
    tree = list_to_tree(structure)
    if len(tree)!=0:
        return tree
    else:
        ### remove appear_start 
        for node in structure:
            node.pop('appear_start', None)
            node.pop('physical_index', None)
        return structure

def clean_structure_post(data):
    if isinstance(data, dict):
        data.pop('page_number', None)
        data.pop('start_index', None)
        data.pop('end_index', None)
        if 'nodes' in data:
            clean_structure_post(data['nodes'])
    elif isinstance(data, list):
        for section in data:
            clean_structure_post(section)
    return data

def remove_fields(data, fields=['text']):
    if isinstance(data, dict):
        return {k: remove_fields(v, fields)
            for k, v in data.items() if k not in fields}
    elif isinstance(data, list):
        return [remove_fields(item, fields) for item in data]
    return data

def print_toc(tree, indent=0):
    for node in tree:
        print('  ' * indent + node['title'])
        if node.get('nodes'):
            print_toc(node['nodes'], indent + 1)

def print_json(data, max_len=40, indent=2):
    def simplify_data(obj):
        if isinstance(obj, dict):
            return {k: simplify_data(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [simplify_data(item) for item in obj]
        elif isinstance(obj, str) and len(obj) > max_len:
            return obj[:max_len] + '...'
        else:
            return obj
    
    simplified = simplify_data(data)
    print(json.dumps(simplified, indent=indent, ensure_ascii=False))


def remove_structure_text(data):
    if isinstance(data, dict):
        data.pop('text', None)
        if 'nodes' in data:
            remove_structure_text(data['nodes'])
    elif isinstance(data, list):
        for item in data:
            remove_structure_text(item)
    return data


def check_token_limit(structure, limit=110000):
    list = structure_to_list(structure)
    for node in list:
        num_tokens = count_tokens(node['text'], model='gpt-4o')
        if num_tokens > limit:
            print(f"Node ID: {node['node_id']} has {num_tokens} tokens")
            print("Start Index:", node['start_index'])
            print("End Index:", node['end_index'])
            print("Title:", node['title'])
            print("\n")


def convert_physical_index_to_int(data):
    if isinstance(data, list):
        for i in range(len(data)):
            # Check if item is a dictionary and has 'physical_index' key
            if isinstance(data[i], dict) and 'physical_index' in data[i]:
                if isinstance(data[i]['physical_index'], str):
                    if data[i]['physical_index'].startswith('<physical_index_'):
                        data[i]['physical_index'] = int(data[i]['physical_index'].split('_')[-1].rstrip('>').strip())
                    elif data[i]['physical_index'].startswith('physical_index_'):
                        data[i]['physical_index'] = int(data[i]['physical_index'].split('_')[-1].strip())
    elif isinstance(data, str):
        if data.startswith('<physical_index_'):
            data = int(data.split('_')[-1].rstrip('>').strip())
        elif data.startswith('physical_index_'):
            data = int(data.split('_')[-1].strip())
        # Check data is int
        if isinstance(data, int):
            return data
        else:
            return None
    return data


def convert_page_to_int(data):
    for item in data:
        if 'page' in item and isinstance(item['page'], str):
            try:
                item['page'] = int(item['page'])
            except ValueError:
                # Keep original value if conversion fails
                pass
    return data


def add_node_text(node, pdf_pages):
    if isinstance(node, dict):
        start_page = node.get('start_index')
        end_page = node.get('end_index')
        node['text'] = get_text_of_pdf_pages(pdf_pages, start_page, end_page)
        if 'nodes' in node:
            add_node_text(node['nodes'], pdf_pages)
    elif isinstance(node, list):
        for index in range(len(node)):
            add_node_text(node[index], pdf_pages)
    return


def add_node_text_with_labels(node, pdf_pages):
    if isinstance(node, dict):
        start_page = node.get('start_index')
        end_page = node.get('end_index')
        node['text'] = get_text_of_pdf_pages_with_labels(pdf_pages, start_page, end_page)
        if 'nodes' in node:
            add_node_text_with_labels(node['nodes'], pdf_pages)
    elif isinstance(node, list):
        for index in range(len(node)):
            add_node_text_with_labels(node[index], pdf_pages)
    return


async def generate_node_summary(node, model=None):
    prompt = format_prompt_by_use_case('metadata.node_summary', text=node['text'])
    response = await Ollama_API_async(model, prompt)
    return response


async def generate_summaries_for_structure(structure, model=None):
    nodes = structure_to_list(structure)
    
    # Handle empty structure case
    if not nodes:
        return structure
    
    # Use higher concurrency for summary generation - RTX 4090 can handle 3-4 concurrent inferences
    # mistral24b-16k (24B) uses ~18GB VRAM on RTX 4090, leaving headroom for multiple requests
    # Using Semaphore(3) for safe parallel processing - avoids rate limiting and race conditions
    semaphore = asyncio.Semaphore(3)
    
    async def limited_summary(node):
        async with semaphore:
            return await generate_node_summary(node, model=model)
    
    tasks = [limited_summary(node) for node in nodes]
    summaries = await asyncio.gather(*tasks)
    
    for node, summary in zip(nodes, summaries):
        if isinstance(node, dict):  # Safety check
            node['summary'] = summary
    return structure


def create_clean_structure_for_description(structure):
    """
    Create a clean structure for document description generation,
    excluding unnecessary fields like 'text'.
    """
    if isinstance(structure, dict):
        clean_node = {}
        # Only include essential fields for description
        for key in ['title', 'node_id', 'summary', 'prefix_summary']:
            if key in structure:
                clean_node[key] = structure[key]
        
        # Recursively process child nodes
        if 'nodes' in structure and structure['nodes']:
            clean_node['nodes'] = create_clean_structure_for_description(structure['nodes'])
        
        return clean_node
    elif isinstance(structure, list):
        return [create_clean_structure_for_description(item) for item in structure]
    else:
        return structure


def generate_doc_description(structure, model=None):
    prompt = format_prompt_by_use_case('metadata.doc_description', structure=str(structure))
    response = Ollama_API(model, prompt)
    return response


def reorder_dict(data, key_order):
    if not key_order:
        return data
    return {key: data[key] for key in key_order if key in data}


def format_structure(structure, order=None):
    if not order:
        return structure
    if isinstance(structure, dict):
        if 'nodes' in structure:
            structure['nodes'] = format_structure(structure['nodes'], order)
        if not structure.get('nodes'):
            structure.pop('nodes', None)
        structure = reorder_dict(structure, order)
    elif isinstance(structure, list):
        structure = [format_structure(item, order) for item in structure]
    return structure


class ConfigLoader:
    def __init__(self, default_path: str = None):
        if default_path is None:
            default_path = Path(__file__).parent / "config.yaml"
        self._default_dict = self._load_yaml(default_path)

    @staticmethod
    def _load_yaml(path):
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _validate_keys(self, user_dict):
        unknown_keys = set(user_dict) - set(self._default_dict)
        if unknown_keys:
            raise ValueError(f"Unknown config keys: {unknown_keys}")

    def load(self, user_opt=None) -> config:
        """
        Load the configuration, merging user options with default values.
        """
        if user_opt is None:
            user_dict = {}
        elif isinstance(user_opt, config):
            user_dict = vars(user_opt)
        elif isinstance(user_opt, dict):
            user_dict = user_opt
        else:
            raise TypeError("user_opt must be dict, config(SimpleNamespace) or None")

        self._validate_keys(user_dict)
        merged = {**self._default_dict, **user_dict}
        return config(**merged)