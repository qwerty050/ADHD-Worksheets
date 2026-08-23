import os
import json
import copy
import math
import random
import re
import asyncio
from .utils import *
from .prompt_loader import format_prompt_by_use_case
from .chunking_config import get_chunking_config_for_model
import os
from concurrent.futures import ThreadPoolExecutor, as_completed


################### check title in page #########################################################
async def check_title_appearance(item, page_list, start_index=1, model=None):    
    title=item['title']
    if 'physical_index' not in item or item['physical_index'] is None:
        return {'list_index': item.get('list_index'), 'answer': 'no', 'title':title, 'page_number': None}
    # Using Semaphore(3) for efficient parallel processing
    semaphore = asyncio.Semaphore(3)
    
    page_number = item['physical_index']
    # Add boundary check to prevent index out of range
    page_idx = page_number - start_index
    if page_idx < 0 or page_idx >= len(page_list):
        return {'list_index': item.get('list_index'), 'answer': 'no', 'title': title, 'page_number': None}
    page_text = page_list[page_idx][0]

    prompt = format_prompt_by_use_case(
        "toc.check_title_appearance",
        title=title,
        page_text=page_text
    )

    response = await Ollama_API_async(model=model, prompt=prompt)
    response = extract_json(response)
    if 'answer' in response:
        answer = response['answer']
    else:
        answer = 'no'
    return {'list_index': item['list_index'], 'answer': answer, 'title': title, 'page_number': page_number}


async def check_title_appearance_in_start(title, page_text, model=None, logger=None):    
    prompt = format_prompt_by_use_case(
        "toc.check_title_start",
        title=title,
        page_text=page_text
    )

    response = await Ollama_API_async(model=model, prompt=prompt)
    response = extract_json(response)
    if logger:
        logger.info(f"Response: {response}")
    return response.get("start_begin", "no")


async def check_title_appearance_in_start_concurrent(structure, page_list, model=None, logger=None):
    if logger:
        logger.info("Checking title appearance in start concurrently (with concurrency limit)")
    
    # skip items without physical_index
    for item in structure:
        if item.get('physical_index') is None:
            item['appear_start'] = 'no'

    # only for items with valid physical_index
    # Use a semaphore to limit concurrent requests to 3 (controlled parallelism)
    semaphore = asyncio.Semaphore(3)
    
    async def limited_check(item, page_text):
        async with semaphore:
            return await check_title_appearance_in_start(item['title'], page_text, model=model, logger=logger)
    
    tasks = []
    valid_items = []
    for item in structure:
        if item.get('physical_index') is not None:
            page_idx = item['physical_index'] - 1
            if page_idx < 0 or page_idx >= len(page_list):
                item['appear_start'] = 'no'
                continue
            page_text = page_list[page_idx][0]
            tasks.append(limited_check(item, page_text))
            valid_items.append(item)

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for item, result in zip(valid_items, results):
        if isinstance(result, Exception):
            if logger:
                logger.error(f"Error checking start for {item['title']}: {result}")
            item['appear_start'] = 'no'
        else:
            item['appear_start'] = result

    return structure


def toc_detector_single_page(content, model=None):
    prompt = format_prompt_by_use_case(
        "toc.detect_single_page",
        text=content
    )

    response = Ollama_API(model=model, prompt=prompt)
    # print('response', response)
    json_content = extract_json(response)
    return json_content.get('toc_detected', 'no')


async def toc_detector_single_page_async(content, model=None):
    """Async version of TOC detector for parallel processing"""
    prompt = format_prompt_by_use_case(
        "toc.detect_single_page",
        text=content
    )

    response = await Ollama_API_async(model=model, prompt=prompt)
    json_content = extract_json(response)
    return json_content.get('toc_detected', 'no')


def check_if_toc_extraction_is_complete(content, toc, model=None):
    prompt = format_prompt_by_use_case(
        "toc.check_extraction_complete",
        content=content,
        toc=toc
    )
    response = Ollama_API(model=model, prompt=prompt)
    json_content = extract_json(response)
    return json_content.get('completed', 'no')


def check_if_toc_transformation_is_complete(content, toc, model=None):
    prompt = format_prompt_by_use_case(
        "toc.check_transformation_complete",
        content=content,
        toc=toc
    )
    response = Ollama_API(model=model, prompt=prompt)
    json_content = extract_json(response)
    return json_content.get('completed', 'no')

def extract_toc_content(content, model=None):
    prompt = format_prompt_by_use_case(
        "toc.extract_content_init",
        content=content
    )

    response, finish_reason = Ollama_API_with_finish_reason(model=model, prompt=prompt)
    
    if_complete = check_if_toc_transformation_is_complete(content, response, model)
    if if_complete == "yes" and finish_reason == "finished":
        return response
    
    chat_history = [
        {"role": "user", "content": prompt}, 
        {"role": "assistant", "content": response},    
    ]
    prompt = format_prompt_by_use_case("toc.extract_content_continue")
    new_response, finish_reason = Ollama_API_with_finish_reason(model=model, prompt=prompt, chat_history=chat_history)
    response = response + new_response
    if_complete = check_if_toc_transformation_is_complete(content, response, model)

    max_retries = 5
    retries = 0
    while not (if_complete == "yes" and finish_reason == "finished"):
        chat_history = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": response},
        ]
        prompt = format_prompt_by_use_case("toc.extract_content_continue")
        new_response, finish_reason = Ollama_API_with_finish_reason(model=model, prompt=prompt, chat_history=chat_history)
        response = response + new_response
        if_complete = check_if_toc_transformation_is_complete(content, response, model)

        retries += 1
        if retries >= max_retries:
            raise Exception('Failed to complete table of contents after maximum retries')

    return response

def detect_page_index(toc_content, model=None):
    print('start detect_page_index')
    prompt = format_prompt_by_use_case(
        "toc.detect_page_index",
        toc_content=toc_content
    )

    response = Ollama_API(model=model, prompt=prompt)
    json_content = extract_json(response)
    return json_content.get('page_index_given_in_toc', 'no')

def toc_extractor(page_list, toc_page_list, model):
    def transform_dots_to_colon(text):
        text = re.sub(r'\.{5,}', ': ', text)
        # Handle dots separated by spaces
        text = re.sub(r'(?:\. ){5,}\.?', ': ', text)
        return text
    
    toc_content = ""
    for page_index in toc_page_list:
        toc_content += page_list[page_index][0]
    toc_content = transform_dots_to_colon(toc_content)
    has_page_index = detect_page_index(toc_content, model=model)
    
    return {
        "toc_content": toc_content,
        "page_index_given_in_toc": has_page_index
    }




def toc_index_extractor(toc, content, model=None):
    print('start toc_index_extractor')
    from pageindex.prompt_loader import format_prompt_by_use_case
    
    prompt = format_prompt_by_use_case('toc.index_extractor', toc=str(toc), content=content)
    response = Ollama_API(model=model, prompt=prompt)
    json_content = extract_json(response)
    return json_content if isinstance(json_content, list) else []



def _toc_transformer_single(toc_content, model=None):
    """Transform a single TOC chunk that fits within token limits"""
    from pageindex.prompt_loader import format_prompt_by_use_case

    def _parse_toc_payload(payload):
        parsed = extract_json(payload)
        if isinstance(parsed, dict):
            return convert_page_to_int(parsed.get('table_of_contents', []))
        if isinstance(parsed, list):
            return convert_page_to_int(parsed)
        return []

    prompt = format_prompt_by_use_case('toc.transformer_init', toc_content=toc_content)
    last_complete, finish_reason = Ollama_API_with_finish_reason(model=model, prompt=prompt)

    initial_items = _parse_toc_payload(last_complete)
    if initial_items:
        return initial_items

    if_complete = check_if_toc_transformation_is_complete(toc_content, last_complete, model)

    if if_complete == "yes" and finish_reason == "finished":
        return _parse_toc_payload(last_complete)

    last_complete = get_json_content(last_complete)
    loop_count = 0
    while not (if_complete == "yes" and finish_reason == "finished"):
        loop_count += 1

        if loop_count > 5:
            break

        position = last_complete.rfind('}')
        if position != -1:
            last_complete = last_complete[:position+1]

        prompt = format_prompt_by_use_case('toc.transformer_continue', toc_content=toc_content, last_complete=last_complete)
        new_complete, finish_reason = Ollama_API_with_finish_reason(model=model, prompt=prompt)

        new_complete_json = get_json_content(new_complete)
        if new_complete_json:
            last_complete = last_complete + new_complete_json

        recovered_items = _parse_toc_payload(last_complete)
        if recovered_items and (if_complete == "yes" or loop_count >= 2):
            return recovered_items

        if_complete = check_if_toc_transformation_is_complete(toc_content, last_complete, model)

    return _parse_toc_payload(last_complete)


def _split_toc_by_chapters(toc_content, max_chunk_chars=None):
    """Split TOC into chunks, trying to break at chapter boundaries.
    
    Args:
        toc_content: Raw TOC text to split
        max_chunk_chars: Maximum chunk size. If None, uses 8000 (default)
    """
    if max_chunk_chars is None:
        max_chunk_chars = 8000
    
    if len(toc_content) <= max_chunk_chars:
        return [toc_content]

    chunks = []
    lines = toc_content.split('\n')
    current_chunk = []
    current_length = 0

    for i, line in enumerate(lines):
        line_with_newline = line + '\n'
        line_length = len(line_with_newline)

        # Check if this line starts a new major chapter
        # Match patterns like "1\n", "2  Introduction", "Chapter 1", etc.
        is_chapter_start = bool(re.match(r'^(\d+)\s+[A-Z]', line.strip())) or bool(re.match(r'^\d+\s*$', line.strip()))

        # Force split if we're over limit and at a chapter boundary
        if current_length + line_length > max_chunk_chars and current_chunk and is_chapter_start:
            chunk_text = ''.join(current_chunk)
            chunks.append(chunk_text)
            print(f"[TOC Split] Chunk {len(chunks)}: {len(chunk_text)} chars, starts: {chunk_text[:60]}")
            current_chunk = [line_with_newline]
            current_length = line_length
        else:
            current_chunk.append(line_with_newline)
            current_length += line_length

    if current_chunk:
        chunk_text = ''.join(current_chunk)
        chunks.append(chunk_text)
        print(f"[TOC Split] Chunk {len(chunks)} (final): {len(chunk_text)} chars, starts: {chunk_text[:60]}")

    return chunks


def toc_transformer(toc_content, model=None):
    print('start toc_transformer')
    from pageindex.prompt_loader import format_prompt_by_use_case

    # Get adaptive chunking config based on model
    config = get_chunking_config_for_model(model)
    char_limit = config.toc_single_pass_threshold
    
    # Check if TOC is too large for single-pass transformation
    if len(toc_content) <= char_limit:
        print(f"[TOC] Single-pass transformation ({len(toc_content)} chars)")
        last_complete, finish_reason = Ollama_API_with_finish_reason(
            model=model,
            prompt=format_prompt_by_use_case('toc.transformer_init', toc_content=toc_content)
        )
        print(f"[TOC] Initial response: {len(last_complete)} chars, finish_reason={finish_reason}")

        parsed = extract_json(last_complete)
        if isinstance(parsed, dict):
            parsed_items = convert_page_to_int(parsed.get('table_of_contents', []))
            if parsed_items:
                print(f"[TOC] Single-pass parse produced {len(parsed_items)} items")
                return parsed_items
        elif isinstance(parsed, list):
            parsed_items = convert_page_to_int(parsed)
            if parsed_items:
                print(f"[TOC] Single-pass parse produced {len(parsed_items)} items")
                return parsed_items

        # If parse is empty and model says finished, return empty directly.
        # Otherwise fall through to chunked recovery path.
        if finish_reason == "finished":
            return []

    # TOC is too large - use chunked transformation
    print(f"[TOC] Large TOC detected ({len(toc_content)} chars), using chunked transformation")
    chunks = _split_toc_by_chapters(toc_content, max_chunk_chars=config.toc_chunk_size)
    print(f"[TOC] Split into {len(chunks)} chunks (config: {config})")

    all_items = []
    for i, chunk in enumerate(chunks):
        print(f"[TOC] Processing chunk {i+1}/{len(chunks)} ({len(chunk)} chars)...")
        try:
            chunk_items = _toc_transformer_single(chunk, model=model)
            if chunk_items:
                print(f"[TOC] Chunk {i+1} yielded {len(chunk_items)} items, first: {chunk_items[0].get('title', 'N/A')[:50]}, last: {chunk_items[-1].get('title', 'N/A')[:50]}")
                all_items.extend(chunk_items)
            else:
                print(f"[TOC] Chunk {i+1} yielded NO items (empty result)")
        except Exception as e:
            print(f"[TOC] Chunk {i+1} failed: {str(e)[:200]}")
            import traceback
            traceback.print_exc()
            continue

    print(f"[TOC] Total items collected: {len(all_items)}")

    # Deduplicate items with same title and page
    seen = set()
    deduplicated = []
    for item in all_items:
        title = str(item.get('title', '')).strip()
        page = item.get('page')
        key = (title.lower(), page)
        if key not in seen:
            seen.add(key)
            deduplicated.append(item)

    print(f"[TOC] ✓ Completed with {len(deduplicated)} items (from {len(all_items)} raw items)")
    if deduplicated:
        print(f"[TOC] First item: {deduplicated[0]}")
        print(f"[TOC] Last item: {deduplicated[-1]}")
    return deduplicated
    



def find_toc_pages(start_page_index, page_list, opt, logger=None):
    """Legacy sync version - deprecated, use find_toc_pages_async instead"""
    print('start find_toc_pages')
    last_page_is_yes = False
    toc_page_list = []
    i = start_page_index
    scan_window = max(opt.toc_check_page_num, 30)
    
    while i < len(page_list):
        # Only check beyond max_pages if we're still finding TOC pages
        if i >= start_page_index + scan_window and not last_page_is_yes:
            break
        detected_result = toc_detector_single_page(page_list[i][0],model=opt.model)
        if detected_result == 'yes':
            if logger:
                logger.info(f'Page {i} has toc')
            toc_page_list.append(i)
            last_page_is_yes = True
        elif detected_result == 'no' and last_page_is_yes:
            if logger:
                logger.info(f'Found the last page with toc: {i-1}')
            break
        i += 1
    
    if not toc_page_list and logger:
        logger.info('No toc found')
        
    return toc_page_list


async def find_toc_pages_async(start_page_index, page_list, opt, logger=None):
    """Async version with parallel processing - 5-30x faster than sync version"""
    print('start find_toc_pages (parallel processing)')
    
    # Determine how many pages to check
    scan_window = max(opt.toc_check_page_num, 30)
    max_check = min(scan_window, len(page_list) - start_page_index)
    
    if max_check <= 0:
        if logger:
            logger.info('No pages to check for TOC')
        return []
    
    # Create tasks for checking pages with semaphore to limit concurrency
    semaphore = asyncio.Semaphore(3)
    
    async def limited_toc_check(i, content):
        async with semaphore:
            return await toc_detector_single_page_async(content, model=opt.model)
    
    tasks = []
    page_indices = []
    for i in range(start_page_index, start_page_index + max_check):
        # Use a larger prefix to improve TOC recall on long front-matter pages
        content = page_list[i][0][:4000] if len(page_list[i][0]) > 4000 else page_list[i][0]
        tasks.append(limited_toc_check(i, content))
        page_indices.append(i)
    
    # Execute with limited concurrency
    if logger:
        logger.info(f'Checking {len(tasks)} pages for TOC (limited concurrency)')
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    toc_page_list = []
    for page_idx, result in zip(page_indices, results):
        if isinstance(result, Exception):
            if logger:
                logger.error(f'Page {page_idx} TOC detection failed: {result}')
            continue
        if result == 'yes':
            if logger:
                logger.info(f'Page {page_idx} has toc')
            toc_page_list.append(page_idx)
    
    # Find consecutive TOC pages starting from first match
    if toc_page_list:
        toc_page_list.sort()
        first_toc = toc_page_list[0]
        consecutive_toc = [first_toc]
        for i in range(1, len(toc_page_list)):
            if toc_page_list[i] == consecutive_toc[-1] + 1:
                consecutive_toc.append(toc_page_list[i])
            else:
                # Stop at first gap
                if logger:
                    logger.info(f'Found TOC gap at page {toc_page_list[i]}, stopping at page {consecutive_toc[-1]}')
                break
        toc_page_list = consecutive_toc
    
    if not toc_page_list and logger:
        logger.info('No toc found')
    else:
        if logger:
            logger.info(f'Found TOC pages: {toc_page_list}')
    
    return toc_page_list

def remove_page_number(data):
    if isinstance(data, dict):
        data.pop('page_number', None)  
        for key in list(data.keys()):
            if 'nodes' in key:
                remove_page_number(data[key])
    elif isinstance(data, list):
        for item in data:
            remove_page_number(item)
    return data

def extract_matching_page_pairs(toc_page, toc_physical_index, start_page_index):
    pairs = []
    for phy_item in toc_physical_index:
        for page_item in toc_page:
            if phy_item.get('title') == page_item.get('title'):
                physical_index = phy_item.get('physical_index')
                if physical_index is not None and int(physical_index) >= start_page_index:
                    pairs.append({
                        'title': phy_item.get('title'),
                        'page': page_item.get('page'),
                        'physical_index': physical_index
                    })
    return pairs


def calculate_page_offset(pairs):
    differences = []
    for pair in pairs:
        try:
            physical_index = pair['physical_index']
            page_number = pair['page']
            difference = physical_index - page_number
            differences.append(difference)
        except (KeyError, TypeError):
            continue
    
    if not differences:
        return None
    
    difference_counts = {}
    for diff in differences:
        difference_counts[diff] = difference_counts.get(diff, 0) + 1
    
    most_common = max(difference_counts.items(), key=lambda x: x[1])[0]
    
    return most_common

def add_page_offset_to_toc_json(data, offset):
    for i in range(len(data)):
        if data[i].get('page') is not None and isinstance(data[i]['page'], int):
            data[i]['physical_index'] = data[i]['page'] + offset
            del data[i]['page']
    
    return data



def page_list_to_group_text(page_contents, token_lengths, max_tokens=20000, overlap_page=1):    
    num_tokens = sum(token_lengths)
    
    if num_tokens <= max_tokens:
        # merge all pages into one text
        page_text = "".join(page_contents)
        return [page_text]
    
    subsets = []
    current_subset = []
    current_token_count = 0

    expected_parts_num = math.ceil(num_tokens / max_tokens)
    average_tokens_per_part = math.ceil(((num_tokens / expected_parts_num) + max_tokens) / 2)
    
    for i, (page_content, page_tokens) in enumerate(zip(page_contents, token_lengths)):
        if current_token_count + page_tokens > average_tokens_per_part:

            subsets.append(''.join(current_subset))
            # Start new subset from overlap if specified
            overlap_start = max(i - overlap_page, 0)
            current_subset = page_contents[overlap_start:i]
            current_token_count = sum(token_lengths[overlap_start:i])
        
        # Add current page to the subset
        current_subset.append(page_content)
        current_token_count += page_tokens

    # Add the last subset if it contains any pages
    if current_subset:
        subsets.append(''.join(current_subset))
    
    print('divide page_list to groups', len(subsets))
    return subsets

def add_page_number_to_toc(part, structure, model=None):
    fill_prompt_seq = """
    You are given an JSON structure of a document and a partial part of the document. Your task is to check if the title that is described in the structure is started in the partial given document.

    The provided text contains tags like <physical_index_X> and <physical_index_X> to indicate the physical location of the page X. 

    If the full target section starts in the partial given document, insert the given JSON structure with the "start": "yes", and "start_index": "<physical_index_X>".

    If the full target section does not start in the partial given document, insert "start": "no",  "start_index": None.

    The response should be in the following format. 
        [
            {
                "structure": <structure index, "x.x.x" or None> (string),
                "title": <title of the section>,
                "start": "<yes or no>",
                "physical_index": "<physical_index_X> (keep the format)" or None
            },
            ...
        ]    
    The given structure contains the result of the previous part, you need to fill the result of the current part, do not change the previous result.
    Directly return the final JSON structure. Do not output anything else."""

    prompt = fill_prompt_seq + f"\n\nCurrent Partial Document:\n{part}\n\nGiven Structure\n{json.dumps(structure, indent=2)}\n"
    current_json_raw = Ollama_API(model=model, prompt=prompt)
    json_result = extract_json(current_json_raw)

    if not isinstance(json_result, list) or not json_result:
        return structure
    
    for item in json_result:
        if 'start' in item:
            del item['start']
    return json_result


def remove_first_physical_index_section(text):
    """
    Removes the first section between <physical_index_X> and <physical_index_X> tags,
    and returns the remaining text.
    """
    pattern = r'<physical_index_\d+>.*?<physical_index_\d+>'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        # Remove the first matched section
        return text.replace(match.group(0), '', 1)
    return text

### add verify completeness
def generate_toc_continue(toc_content, part, model="mistral24b-16k"):
    print('start generate_toc_continue')
    prompt = format_prompt_by_use_case(
        "toc.generate_continue",
        part=part,
        toc_content=json.dumps(toc_content, indent=2)
    )
    response, finish_reason = Ollama_API_with_finish_reason(model=model, prompt=prompt)
    if finish_reason == 'finished':
        return extract_json(response)
    else:
        raise Exception(f'finish reason: {finish_reason}')
    
### add verify completeness
def generate_toc_init(part, model=None):
    print('start generate_toc_init')
    prompt = format_prompt_by_use_case(
        "toc.generate_init",
        part=part
    )
    response, finish_reason = Ollama_API_with_finish_reason(model=model, prompt=prompt)

    if finish_reason == 'finished':
         return extract_json(response)
    else:
        raise Exception(f'finish reason: {finish_reason}')

def create_simple_page_structure(page_list, start_index=1, pages_per_section=5):
    """
    Fallback structure creator for PDFs without TOC.
    Creates simple page-based sections instead of trying to detect structure.
    
    Args:
        page_list: List of pages
        start_index: Starting page index (default: 1)
        pages_per_section: Number of pages per section (default: 5)
    
    Returns:
        List of simple TOC entries grouping pages into sections
    """
    toc_structure = []
    num_pages = len(page_list)
    
    for section_start in range(start_index, start_index + num_pages, pages_per_section):
        section_end = min(section_start + pages_per_section - 1, start_index + num_pages - 1)
        
        if section_start == section_end:
            title = f"Page {section_start}"
        else:
            title = f"Pages {section_start}-{section_end}"
        
        toc_structure.append({
            'title': title,
            'physical_index': section_start
        })
    
    return toc_structure

def _normalize_toc_items(items):
    if isinstance(items, dict):
        return [items] if items else []
    if isinstance(items, list):
        return items
    return []


def _process_no_toc_single_pass(page_list, start_index=1, model=None, logger=None):
    page_contents=[]
    token_lengths=[]
    for page_index in range(start_index, start_index+len(page_list)):
        page_text = f"<physical_index_{page_index}>\n{page_list[page_index-start_index][0]}\n<physical_index_{page_index}>\n\n"
        page_contents.append(page_text)
        token_lengths.append(count_tokens(page_text, model))
    group_texts = page_list_to_group_text(page_contents, token_lengths)
    if logger:
        logger.info(f'len(group_texts): {len(group_texts)}')

    toc_with_page_number = generate_toc_init(group_texts[0], model)
    toc_with_page_number = _normalize_toc_items(toc_with_page_number)

    for group_text in group_texts[1:]:
        toc_with_page_number_additional = generate_toc_continue(toc_with_page_number, group_text, model)
        toc_with_page_number_additional = _normalize_toc_items(toc_with_page_number_additional)
        if toc_with_page_number_additional:
            toc_with_page_number.extend(toc_with_page_number_additional)

    if logger:
        logger.info(f'generate_toc: {toc_with_page_number}')

    toc_with_page_number = convert_physical_index_to_int(toc_with_page_number)
    if logger:
        logger.info(f'convert_physical_index_to_int: {toc_with_page_number}')

    return toc_with_page_number


def _should_use_hierarchical_no_toc(page_list, opt=None, model=None):
    """Determine if hierarchical chunking should be used for large no-TOC documents.
    
    Args:
        page_list: List of (text, tokens) tuples
        opt: Optional config object
        model: Model name for adaptive thresholds
    """
    # Get adaptive config
    config = get_chunking_config_for_model(model)
    
    total_pages = len(page_list)
    total_tokens = sum(page[1] for page in page_list)

    if total_pages >= config.no_toc_page_threshold:
        print(f"[Hierarchical] Triggered by page count: {total_pages} >= {config.no_toc_page_threshold}")
        return True

    token_threshold = config.no_toc_token_threshold
    if opt and getattr(opt, 'max_token_num_each_node', None):
        token_threshold = max(token_threshold, int(opt.max_token_num_each_node) * 4)

    if total_tokens >= token_threshold:
        print(f"[Hierarchical] Triggered by token count: {total_tokens} >= {token_threshold}")
        return True
    
    return False


def process_no_toc_hierarchical(page_list, start_index=1, model=None, logger=None, chunk_page_size=None, overlap_pages=None):
    """Process large no-TOC documents using hierarchical chunking.
    
    Args:
        page_list: List of (text, tokens) tuples
        start_index: Starting page number
        model: Model name (used for adaptive config)
        logger: Optional logger
        chunk_page_size: Pages per chunk (uses model's config if None)
        overlap_pages: Overlap between chunks (uses model's config if None)
    """
    # Get adaptive config
    config = get_chunking_config_for_model(model)
    if chunk_page_size is None:
        chunk_page_size = config.no_toc_chunk_size
    if overlap_pages is None:
        overlap_pages = config.no_toc_overlap_pages
    
    total_pages = len(page_list)
    if total_pages <= chunk_page_size:
        return _process_no_toc_single_pass(page_list, start_index=start_index, model=model, logger=logger)

    if logger:
        logger.info({
            'mode': 'process_no_toc_hierarchical',
            'total_pages': total_pages,
            'chunk_page_size': chunk_page_size,
            'overlap_pages': overlap_pages
        })

    merged_items = []
    step = max(1, chunk_page_size - overlap_pages)

    for local_chunk_start in range(0, total_pages, step):
        local_chunk_end = min(local_chunk_start + chunk_page_size, total_pages)
        chunk_pages = page_list[local_chunk_start:local_chunk_end]
        chunk_start_index = start_index + local_chunk_start

        if logger:
            logger.info({
                'hier_chunk_start': chunk_start_index,
                'hier_chunk_end': chunk_start_index + len(chunk_pages) - 1,
                'hier_chunk_pages': len(chunk_pages)
            })

        try:
            chunk_items = _process_no_toc_single_pass(
                chunk_pages,
                start_index=chunk_start_index,
                model=model,
                logger=logger
            )
        except Exception as exc:
            if logger:
                logger.info({
                    'hier_chunk_error': str(exc),
                    'chunk_start_index': chunk_start_index
                })
            chunk_items = create_simple_page_structure(chunk_pages, start_index=chunk_start_index, pages_per_section=10)

        merged_items.extend(_normalize_toc_items(chunk_items))

    deduped_items = []
    seen = set()
    for item in sorted(merged_items, key=lambda x: (x.get('physical_index') is None, x.get('physical_index') or 10**9, str(x.get('title', '')))):
        title = re.sub(r'\s+', ' ', str(item.get('title', '')).strip().lower())
        key = (item.get('physical_index'), title)
        if key in seen:
            continue
        seen.add(key)
        deduped_items.append(item)

    if not deduped_items:
        return create_simple_page_structure(page_list, start_index=start_index)

    return deduped_items


def process_no_toc(page_list, start_index=1, model=None, logger=None, opt=None):
    """Process no-TOC documents, automatically choosing single-pass or hierarchical.
    
    Args:
        page_list: List of (text, tokens) tuples
        start_index: Starting page number
        model: Model name (used for adaptive thresholds)
        logger: Optional logger
        opt: Optional config object
    """
    if _should_use_hierarchical_no_toc(page_list, opt=opt, model=model):
        print('start process_no_toc_hierarchical')
        return process_no_toc_hierarchical(page_list, start_index=start_index, model=model, logger=logger)
    return _process_no_toc_single_pass(page_list, start_index=start_index, model=model, logger=logger)

def process_toc_no_page_numbers(toc_content, toc_page_list, page_list,  start_index=1, model=None, logger=None):
    page_contents=[]
    token_lengths=[]
    toc_content = toc_transformer(toc_content, model)
    logger.info(f'toc_transformer: {toc_content}')
    for page_index in range(start_index, start_index+len(page_list)):
        page_text = f"<physical_index_{page_index}>\n{page_list[page_index-start_index][0]}\n<physical_index_{page_index}>\n\n"
        page_contents.append(page_text)
        token_lengths.append(count_tokens(page_text, model))
    
    group_texts = page_list_to_group_text(page_contents, token_lengths)
    logger.info(f'len(group_texts): {len(group_texts)}')

    toc_with_page_number=copy.deepcopy(toc_content)
    for group_text in group_texts:
        toc_with_page_number = add_page_number_to_toc(group_text, toc_with_page_number, model)
    logger.info(f'add_page_number_to_toc: {toc_with_page_number}')

    toc_with_page_number = convert_physical_index_to_int(toc_with_page_number)
    logger.info(f'convert_physical_index_to_int: {toc_with_page_number}')

    resolved_count = 0
    if isinstance(toc_with_page_number, list):
        resolved_count = sum(1 for item in toc_with_page_number if isinstance(item, dict) and item.get('physical_index') is not None)

    if resolved_count == 0:
        logger.info('No physical indices resolved from TOC-without-page-numbers flow; using simple page structure fallback')
        return create_simple_page_structure(page_list, start_index=start_index)

    return toc_with_page_number



def process_toc_with_page_numbers(toc_content, toc_page_list, page_list, toc_check_page_num=None, model=None, logger=None):
    toc_with_page_number = toc_transformer(toc_content, model)
    logger.info(f'toc_with_page_number: {toc_with_page_number}')

    toc_no_page_number = remove_page_number(copy.deepcopy(toc_with_page_number))
    
    start_page_index = toc_page_list[-1] + 1
    main_content = ""
    for page_index in range(start_page_index, min(start_page_index + toc_check_page_num, len(page_list))):
        main_content += f"<physical_index_{page_index+1}>\n{page_list[page_index][0]}\n<physical_index_{page_index+1}>\n\n"

    toc_with_physical_index = toc_index_extractor(toc_no_page_number, main_content, model)
    logger.info(f'toc_with_physical_index: {toc_with_physical_index}')

    toc_with_physical_index = convert_physical_index_to_int(toc_with_physical_index)
    logger.info(f'toc_with_physical_index: {toc_with_physical_index}')

    matching_pairs = extract_matching_page_pairs(toc_with_page_number, toc_with_physical_index, start_page_index)
    logger.info(f'matching_pairs: {matching_pairs}')

    offset = calculate_page_offset(matching_pairs)
    logger.info(f'offset: {offset}')

    toc_with_page_number = add_page_offset_to_toc_json(toc_with_page_number, offset)
    logger.info(f'toc_with_page_number: {toc_with_page_number}')

    toc_with_page_number = process_none_page_numbers(toc_with_page_number, page_list, model=model)
    logger.info(f'toc_with_page_number: {toc_with_page_number}')

    return toc_with_page_number



##check if needed to process none page numbers
def process_none_page_numbers(toc_items, page_list, start_index=1, model=None):
    for i, item in enumerate(toc_items):
        if "physical_index" not in item:
            # logger.info(f"fix item: {item}")
            # Find previous physical_index
            prev_physical_index = 0  # Default if no previous item exists
            for j in range(i - 1, -1, -1):
                if toc_items[j].get('physical_index') is not None:
                    prev_physical_index = toc_items[j]['physical_index']
                    break
            
            # Find next physical_index
            next_physical_index = -1  # Default if no next item exists
            for j in range(i + 1, len(toc_items)):
                if toc_items[j].get('physical_index') is not None:
                    next_physical_index = toc_items[j]['physical_index']
                    break

            page_contents = []
            for page_index in range(prev_physical_index, next_physical_index+1):
                # Add bounds checking to prevent IndexError
                list_index = page_index - start_index
                if list_index >= 0 and list_index < len(page_list):
                    page_text = f"<physical_index_{page_index}>\n{page_list[list_index][0]}\n<physical_index_{page_index}>\n\n"
                    page_contents.append(page_text)
                else:
                    continue

            item_copy = copy.deepcopy(item)
            del item_copy['page']
            result = add_page_number_to_toc(page_contents, item_copy, model)
            if result and isinstance(result[0]['physical_index'], str) and result[0]['physical_index'].startswith('<physical_index'):
                item['physical_index'] = int(result[0]['physical_index'].split('_')[-1].rstrip('>').strip())
                del item['page']
    
    return toc_items




def check_toc(page_list, opt=None):
    toc_page_list = find_toc_pages(start_page_index=0, page_list=page_list, opt=opt)
    if len(toc_page_list) == 0:
        print('no toc found')
        return {'toc_content': None, 'toc_page_list': [], 'page_index_given_in_toc': 'no'}
    else:
        print('toc found')
        toc_json = toc_extractor(page_list, toc_page_list, opt.model)

        if toc_json['page_index_given_in_toc'] == 'yes':
            print('index found')
            return {'toc_content': toc_json['toc_content'], 'toc_page_list': toc_page_list, 'page_index_given_in_toc': 'yes'}
        else:
            current_start_index = toc_page_list[-1] + 1
            
            while (toc_json['page_index_given_in_toc'] == 'no' and 
                   current_start_index < len(page_list)):
                
                additional_toc_pages = find_toc_pages(
                    start_page_index=current_start_index,
                    page_list=page_list,
                    opt=opt
                )
                
                if len(additional_toc_pages) == 0:
                    break

                additional_toc_json = toc_extractor(page_list, additional_toc_pages, opt.model)
                if additional_toc_json['page_index_given_in_toc'] == 'yes':
                    print('index found')
                    return {'toc_content': additional_toc_json['toc_content'], 'toc_page_list': additional_toc_pages, 'page_index_given_in_toc': 'yes'}

                else:
                    current_start_index = additional_toc_pages[-1] + 1
            print('index not found')
            return {'toc_content': toc_json['toc_content'], 'toc_page_list': toc_page_list, 'page_index_given_in_toc': 'no'}


async def check_toc_async(page_list, opt=None):
    """Async version with parallel TOC detection - 5-30x faster"""
    toc_page_list = await find_toc_pages_async(start_page_index=0, page_list=page_list, opt=opt)
    if len(toc_page_list) == 0:
        print('no toc found')
        return {'toc_content': None, 'toc_page_list': [], 'page_index_given_in_toc': 'no'}
    else:
        print('toc found')
        toc_json = toc_extractor(page_list, toc_page_list, opt.model)

        if toc_json['page_index_given_in_toc'] == 'yes':
            print('index found')
            return {'toc_content': toc_json['toc_content'], 'toc_page_list': toc_page_list, 'page_index_given_in_toc': 'yes'}
        else:
            current_start_index = toc_page_list[-1] + 1
            
            while (toc_json['page_index_given_in_toc'] == 'no' and 
                   current_start_index < len(page_list)):
                
                additional_toc_pages = await find_toc_pages_async(
                    start_page_index=current_start_index,
                    page_list=page_list,
                    opt=opt
                )
                
                if len(additional_toc_pages) == 0:
                    break

                additional_toc_json = toc_extractor(page_list, additional_toc_pages, opt.model)
                if additional_toc_json['page_index_given_in_toc'] == 'yes':
                    print('index found')
                    return {'toc_content': additional_toc_json['toc_content'], 'toc_page_list': additional_toc_pages, 'page_index_given_in_toc': 'yes'}

                else:
                    current_start_index = additional_toc_pages[-1] + 1
            print('index not found')
            return {'toc_content': toc_json['toc_content'], 'toc_page_list': toc_page_list, 'page_index_given_in_toc': 'no'}






################### fix incorrect toc #########################################################
def single_toc_item_index_fixer(section_title, content, model="mistral24b-16k"):
    from pageindex.prompt_loader import format_prompt_by_use_case
    
    prompt = format_prompt_by_use_case('toc.item_index_fixer', section_title=str(section_title), content=content)
    response = Ollama_API(model=model, prompt=prompt)
    json_content = extract_json(response)
    physical_index = json_content.get('physical_index') if isinstance(json_content, dict) else None
    return convert_physical_index_to_int(physical_index) if physical_index else None



async def fix_incorrect_toc(toc_with_page_number, page_list, incorrect_results, start_index=1, model=None, logger=None):
    print(f'start fix_incorrect_toc with {len(incorrect_results)} incorrect results')
    incorrect_indices = {result['list_index'] for result in incorrect_results}
    
    end_index = len(page_list) + start_index - 1
    
    incorrect_results_and_range_logs = []
    # Helper function to process and check a single incorrect item
    async def process_and_check_item(incorrect_item):
        list_index = incorrect_item['list_index']
        
        # Check if list_index is valid
        if list_index < 0 or list_index >= len(toc_with_page_number):
            # Return an invalid result for out-of-bounds indices
            return {
                'list_index': list_index,
                'title': incorrect_item['title'],
                'physical_index': incorrect_item.get('physical_index'),
                'is_valid': False
            }
        
        # Find the previous correct item
        prev_correct = None
        for i in range(list_index-1, -1, -1):
            if i not in incorrect_indices and i >= 0 and i < len(toc_with_page_number):
                physical_index = toc_with_page_number[i].get('physical_index')
                if physical_index is not None:
                    prev_correct = physical_index
                    break
        # If no previous correct item found, use start_index
        if prev_correct is None:
            prev_correct = start_index - 1
        
        # Find the next correct item
        next_correct = None
        for i in range(list_index+1, len(toc_with_page_number)):
            if i not in incorrect_indices and i >= 0 and i < len(toc_with_page_number):
                physical_index = toc_with_page_number[i].get('physical_index')
                if physical_index is not None:
                    next_correct = physical_index
                    break
        # If no next correct item found, use end_index
        if next_correct is None:
            next_correct = end_index
        
        incorrect_results_and_range_logs.append({
            'list_index': list_index,
            'title': incorrect_item['title'],
            'prev_correct': prev_correct,
            'next_correct': next_correct
        })

        page_contents=[]
        for page_index in range(prev_correct, next_correct+1):
            # Add bounds checking to prevent IndexError
            list_index = page_index - start_index
            if list_index >= 0 and list_index < len(page_list):
                page_text = f"<physical_index_{page_index}>\n{page_list[list_index][0]}\n<physical_index_{page_index}>\n\n"
                page_contents.append(page_text)
            else:
                continue
        content_range = ''.join(page_contents)
        
        physical_index_int = single_toc_item_index_fixer(incorrect_item['title'], content_range, model)
        
        # Check if the result is correct
        check_item = incorrect_item.copy()
        check_item['physical_index'] = physical_index_int
        check_result = await check_title_appearance(check_item, page_list, start_index, model)

        return {
            'list_index': list_index,
            'title': incorrect_item['title'],
            'physical_index': physical_index_int,
            'is_valid': check_result['answer'] == 'yes'
        }

    # Process incorrect items with limited concurrency
    semaphore = asyncio.Semaphore(3)
    
    async def limited_process(item):
        async with semaphore:
            return await process_and_check_item(item)
    
    tasks = [
        limited_process(item)
        for item in incorrect_results
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for item, result in zip(incorrect_results, results):
        if isinstance(result, Exception):
            print(f"Processing item {item} generated an exception: {result}")
            continue
    results = [result for result in results if not isinstance(result, Exception)]

    # Update the toc_with_page_number with the fixed indices and check for any invalid results
    invalid_results = []
    for result in results:
        if result['is_valid']:
            # Add bounds checking to prevent IndexError
            list_idx = result['list_index']
            if 0 <= list_idx < len(toc_with_page_number):
                toc_with_page_number[list_idx]['physical_index'] = result['physical_index']
            else:
                # Index is out of bounds, treat as invalid
                invalid_results.append({
                    'list_index': result['list_index'],
                    'title': result['title'],
                    'physical_index': result['physical_index'],
                })
        else:
            invalid_results.append({
                'list_index': result['list_index'],
                'title': result['title'],
                'physical_index': result['physical_index'],
            })

    logger.info(f'incorrect_results_and_range_logs: {incorrect_results_and_range_logs}')
    logger.info(f'invalid_results: {invalid_results}')

    return toc_with_page_number, invalid_results



async def fix_incorrect_toc_with_retries(toc_with_page_number, page_list, incorrect_results, start_index=1, max_attempts=3, model=None, logger=None):
    print('start fix_incorrect_toc')
    fix_attempt = 0
    current_toc = toc_with_page_number
    current_incorrect = incorrect_results

    while current_incorrect:
        print(f"Fixing {len(current_incorrect)} incorrect results")
        
        current_toc, current_incorrect = await fix_incorrect_toc(current_toc, page_list, current_incorrect, start_index, model, logger)
                
        fix_attempt += 1
        if fix_attempt >= max_attempts:
            logger.info("Maximum fix attempts reached")
            break
    
    return current_toc, current_incorrect




################### verify toc #########################################################
async def verify_toc(page_list, list_result, start_index=1, N=None, model=None):
    print('start verify_toc')
    # Find the last non-None physical_index
    last_physical_index = None
    for item in reversed(list_result):
        if item.get('physical_index') is not None:
            last_physical_index = item['physical_index']
            break
    
    # Early return only when we have no valid physical indices at all
    if last_physical_index is None:
        return 0, []

    # Keep verification alive even if the last index is in the first half of the document.
    # This avoids forcing a zero-accuracy fallback for partially valid TOCs.
    if last_physical_index < len(page_list) / 2:
        print(f"⚠️ verify_toc: last physical index {last_physical_index} is in first half of document; continuing verification")
    
    # Determine which items to check
    if N is None:
        print('check all items')
        sample_indices = range(0, len(list_result))
    else:
        N = min(N, len(list_result))
        print(f'check {N} items')
        sample_indices = random.sample(range(0, len(list_result)), N)

    # Prepare items with their list indices
    indexed_sample_list = []
    for idx in sample_indices:
        item = list_result[idx]
        # Skip items with None physical_index (these were invalidated by validate_and_truncate_physical_indices)
        if item.get('physical_index') is not None:
            item_with_index = item.copy()
            item_with_index['list_index'] = idx  # Add the original index in list_result
            indexed_sample_list.append(item_with_index)

    if not indexed_sample_list:
        return 0, []

    # Run checks concurrently
    tasks = [
        check_title_appearance(item, page_list, start_index, model)
        for item in indexed_sample_list
    ]
    results = await asyncio.gather(*tasks)
    
    # Process results
    correct_count = 0
    incorrect_results = []
    for result in results:
        if result['answer'] == 'yes':
            correct_count += 1
        else:
            incorrect_results.append(result)
    
    # Calculate accuracy
    checked_count = len(results)
    accuracy = correct_count / checked_count if checked_count > 0 else 0
    print(f"accuracy: {accuracy*100:.2f}%")
    return accuracy, incorrect_results





################### main process #########################################################
async def meta_processor(page_list, mode=None, toc_content=None, toc_page_list=None, start_index=1, opt=None, logger=None):
    print(mode)
    print(f'start_index: {start_index}')
    
    if mode == 'process_toc_with_page_numbers':
        toc_with_page_number = process_toc_with_page_numbers(toc_content, toc_page_list, page_list, toc_check_page_num=opt.toc_check_page_num, model=opt.model, logger=logger)
    elif mode == 'process_toc_no_page_numbers':
        toc_with_page_number = process_toc_no_page_numbers(toc_content, toc_page_list, page_list, model=opt.model, logger=logger)
    else:
        toc_with_page_number = process_no_toc(page_list, start_index=start_index, model=opt.model, logger=logger, opt=opt)
            
    toc_with_page_number = [item for item in toc_with_page_number if item.get('physical_index') is not None] 
    
    toc_with_page_number = validate_and_truncate_physical_indices(
        toc_with_page_number, 
        len(page_list), 
        start_index=start_index, 
        logger=logger
    )
    
    accuracy, incorrect_results = await verify_toc(page_list, toc_with_page_number, start_index=start_index, model=opt.model)
        
    logger.info({
        'mode': 'process_toc_with_page_numbers',
        'accuracy': accuracy,
        'incorrect_results': incorrect_results
    })
    if accuracy == 1.0 and len(incorrect_results) == 0:
        return toc_with_page_number
    if accuracy > 0.6 and len(incorrect_results) > 0:
        toc_with_page_number, incorrect_results = await fix_incorrect_toc_with_retries(toc_with_page_number, page_list, incorrect_results,start_index=start_index, max_attempts=3, model=opt.model, logger=logger)
        return toc_with_page_number
    else:
        if mode == 'process_toc_with_page_numbers':
            return await meta_processor(page_list, mode='process_toc_no_page_numbers', toc_content=toc_content, toc_page_list=toc_page_list, start_index=start_index, opt=opt, logger=logger)
        elif mode == 'process_toc_no_page_numbers':
            return await meta_processor(page_list, mode='process_no_toc', start_index=start_index, opt=opt, logger=logger)
        else:
            # Final fallback: Auto-generated TOC failed verification
            # Create simple page-based structure instead of raising exception
            print(f'⚠️  Auto-generated TOC has low accuracy ({accuracy*100:.1f}%). Using simple page-based structure.')
            logger.info({'fallback_reason': 'low_accuracy', 'accuracy': accuracy})
            return create_simple_page_structure(page_list, start_index=start_index)
        
 
async def process_large_node_recursively(node, page_list, opt=None, logger=None):
    node_page_list = page_list[node['start_index']-1:node['end_index']]
    token_num = sum([page[1] for page in node_page_list])
    
    if node['end_index'] - node['start_index'] > opt.max_page_num_each_node and token_num >= opt.max_token_num_each_node:
        print('large node:', node['title'], 'start_index:', node['start_index'], 'end_index:', node['end_index'], 'token_num:', token_num)

        node_toc_tree = await meta_processor(node_page_list, mode='process_no_toc', start_index=node['start_index'], opt=opt, logger=logger)
        node_toc_tree = await check_title_appearance_in_start_concurrent(node_toc_tree, page_list, model=opt.model, logger=logger)
        
        # Filter out items with None physical_index before post_processing
        valid_node_toc_items = [item for item in node_toc_tree if item.get('physical_index') is not None]
        
        if valid_node_toc_items and node['title'].strip() == valid_node_toc_items[0]['title'].strip():
            node['nodes'] = post_processing(valid_node_toc_items[1:], node['end_index'])
            node['end_index'] = valid_node_toc_items[1]['start_index'] if len(valid_node_toc_items) > 1 else node['end_index']
        else:
            node['nodes'] = post_processing(valid_node_toc_items, node['end_index'])
            node['end_index'] = valid_node_toc_items[0]['start_index'] if valid_node_toc_items else node['end_index']
        
    if 'nodes' in node and node['nodes']:
        tasks = [
            process_large_node_recursively(child_node, page_list, opt, logger=logger)
            for child_node in node['nodes']
        ]
        await asyncio.gather(*tasks)
    
    return node

async def tree_parser(page_list, opt, doc=None, logger=None):
    check_toc_result = await check_toc_async(page_list, opt)
    logger.info(check_toc_result)

    toc_content = check_toc_result.get("toc_content")
    page_index_in_toc = check_toc_result.get("page_index_given_in_toc")

    if toc_content and toc_content.strip():
        processing_mode = 'process_toc_with_page_numbers' if page_index_in_toc == "yes" else 'process_toc_no_page_numbers'
        toc_with_page_number = await meta_processor(
            page_list,
            mode=processing_mode,
            start_index=1,
            toc_content=toc_content,
            toc_page_list=check_toc_result.get('toc_page_list', []),
            opt=opt,
            logger=logger)
    else:
        toc_with_page_number = await meta_processor(
            page_list, 
            mode='process_no_toc', 
            start_index=1, 
            opt=opt,
            logger=logger)

    toc_with_page_number = add_preface_if_needed(toc_with_page_number)
    toc_with_page_number = await check_title_appearance_in_start_concurrent(toc_with_page_number, page_list, model=opt.model, logger=logger)
    
    # Filter out items with None physical_index before post_processings
    valid_toc_items = [item for item in toc_with_page_number if item.get('physical_index') is not None]
    
    toc_tree = post_processing(valid_toc_items, len(page_list))
    tasks = [
        process_large_node_recursively(node, page_list, opt, logger=logger)
        for node in toc_tree
    ]
    await asyncio.gather(*tasks)
    
    return toc_tree


def page_index_main(doc, opt=None):
    logger = JsonLogger(doc)
    
    is_valid_pdf = (
        (isinstance(doc, str) and os.path.isfile(doc) and doc.lower().endswith(".pdf")) or 
        isinstance(doc, BytesIO)
    )
    if not is_valid_pdf:
        raise ValueError("Unsupported input type. Expected a PDF file path or BytesIO object.")

    print('Parsing PDF...')
    page_list = get_page_tokens(doc)

    logger.info({'total_page_number': len(page_list)})
    logger.info({'total_token': sum([page[1] for page in page_list])})

    async def page_index_builder():
        structure = await tree_parser(page_list, opt, doc=doc, logger=logger)
        if opt.if_add_node_id == 'yes':
            write_node_id(structure)    
        if opt.if_add_node_text == 'yes':
            add_node_text(structure, page_list)
        if opt.if_add_node_summary == 'yes':
            if opt.if_add_node_text == 'no':
                add_node_text(structure, page_list)
            await generate_summaries_for_structure(structure, model=opt.model)
            if opt.if_add_node_text == 'no':
                remove_structure_text(structure)
            if opt.if_add_doc_description == 'yes':
                # Create a clean structure without unnecessary fields for description generation
                clean_structure = create_clean_structure_for_description(structure)
                doc_description = generate_doc_description(clean_structure, model=opt.model)
                return {
                    'doc_name': get_pdf_name(doc),
                    'doc_description': doc_description,
                    'structure': structure,
                }
        return {
            'doc_name': get_pdf_name(doc),
            'structure': structure,
        }

    return asyncio.run(page_index_builder())


def page_index(doc, model=None, toc_check_page_num=None, max_page_num_each_node=None, max_token_num_each_node=None,
               if_add_node_id=None, if_add_node_summary=None, if_add_doc_description=None, if_add_node_text=None):
    
    user_opt = {
        arg: value for arg, value in locals().items()
        if arg != "doc" and value is not None
    }
    opt = ConfigLoader().load(user_opt)
    return page_index_main(doc, opt)


def validate_and_truncate_physical_indices(toc_with_page_number, page_list_length, start_index=1, logger=None):
    """
    Validates and truncates physical indices that exceed the actual document length.
    This prevents errors when TOC references pages that don't exist in the document (e.g. the file is broken or incomplete).
    """
    if not toc_with_page_number:
        return toc_with_page_number
    
    max_allowed_page = page_list_length + start_index - 1
    truncated_items = []
    
    for i, item in enumerate(toc_with_page_number):
        if item.get('physical_index') is not None:
            original_index = item['physical_index']
            if original_index > max_allowed_page:
                item['physical_index'] = None
                truncated_items.append({
                    'title': item.get('title', 'Unknown'),
                    'original_index': original_index
                })
                if logger:
                    logger.info(f"Removed physical_index for '{item.get('title', 'Unknown')}' (was {original_index}, too far beyond document)")
    
    if truncated_items and logger:
        logger.info(f"Total removed items: {len(truncated_items)}")
        
    print(f"Document validation: {page_list_length} pages, max allowed index: {max_allowed_page}")
    if truncated_items:
        print(f"Truncated {len(truncated_items)} TOC items that exceeded document length")
     
    return toc_with_page_number