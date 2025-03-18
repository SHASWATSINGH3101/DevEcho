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
- If the answer is not found in the context, say you don’t know—do not guess or make up an answer.  
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


all_splits[0].metadata





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


# highlight-next-line
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
    
    # Save result to JSON
    result_data = {
        "query": state["question"],
        "retrieved_context": [doc.page_content for doc in state["context"]],
        "answer": response.content
    }

    with open('./output/result.json', 'w', encoding='utf-8') as file:
        json.dump(result_data, file, indent=4)

    print('Result saved to output/result.json')
    return {"answer": response.content}


# highlight-start
graph_builder = StateGraph(State).add_sequence([analyze_query, retrieve, generate])
graph_builder.add_edge(START, "analyze_query")
# highlight-end
graph = graph_builder.compile()


def run_rag():
# Load the query from query.json
    with open('./query/query.json', 'r', encoding='utf-8') as file:
        query_data = json.load(file)

    # Stream the graph using the loaded query
    for step in graph.stream(
        {"question": query_data["query"]},
        stream_mode="updates",
    ):
        print(f"{step}\n\n----------------\n")
if __name__ == "__main__":
    run_rag()