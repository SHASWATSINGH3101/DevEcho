from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document
from typing import Literal, TypedDict, List
from typing_extensions import Annotated
from langgraph.graph import START, StateGraph
from langchain_core.vectorstores import InMemoryVectorStore
import json
import os

llm = ChatGroq(
            model='llama3-70b-8192',
            temperature=0.7,
            max_tokens=1024,
            api_key='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'
        )

embeddings = HuggingFaceEmbeddings(model_name='sentence-transformers/all-mpnet-base-v2')

loader = DirectoryLoader(
            path='./data',
            glob='**/*.txt',
            loader_cls=TextLoader,
            loader_kwargs={'encoding': 'utf-8'}
        )
docs = loader.load()
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    add_start_index=True
)
all_splits = text_splitter.split_documents(docs)

vector_store = InMemoryVectorStore(embeddings)

_ = vector_store.add_documents(all_splits)
print('indexing done')

template ="""Use the following context to provide a clear and accurate answer to the question below.  
- If the answer is not found in the context, say you don't know—do not guess or make up an answer.  
- Provide a thorough but concise answer in up to **Twenty sentences**.  
- Include relevant details from the context to support your response.  

**Context:**  
{context}  

**Question:**  
{question}  

**Helpful Answer:**  
"""

prompt = PromptTemplate.from_template(template)

total_documents = len(all_splits)
third = total_documents // 3

for i, document in enumerate(all_splits):
    if i < third:
        document.metadata["section"] = "beginning"
    elif i < 2 * third:
        document.metadata["section"] = "middle"
    else:
        document.metadata["section"] = "end"


class Search(TypedDict):
    """Search query."""

    query: Annotated[str, ..., "Search query to run."]
    section: Annotated[
        Literal["beginning", "middle", "end"],
        ...,
        "Section to query.",
    ]

class State(TypedDict):
    question: str
    # highlight-next-line
    query: Search
    context: List[Document]
    answer: str
    input_type: str  # Added to track the type of input
    input_url: str   # Added to track the source URL


def analyze_query(state: State):
    # Enhance the prompt with additional instructions for decomposition and validation.
    enhanced_instructions = (
        "You are an expert query analyzer. Decompose the following question into its core components. "
        "Extract the main query and, if present, any sub-questions that might require separate handling. "
        "Also determine the document section to search over: 'beginning', 'middle', or 'end'. "
        "Return the result as a JSON with keys 'query' and 'section'.\n"
        "Question: " + state["question"]
    )
    
    structured_llm = llm.with_structured_output(Search)
    result = structured_llm.invoke(enhanced_instructions)    
    return {"query": result}


def retrieve(state: State):
    # highlight-start
    query = state["query"]
    retrieved_docs = vector_store.similarity_search(
        query["query"],
        filter=lambda doc: doc.metadata.get("section") == query["section"],
    )
    # highlight-end
    return {"context": retrieved_docs}


def generate(state: State):
    docs_content = "\n\n".join(doc.page_content for doc in state["context"])
    messages = prompt.invoke({"question": state["question"], "context": docs_content})
    response = llm.invoke(messages)
    
    # Get input type and URL from query.json if available
    input_type = state.get("input_type", "")
    input_url = state.get("input_url", "")
    
    try:
        with open('./query/query.json', 'r', encoding='utf-8') as file:
            query_data = json.load(file)
            if "input_type" in query_data:
                input_type = query_data["input_type"]
            if "input_url" in query_data:
                input_url = query_data["input_url"]
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    
    # Save result to JSON
    result_data = {
        "query": state["question"],
        "retrieved_context": [doc.page_content for doc in state["context"]],
        "answer": response.content,
        "input_type": input_type,
        "input_url": input_url
    }

    # Ensure output directory exists
    os.makedirs('./output', exist_ok=True)
    
    with open('./output/result.json', 'w', encoding='utf-8') as file:
        json.dump(result_data, file, indent=4)

    print('Result saved to output/result.json')
    return {
        "answer": response.content,
        "input_type": input_type,
        "input_url": input_url
    }


# highlight-start
graph_builder = StateGraph(State).add_sequence([analyze_query, retrieve, generate])
graph_builder.add_edge(START, "analyze_query")
# highlight-end
graph = graph_builder.compile()


def run_rag():
    # Load the query from query.json
    input_type = ""
    input_url = ""
    question = ""
    
    try:
        with open('./query/query.json', 'r', encoding='utf-8') as file:
            query_data = json.load(file)
            question = query_data.get("query", "")
            input_type = query_data.get("input_type", "")
            input_url = query_data.get("input_url", "")
    except (FileNotFoundError, json.JSONDecodeError):
        print("Error: query.json not found or invalid")
        return

    # Stream the graph using the loaded query
    for step in graph.stream(
        {
            "question": question,
            "input_type": input_type,
            "input_url": input_url
        },
        stream_mode="updates",
    ):
        print(f"{step}\n\n----------------\n")
        
if __name__ == "__main__":
    run_rag()