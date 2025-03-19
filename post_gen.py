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

from pydantic import BaseModel, Field
seed = np.random.seed(42)

llm = ChatGroq(
    model= "llama3-70b-8192",
    temperature= 0.7,
    api_key= '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'
)


EDITOR_PROMPT = """
Rewrite for maximum social media engagement:

- Use attention-grabbing, concise language
- Inject personality and humor
- Optimize formatting (short paragraphs)
- Encourage interaction (questions, calls-to-action)
- Ensure perfect grammar and spelling
- Rewrite from first person perspective, when talking to an audience

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
"""

TWITTER_CRITIQUE_PROMPT = """
You are a Tweet Critique Agent. Your task is to analyze tweets and provide actionable feedback to make them more engaging. Focus on:

1. Clarity: Is the message clear and easy to understand?
2. Hook: Does it grab attention in the first few words?
3. Brevity: Is it concise while maintaining impact?
4. Call-to-action: Does it encourage interaction or sharing?
5. Tone: Is it appropriate for the intended audience?
6. Storytelling: Does it evoke curiosity?
7. Remove hype: Does it promise more than it delivers?

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

Maintain a professional, informative tone. Avoid emojis and hashtags.
Keep the post concise (50-80 words) and relevant to the industry.
Focus on providing valuable insights or actionable takeaways that will resonate
with professionals in the field.
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
    #this works for me, not this (drafts: List[str])
    feedback: Optional[str]

class Appstate(TypedDict):
    user_text: str
    target_audience: str
    edit_text: str
    tweet: str
    linkedin_post: str
    n_drafts: str

def editor_node(state: Appstate): # state is current_state
    prompt = f"""text:{state['user_text']}""".strip()
    response = llm.invoke([SystemMessage(EDITOR_PROMPT), HumanMessage(prompt)])
    return {'edit_text': response.content}

def tweet_writer_node(state: Appstate): # state is current_state
    post = state['tweet'] # post variable gets state['tweet']
    feedback_prompt = ... # Construct feedback prompt based on post.feedback
    prompt = f"""text:{state['edit_text']} ... {feedback_prompt} ... Target audience: {state['target_audience']} ...""".strip()
    response = llm.invoke([SystemMessage(TWITTER_PROMPT), HumanMessage(prompt)])
    post.drafts.append(response.content) # Update post.drafts
    return {'tweet': post} # Return updated post for 'tweet' in state

def linkedin_writer_node(state: Appstate):
    post = state['linkedin_post']

    # Check if drafts exist before trying to access post.drafts[-1]
    if post.feedback and post.drafts:
        feedback_prompt = f"""LinkedIn post :```{post.drafts[-1]}```Use the feedback to improve it:```{post.feedback}```""".strip()
    else:
        feedback_prompt = ""

    prompt = f"""text:```{state['edit_text']}```{feedback_prompt}Target audience:
    {state['target_audience']}write only the text for the post """.strip()
    response = llm.invoke([SystemMessage(LINKEDIN_PROMPT), HumanMessage(prompt)])
    post.drafts.append(response.content)
    return {'linkedin_post': post}

def critique_tweet_node(state: Appstate):
    post = state["tweet"]
    
    # Ensure drafts exist before accessing
    if post.drafts:
        prompt = f"""Full post:```{state["edit_text"]}```Suggested tweet (critique this):```{post.drafts[-1]}```Target audience: {state["target_audience"]}""".strip()
        
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
        prompt = f"""Full post:```{state['edit_text']}```Suggested LinkedIn post (critique this):```{post.drafts[-1]}```
Target audience: {state['target_audience']}
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


graph = StateGraph(Appstate)

graph.add_node('editor', editor_node)
graph.add_node('tweet_writer', tweet_writer_node)
graph.add_node('tweet_critique', critique_tweet_node)
graph.add_node('linkedin_writer', linkedin_writer_node)
graph.add_node('linkedin_critique', critique_linkedin_node )
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

# display(Image(app.get_graph().draw_mermaid_png()))



import os
import json


# Load data from result.json
with open('./output/result.json', 'r', encoding='utf-8') as file:
    data = json.load(file)

# Extract retrieved context and format it into a single string
retrieved_context = "\n\n".join(data["retrieved_context"])
retrieved_context = "\n\n".join(data["answer"])
# Config settings
config = {"configurable": {"thread_id": 42}}

# Use retrieved context as user text
user_text = retrieved_context

state = app.invoke(
    {
        "user_text": user_text,
        "target_audience": "AI/ML engineers and researchers, Data Scientists",
        "tweet": Post(drafts=[], feedback=None),
        "linkedin_post": Post(drafts=[], feedback='Add Sources'),
        "n_drafts": 3,
    },
    config=config,
)

# l_post = []
# for i, draft in enumerate(state["linkedin_post"].drafts):
#     l_post.append(state["linkedin_post"].drafts)
 
import textwrap


output_data = []

for i, draft in enumerate(state["linkedin_post"].drafts):
    draft_info = {
        "draft_number": i + 1,
        "content": textwrap.fill(draft, 80)
    }
    output_data.append(draft_info)


    

print("Drafts saved successfully to drafts_output.json!")


# Ensure the './posts' directory exists
os.makedirs('./linkedin_posts', exist_ok=True)

with open('./linkedin_posts/linkedinpost.json', 'w', encoding='utf-8') as json_file:
    json.dump(output_data, json_file, indent=4)

