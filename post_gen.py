import textwrap
from typing import List, Optional, TypedDict
from enum import Enum, auto

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.graph import END, StateGraph

import re
import json
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("post_gen.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Set random seed for reproducibility
seed = np.random.seed(42)

# Initialize the LLM (using Groq's llama3-70b-8192 model)
llm = ChatGroq(
    model="llama3-70b-8192",
    temperature=0.7,
    api_key='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'
)

# Define different tone prompts
TONE_PROMPTS = {
    "professional": """
    Write in a clear, authoritative tone. Use industry terminology appropriately.
    Maintain a balanced perspective and back statements with evidence.
    Be concise and direct while maintaining formality.
    """,
    
    "casual": """
    Write in a conversational, approachable tone.
    Use simple language and occasional humor where appropriate.
    Be friendly and relatable while still informative.
    """,
    
    "educational": """
    Write in an instructive, explanatory tone.
    Break down complex concepts into digestible information.
    Use examples and analogies to illustrate points.
    """,
    
    "persuasive": """
    Write in a compelling, convincing tone.
    Emphasize benefits and opportunities.
    Use strong calls-to-action and emphasize value propositions.
    """
}

EDITOR_PROMPT = """
Rewrite for maximum social media engagement:

- Use attention-grabbing, concise language
- Inject personality and humor
- Optimize formatting (short paragraphs)
- Encourage interaction (questions, calls-to-action)
- Ensure perfect grammar and spelling
- Rewrite from first person perspective, when talking to an audience

{tone_instructions}

Use only the information provided in the text. Think carefully.
"""

LINKEDIN_PROMPT = """
Write a compelling LinkedIn post from the given text. Structure it as follows:

1. Eye-catching headline (5-7 words)
2. Identify a key problem or challenge
3. Provide a bullet list of key benefits/features
4. Highlight a clear benefit or solution
5. Conclude with a thought-provoking question

{tone_instructions}

Maintain a professional, informative tone. Avoid emojis and hashtags.
Keep the post concise (150-300 words) and relevant to the industry.
Focus on providing valuable insights or actionable takeaways that will resonate
with professionals in the field.

Make sure to include sources at the end of the post in a professional format.
"""

LINKEDIN_CRITIQUE_PROMPT = """
Your role is to analyze LinkedIn posts and provide actionable feedback to make them more engaging.
Focus on the following aspects:

1. Hook: Evaluate the opening line's ability to grab attention.
2. Structure: Assess the post's flow and readability.
3. Content value: Determine if the post provides useful information or insights.
4. Call-to-action: Check if there's a clear next step for readers.
5. Language: Suggest improvements in tone, style, and word choice.
6. Visual elements: Recommend additions or changes to images, videos, or formatting.
7. Tone match: Verify if the post matches the requested tone.
8. Sources: Ensure sources are properly included and formatted.

For each aspect, provide:
- A brief assessment (1-2 sentences)
- A specific suggestion for improvement
- A concise example of the suggested change

Conclude with an overall recommendation for the most impactful change the author can make to increase engagement.
Your goal is to help the writer improve their social media writing skills and increase engagement with their posts.
"""

class Post(BaseModel):
    """A post written in different versions"""
    drafts: list = Field(default_factory=list)
    feedback: Optional[str] = None

class Appstate(TypedDict):
    user_text: str
    target_audience: str
    tone: str
    sources: list
    edit_text: str
    linkedin_post: Post
    n_drafts: int

def editor_node(state: Appstate):
    """Process the input text to make it more engaging"""
    tone_instructions = TONE_PROMPTS.get(state['tone'], "")
    prompt = f"""text:{state['user_text']}""".strip()
    editor_prompt_with_tone = EDITOR_PROMPT.format(tone_instructions=tone_instructions)
    response = llm.invoke([SystemMessage(editor_prompt_with_tone), HumanMessage(prompt)])
    return {'edit_text': response.content}

def linkedin_writer_node(state: Appstate):
    """Generate LinkedIn post drafts"""
    post = state['linkedin_post']
    tone_instructions = TONE_PROMPTS.get(state['tone'], "")
    
    # Prepare sources string
    sources_text = ""
    if state.get('sources') and len(state['sources']) > 0:
        sources_text = "\n\nSources available to reference:\n" + "\n".join(state['sources'])
    
    feedback_prompt = ""
    if post.feedback and post.drafts:
        feedback_prompt = f"\nUse the feedback to improve it:\n{post.feedback}"
    
    prompt = f"""text:{state['edit_text']}{feedback_prompt}
    Target audience: {state['target_audience']}
    {sources_text}
    write only the text for the post""".strip()
    
    linkedin_prompt_with_tone = LINKEDIN_PROMPT.format(tone_instructions=tone_instructions)
    response = llm.invoke([SystemMessage(linkedin_prompt_with_tone), HumanMessage(prompt)])
    post.drafts.append(response.content)
    return {'linkedin_post': post}

def critique_linkedin_node(state: Appstate):
    """Provide feedback on the LinkedIn post drafts"""
    post = state['linkedin_post']

    # Ensure drafts exist before accessing
    if post.drafts:
        prompt = f"""Full post:```{state['edit_text']}```
        Suggested LinkedIn post (critique this):```{post.drafts[-1]}```
        Target audience: {state['target_audience']}
        Requested tone: {state["tone"]}
        """.strip()
        response = llm.invoke(
            [SystemMessage(LINKEDIN_CRITIQUE_PROMPT), HumanMessage(prompt)]
        )
        post.feedback = response.content
    else:
        # Handle case where no drafts exist yet
        post.feedback = "No draft available to critique yet."
    
    return {'linkedin_post': post}

def supervisor_node(state: Appstate):
    """Monitor the state and pass it through"""
    return state

def should_rewrite(state: Appstate):
    """Decide if more drafts are needed"""
    linkedin_post = state['linkedin_post']
    n_drafts = state['n_drafts']
    if len(linkedin_post.drafts) >= n_drafts:
        return END
    return ['linkedin_critique']

def extract_sources(result_json):
    """Extract sources from the result.json file"""
    sources = []
    
    # Try to find URLs in the retrieved context
    if "retrieved_context" in result_json:
        for context in result_json["retrieved_context"]:
            # Simple URL extraction regex
            urls = re.findall(r'https?://\S+', context)
            for url in urls:
                if url not in sources:
                    sources.append(url)
                    
    # If no URLs found in context, try to identify the source type
    if not sources and "input_type" in result_json:
        if result_json.get("input_type") == "github_repo" and "input_url" in result_json:
            sources.append(result_json["input_url"])
        elif result_json.get("input_type") == "url" and "input_url" in result_json:
            sources.append(result_json["input_url"])
            
    return sources

def get_current_tone():
    """Get the current tone from configuration file"""
    tone = "professional"  # Default tone
    try:
        with open('./config/tone.json', 'r', encoding='utf-8') as tone_file:
            tone_data = json.load(tone_file)
            tone = tone_data.get("tone", "professional")
    except (FileNotFoundError, json.JSONDecodeError):
        # Create the tone.json file with default tone
        os.makedirs('./config', exist_ok=True)
        with open('./config/tone.json', 'w', encoding='utf-8') as tone_file:
            json.dump({"tone": tone}, tone_file, indent=4)
    return tone

def main():
    """Main function to run the LinkedIn post generation process"""
    try:
        logger.info("Starting LinkedIn post generation")
        
        # Create necessary directories
        os.makedirs('./output', exist_ok=True)
        os.makedirs('./config', exist_ok=True)
        os.makedirs('./linkedin_posts', exist_ok=True)
        
        # Load data from result.json
        with open('./output/result.json', 'r', encoding='utf-8') as file:
            data = json.load(file)
        
        # Extract retrieved context and format it into a single string
        retrieved_context = "\n\n".join(data["retrieved_context"])
        answer = data["answer"]
        
        # Try to extract sources
        sources = extract_sources(data)
        
        # Save input_type and input_url in result.json if they exist
        if "input_type" not in data and "type" in data:
            data["input_type"] = data["type"]
            with open('./output/result.json', 'w', encoding='utf-8') as file:
                json.dump(data, file, indent=4)
        
        # Get tone from configuration
        tone = get_current_tone()
        
        # Setup LangGraph
        graph = StateGraph(Appstate)
        
        # Add nodes
        graph.add_node('editor', editor_node)
        graph.add_node('linkedin_writer', linkedin_writer_node)
        graph.add_node('linkedin_critique', critique_linkedin_node)
        graph.add_node('supervisor', supervisor_node)
        
        # Add edges
        graph.add_edge('editor', 'linkedin_writer')
        graph.add_edge('linkedin_writer', 'supervisor')
        graph.add_conditional_edges('supervisor', should_rewrite)
        graph.add_edge('linkedin_critique', 'linkedin_writer')
        
        # Set entry point
        graph.set_entry_point('editor')
        
        # Compile the graph
        app = graph.compile()
        
        # Config settings
        config = {"configurable": {"thread_id": 42}}
        
        # Invoke the graph with initial state
        logger.info(f"Invoking LangGraph with tone: {tone}")
        state = app.invoke(
            {
                "user_text": answer,  # Use the answer from RAG
                "target_audience": "AI/ML engineers and researchers, Data Scientists",
                "tone": tone,  # Use the tone from config
                "sources": sources,  # Add extracted sources
                "linkedin_post": Post(drafts=[], feedback='Add Sources'),
                "n_drafts": 3,
            },
            config=config,
        )
        
        # Prepare output data for LinkedIn posts
        linkedin_output_data = []
        for i, draft in enumerate(state["linkedin_post"].drafts):
            draft_info = {
                "draft_number": i + 1,
                "content": textwrap.fill(draft, 80),
                "tone": tone,
                "sources": sources
            }
            linkedin_output_data.append(draft_info)
        
        # Save LinkedIn posts
        with open('./linkedin_posts/linkedinpost.json', 'w', encoding='utf-8') as json_file:
            json.dump(linkedin_output_data, json_file, indent=4)
        
        logger.info(f"Generated {len(linkedin_output_data)} LinkedIn posts successfully")
        return 0
        
    except Exception as e:
        logger.error(f"Error in post generation: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)