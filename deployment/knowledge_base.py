from langchain_community.tools import TavilySearchResults
from langchain_community.document_loaders.firecrawl import FireCrawlLoader

from typing import Tuple, Optional, List 

from gitingest import ingest
import os
import re
from gitingest import ingest_async
import asyncio
import json

os.environ['TAVILY_API_KEY'] = ''

def classify_input(user_instruction: str, user_input: str) -> dict:
    url_pattern = re.compile(
        r'^(https?:\/\/)?'                       
        r'(([a-zA-Z0-9\-_]+\.)+[a-zA-Z]{2,}|'      
        r'localhost|'                             
        r'(\d{1,3}\.){3}\d{1,3})'                  
        r'(:\d+)?(\/[^\s]*)?$'                     
    )

    user_input = user_input.strip()

    if url_pattern.match(user_input):
        if "github.com" in user_input:
            return {
                "type": "github_repo",
                "input": user_input,
                "instruction": user_instruction
            }
        else:
            return {
                "type": "url",
                "input": user_input,
                "instruction": user_instruction
            }
    else:
        return {
            "type": "topic",
            "input": user_input,
            "instruction": user_instruction
        }

# Modified to be async-compatible
async def process_with_gitingest_async(github_url: str) -> Tuple[str, str, str]:
    try:
        summary, tree, content = await ingest_async(github_url)
        print(f'Ingested data from {github_url}')
        return summary, tree, content
    except Exception as e:
        print('Ingestion error:', e)
        return "", "", ""

# Synchronous fallback that doesn't use asyncio.run()
def process_with_gitingest(github_url: str) -> Tuple[str, str, str]:
    try:
        summary, tree, content = ingest(github_url)  # Use synchronous ingest
        print(f'Ingested data from {github_url}')
        return summary, tree, content
    except Exception as e:
        print('Ingestion error:', e)
        return "", "", ""

# Modified to support both sync and async operation
async def handle_github_repo_async(github_url: Optional[str] = None) -> None:
    if not github_url:
        print('No url, ingestion Skipped')
        return
    summary, tree, content = await process_with_gitingest_async(github_url)
    try:
        os.makedirs('./data', exist_ok=True)
        with open('./data/results.txt', 'w', encoding='utf-8') as file:
            file.write(summary)
            file.write(tree)
            file.write(content)
            file.close()
        print('data written')
    except Exception as e:
        print('error in writing data')
        raise

# Keep synchronous version for non-async contexts
def handle_github_repo(github_url: Optional[str] = None) -> None:
    if not github_url:
        print('No url, ingestion Skipped')
        return
    summary, tree, content = process_with_gitingest(github_url)
    try:
        os.makedirs('./data', exist_ok=True)
        with open('./data/results.txt', 'w', encoding='utf-8') as file:
            file.write(summary)
            file.write(tree)
            file.write(content)
            file.close()
        print('data written')
    except Exception as e:
        print('error in writing data')
        raise
        
# Function to handle general URLs
async def handle_url_async(url):
    loader = FireCrawlLoader(
    api_key="FIRECRWAL_API_KEY", url=url, mode="scrape"
    )
    pages = []
    for doc in loader.lazy_load():
        pages.append(doc)
    
    os.makedirs('./data', exist_ok=True)
    f = open('./data/results.txt', "w", encoding='utf-8')
    f.write((str(pages)))
    f.close()

# Synchronous version for backward compatibility
def handle_url(url):
    loader = FireCrawlLoader(
    api_key="FIRECRWAL_API_KEY", url=url, mode="scrape"
    )
    pages = []
    for doc in loader.lazy_load():
        pages.append(doc)
    
    os.makedirs('./data', exist_ok=True)
    f = open('./data/results.txt', "w", encoding='utf-8')
    f.write((str(pages)))
    f.close()

# Async version of handle_topic
async def handle_topic_async(instruction, query):
    search = TavilySearchResults(max_results=5, search_depth="advanced", include_answer=True)
    search_result = search.invoke(instruction + ':-' + query)
    
    os.makedirs('./data', exist_ok=True)
    f = open('./data/results.txt', "w", encoding='utf-8')
    f.write((str(search_result)))
    f.close()

# Function to handle topics (synchronous version)
def handle_topic(instruction, query):
    search = TavilySearchResults(max_results=5, search_depth="advanced", include_answer=True)
    search_result = search.invoke(instruction + ':-' + query)
    
    os.makedirs('./data', exist_ok=True)
    f = open('./data/results.txt', "w", encoding='utf-8')
    f.write((str(search_result)))
    f.close()

# Async version of process_classification_result
async def process_classification_result_async(result: dict):
    input_type = result["type"]
    input_url = result["input"] if input_type in ["github_repo", "url"] else ""

    if input_type == "github_repo":
        await handle_github_repo_async(result["input"])
    elif input_type == "url":
        await handle_url_async(result["input"])
    elif input_type == "topic":
        await handle_topic_async(result["instruction"], result["input"])
    else:
        print("Unknown input type.")
    
    return result["instruction"], result['input'], input_type, input_url

# Keep synchronous version for backward compatibility
def process_classification_result(result: dict):
    input_type = result["type"]
    input_url = result["input"] if input_type in ["github_repo", "url"] else ""

    if input_type == "github_repo":
        handle_github_repo(result["input"])
    elif input_type == "url":
        handle_url(result["input"])
    elif input_type == "topic":
        handle_topic(result["instruction"], result["input"])
    else:
        print("Unknown input type.")
    
    return result["instruction"], result['input'], input_type, input_url


def query_saver(query: str, input_type: str, input_url: str):
    # Ensure the directory exists
    os.makedirs('./query', exist_ok=True)
    with open('./query/query.json', 'w', encoding='utf-8') as file:
        json.dump({
            "query": query,
            "input_type": input_type,
            "input_url": input_url
        }, file, indent=4)

# Add async version of run_data_collection
async def run_data_collection_async(user_inst=None, user_rep=None):
    # Get user input
    if user_inst and user_rep:
        user_instruction = user_inst
        user_response = user_rep
    else:
        user_instruction = input('enter instructions:- ')
        user_response = input('enter input:-')

    # Classify input
    result = classify_input(user_instruction, user_response)

    user_prompt, user_input, input_type, input_url = await process_classification_result_async(result)
    query_saver(user_prompt, input_type, input_url)
    
    # Return a message about the data collection
    return f"Data collected successfully!\nType: {input_type}\nQuery: {user_prompt}"
  
def run_data_collection(user_inst=None, user_rep=None):
    # Get user input
    if user_inst and user_rep:
        user_instruction = user_inst
        user_response = user_rep
    else:
        user_instruction = input('enter instructions:- ')
        user_response = input('enter input:-')

    # Classify input
    result = classify_input(user_instruction, user_response)

    user_prompt, user_input, input_type, input_url = process_classification_result(result)
    query_saver(user_prompt, input_type, input_url)
    
    # Return a message about the data collection
    return f"Data collected successfully!\nType: {input_type}\nQuery: {user_prompt}"

if __name__ == '__main__':
    run_data_collection()