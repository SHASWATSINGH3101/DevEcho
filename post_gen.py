import sqlite3
import textwrap
from enum import Enum, auto
from typing import List, Literal, Optional, TypedDict

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from IPython.display import Image, display
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama
from langgraph.graph import END, StateGraph

import re
from pydantic import BaseModel, Field
import json
import os
seed = np.random.seed(42)

llm = ChatGroq(
    model= "llama3-70b-8192",
    temperature= 0.7,
    api_key= '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'
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

TWITTER_PROMPT = """
Generate a high-engagement tweet from the given text:
1. What problem does this solve?
2. Focus on the main technical points/features
3. Write a short, coherent paragraph (2-3 sentences max)
4. Use natural, conversational language
5. Optimize for virality: make it intriguing, relatable, or controversial
6. Exclude emojis and hashtags

{tone_instructions}

Make sure to include sources at the end of the tweet if they're available, in a brief format.
"""

TWITTER_CRITIQUE_PROMPT = """
You are a Tweet Critique Agent. Your task is to analyze tweets and provide actionable feedback to make them more engaging. Focus on:

1. Clarity: Is the message clear and easy to understand?
2. Hook: Does it grab attention in the first few words?
3. Brevity: Is it concise while maintaining impact?
4. Call-to-action: Does it encourage interaction or sharing?
5. Tone: Is it appropriate for the intended audience and matches the requested tone?
6. Storytelling: Does it evoke curiosity?
7. Remove hype: Does it promise more than it delivers?
8. Sources: Are sources properly included and formatted?

Provide 2-3 specific suggestions to improve the tweet's engagement potential.
Do not suggest hashtags. Keep your feedback concise and actionable.

Your goal is to help the writer improve their social media writing skills and increase engagement with their posts.
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
Keep the post concise (50-80 words) and relevant to the industry.
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
    feedback: Optional[str]

class Appstate(TypedDict):
    user_text: str
    target_audience: str
    tone: str
    sources: list
    edit_text: str
    tweet: str
    linkedin_post: str
    n_drafts: str

def editor_node(state: Appstate):
    tone_instructions = TONE_PROMPTS.get(state['tone'], "")
    prompt = f"""text:{state['user_text']}""".strip()
    editor_prompt_with_tone = EDITOR_PROMPT.format(tone_instructions=tone_instructions)
    response = llm.invoke([SystemMessage(editor_prompt_with_tone), HumanMessage(prompt)])
    return {'edit_text': response.content}

def tweet_writer_node(state: Appstate):
    post = state['tweet']
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
    {sources_text}""".strip()
    
    twitter_prompt_with_tone = TWITTER_PROMPT.format(tone_instructions=tone_instructions)
    response = llm.invoke([SystemMessage(twitter_prompt_with_tone), HumanMessage(prompt)])
    post.drafts.append(response.content)
    return {'tweet': post}

def linkedin_writer_node(state: Appstate):
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

def critique_tweet_node(state: Appstate):
    post = state["tweet"]
    
    # Ensure drafts exist before accessing
    if post.drafts:
        prompt = f"""Full post:```{state["edit_text"]}```
        Suggested tweet (critique this):```{post.drafts[-1]}```
        Target audience: {state["target_audience"]}
        Requested tone: {state["tone"]}""".strip()
        
        response = llm.invoke(
            [SystemMessage(TWITTER_CRITIQUE_PROMPT), HumanMessage(prompt)]
        )
        post.feedback = response.content
    else:
        # Handle case where no drafts exist yet
        post.feedback = "No draft available to critique yet."
    
    return {"tweet": post}

def critique_linkedin_node(state: Appstate):
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
    return state

def should_rewrite(state: Appstate)-> Literal[['linkedin_critique', 'tweet_critique'], END]:
    tweet = state['tweet']
    linkedin_post = state['linkedin_post']
    n_drafts = state['n_drafts']
    if len(tweet.drafts) >= n_drafts and len(linkedin_post.drafts)>= n_drafts:
        return END
    return ['linkedin_critique', 'tweet_critique']

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

graph = StateGraph(Appstate)

graph.add_node('editor', editor_node)
graph.add_node('tweet_writer', tweet_writer_node)
graph.add_node('tweet_critique', critique_tweet_node)
graph.add_node('linkedin_writer', linkedin_writer_node)
graph.add_node('linkedin_critique', critique_linkedin_node)
graph.add_node('supervisor', supervisor_node)

graph.add_edge('editor', 'tweet_writer')
graph.add_edge('editor','linkedin_writer')

graph.add_edge('tweet_writer', 'supervisor')
graph.add_edge('linkedin_writer', 'supervisor')
graph.add_conditional_edges('supervisor', should_rewrite)

graph.add_edge('tweet_critique', 'tweet_writer')
graph.add_edge('linkedin_critique', 'linkedin_writer')

graph.set_entry_point('editor')

app = graph.compile()

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

# Config settings
config = {"configurable": {"thread_id": 42}}

# Get tone from tone.json if it exists, otherwise use "professional"
tone = "professional"
try:
    with open('./config/tone.json', 'r', encoding='utf-8') as tone_file:
        tone_data = json.load(tone_file)
        tone = tone_data.get("tone", "professional")
except (FileNotFoundError, json.JSONDecodeError):
    # Create the tone.json file with default tone
    os.makedirs('./config', exist_ok=True)
    with open('./config/tone.json', 'w', encoding='utf-8') as tone_file:
        json.dump({"tone": tone}, tone_file, indent=4)

state = app.invoke(
    {
        "user_text": answer,  # Use the answer from RAG
        "target_audience": "AI/ML engineers and researchers, Data Scientists",
        "tone": tone,  # Use the tone from config
        "sources": sources,  # Add extracted sources
        "tweet": Post(drafts=[], feedback=None),
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

# Prepare output data for Twitter posts
twitter_output_data = []
for i, draft in enumerate(state["tweet"].drafts):
    draft_info = {
        "draft_number": i + 1,
        "content": textwrap.fill(draft, 80),
        "tone": tone,
        "sources": sources
    }
    twitter_output_data.append(draft_info)

# Ensure the output directories exist
os.makedirs('./linkedin_posts', exist_ok=True)
os.makedirs('./twitter_posts', exist_ok=True)

# Save LinkedIn posts
with open('./linkedin_posts/linkedinpost.json', 'w', encoding='utf-8') as json_file:
    json.dump(linkedin_output_data, json_file, indent=4)

# Save Twitter posts
with open('./twitter_posts/twitterpost.json', 'w', encoding='utf-8') as json_file:
    json.dump(twitter_output_data, json_file, indent=4)

print("Posts generated and saved successfully!")

if __name__ == "__main__":
    # This will execute only when run directly, not when imported
    pass