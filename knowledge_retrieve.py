from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document
from typing import Literal, TypedDict, List
from typing_extensions import Annotated
from langgraph.graph import START, StateGraph
from langchain_core.vectorstores import InMemoryVectorStore
import json
import os
import logging
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("knowledge_retrieve.log", mode='a'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Define global TypedDicts
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
    query: Search
    context: List[Document]
    answer: str
    input_type: str  # Added to track the type of input
    input_url: str   # Added to track the source URL

# Define the RAG pipeline as a class to prevent caching issues
class RAGPipeline:
    def __init__(self):
        logger.info("Initializing new RAG Pipeline instance")
        
        # Initialize LLM
        self.llm = ChatGroq(
            model='llama3-70b-8192',
            temperature=0.7,
            max_tokens=1024,
            api_key='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'
        )

        # Initialize embeddings
        self.embeddings = HuggingFaceEmbeddings(model_name='sentence-transformers/all-mpnet-base-v2')
        
        # Create necessary directories
        os.makedirs('./data', exist_ok=True)
        os.makedirs('./query', exist_ok=True)
        os.makedirs('./output', exist_ok=True)
        
        # Define template for RAG
        self.template = """Use the following context to provide a clear and accurate answer to the question below.  
- If the answer is not found in the context, say you don't know—do not guess or make up an answer.  
- Provide a thorough but concise answer in up to **Twenty sentences**.  
- Include relevant details from the context to support your response.  

**Context:**  
{context}  

**Question:**  
{question}  

**Helpful Answer:**  
"""
        self.prompt = PromptTemplate.from_template(self.template)
        self.vector_store = None
        self.all_splits = []
        self.graph = None
        
        # Load and prepare documents
        self._prepare_documents()
        self._build_graph()

    def _prepare_documents(self):
        """Load and prepare documents from the data directory"""
        try:
            # Check if data directory has any txt files
            if not os.path.exists('./data'):
                os.makedirs('./data', exist_ok=True)
                
            txt_files_exist = any(
                file.endswith('.txt') 
                for file in os.listdir('./data') 
                if os.path.isfile(os.path.join('./data', file))
            )
            
            if not txt_files_exist:
                logger.warning("No .txt files found in ./data directory. Creating a sample document.")
                with open('./data/sample_document.txt', 'w', encoding='utf-8') as f:
                    f.write("This is a sample document created automatically because no documents were found.\n")
                    f.write("You can replace this with your actual content or add more documents to the data directory.")
            
            loader = DirectoryLoader(
                path='./data',
                glob='**/*.txt',
                loader_cls=TextLoader,
                loader_kwargs={'encoding': 'utf-8'}
            )
            docs = loader.load()
            logger.info(f"Loaded {len(docs)} documents from ./data directory")
            
        except Exception as e:
            logger.error(f"Error loading documents: {str(e)}")
            # Create a default document when loading fails
            docs = [Document(
                page_content="This is a default document created when document loading failed.",
                metadata={"source": "default"}
            )]
            logger.info("Created a default document due to loading failure")

        # Split documents
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            add_start_index=True
        )
        self.all_splits = text_splitter.split_documents(docs)
        logger.info(f"Split documents into {len(self.all_splits)} chunks")

        # Create vector store
        self.vector_store = InMemoryVectorStore(self.embeddings)

        # Add documents to vector store
        _ = self.vector_store.add_documents(self.all_splits)
        logger.info('Indexing completed successfully')
        
        # Add section metadata to documents
        total_documents = len(self.all_splits)
        if total_documents > 0:
            third = max(1, total_documents // 3)
            
            for i, document in enumerate(self.all_splits):
                if i < third:
                    document.metadata["section"] = "beginning"
                elif i < 2 * third:
                    document.metadata["section"] = "middle"
                else:
                    document.metadata["section"] = "end"
            logger.info("Added section metadata to documents")

    def analyze_query(self, state: State):
        """Analyze and structure the query for better retrieval"""
        logger.info(f"Analyzing query: {state['question']}")
        
        # Enhance the prompt with additional instructions for decomposition and validation.
        enhanced_instructions = (
            "You are an expert query analyzer. Decompose the following question into its core components. "
            "Extract the main query and, if present, any sub-questions that might require separate handling. "
            "Also determine the document section to search over: 'beginning', 'middle', or 'end'. "
            "Return the result as a JSON with keys 'query' and 'section'.\n"
            "Question: " + state["question"]
        )
        
        structured_llm = self.llm.with_structured_output(Search)
        result = structured_llm.invoke(enhanced_instructions)
        logger.info(f"Analyzed query result: {result}")
        return {"query": result}

    def retrieve(self, state: State):
        """Retrieve relevant documents based on query"""
        logger.info(f"Retrieving documents for query: {state['query']['query']}, section: {state['query']['section']}")
        
        try:
            query = state["query"]
            retrieved_docs = self.vector_store.similarity_search(
                query["query"],
                filter=lambda doc: doc.metadata.get("section") == query["section"],
            )
            logger.info(f"Retrieved {len(retrieved_docs)} documents")
            return {"context": retrieved_docs}
        except Exception as e:
            logger.error(f"Error during document retrieval: {str(e)}")
            # Return empty context if retrieval fails
            return {"context": []}

    def generate(self, state: State):
        """Generate answer based on retrieved context"""
        logger.info("Generating answer based on retrieved context")
        
        # Get input type and URL from query.json if available
        input_type = state.get("input_type", "")
        input_url = state.get("input_url", "")
        
        try:
            if state["context"]:
                docs_content = "\n\n".join(doc.page_content for doc in state["context"])
                messages = self.prompt.invoke({"question": state["question"], "context": docs_content})
                response = self.llm.invoke(messages)
                answer = response.content
                logger.info("Answer generated successfully")
            else:
                answer = "I couldn't find relevant information to answer your question based on the available documents."
                logger.warning("No context available, returning default answer")
        except Exception as e:
            logger.error(f"Error generating answer: {str(e)}")
            answer = "An error occurred while generating the answer. Please try again."
        
        # Try to load input_type and input_url from query.json
        try:
            with open('./query/query.json', 'r', encoding='utf-8') as file:
                query_data = json.load(file)
                if "input_type" in query_data:
                    input_type = query_data["input_type"]
                if "input_url" in query_data:
                    input_url = query_data["input_url"]
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Error reading query.json: {str(e)}")
        
        # Save result to JSON with timestamp to prevent caching issues
        result_data = {
            "query": state["question"],
            "retrieved_context": [doc.page_content for doc in state["context"]] if state["context"] else [],
            "answer": answer,
            "input_type": input_type,
            "input_url": input_url,
            "timestamp": time.time()  # Add timestamp to prevent caching
        }
        
        try:
            # Clear any previous result.json to ensure fresh data
            if os.path.exists('./output/result.json'):
                os.remove('./output/result.json')
                
            with open('./output/result.json', 'w', encoding='utf-8') as file:
                json.dump(result_data, file, indent=4)
            logger.info('Result saved to output/result.json')
        except Exception as e:
            logger.error(f"Error saving result.json: {str(e)}")
        
        return {
            "answer": answer,
            "input_type": input_type,
            "input_url": input_url
        }

    def _build_graph(self):
        """Build and compile the graph for the RAG pipeline"""
        graph_builder = StateGraph(State)
        
        # Add nodes
        graph_builder.add_node("analyze_query", self.analyze_query)
        graph_builder.add_node("retrieve", self.retrieve)
        graph_builder.add_node("generate", self.generate)
        
        # Add edges
        graph_builder.add_edge("analyze_query", "retrieve")
        graph_builder.add_edge("retrieve", "generate")
        graph_builder.add_edge(START, "analyze_query")
        
        # Compile graph
        self.graph = graph_builder.compile()
        logger.info("Graph compiled successfully")

    def run(self, query=None, input_type="", input_url=""):
        """Run the RAG pipeline with the given query or from query.json"""
        logger.info("Starting RAG pipeline execution")
        
        # If query is not provided, load from query.json
        if query is None:
            try:
                if os.path.exists('./query/query.json'):
                    with open('./query/query.json', 'r', encoding='utf-8') as file:
                        query_data = json.load(file)
                        query = query_data.get("query", "")
                        input_type = query_data.get("input_type", "")
                        input_url = query_data.get("input_url", "")
                        logger.info(f"Loaded query from query.json: {query}")
                else:
                    logger.warning("query.json not found")
                    query = "What is this document about?"
                    logger.info(f"Using default question: {query}")
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logger.error(f"Error reading query.json: {str(e)}")
                query = "What is this document about?"
                logger.info(f"Using default question due to error: {query}")
        else:
            # Save the provided query to query.json
            os.makedirs('./query', exist_ok=True)
            with open('./query/query.json', 'w', encoding='utf-8') as file:
                json.dump({
                    "query": query,
                    "input_type": input_type,
                    "input_url": input_url,
                    "timestamp": time.time()  # Add timestamp to prevent caching
                }, file, indent=4)
            logger.info(f"Saved new query to query.json: {query}")

        # Stream the graph using the loaded query
        try:
            logger.info("Streaming graph execution")
            final_state = None
            for step in self.graph.stream(
                {
                    "question": query,
                    "input_type": input_type,
                    "input_url": input_url
                },
                stream_mode="updates",
            ):
                current_node = list(step.keys())[0] if step else "unknown"
                logger.info(f"Completed node: {current_node}")
                print(f"{step}\n\n----------------\n")
                final_state = step
                
            logger.info("RAG pipeline completed successfully")
            return final_state.get("generate", {}).get("answer", "No answer generated") if final_state else "Pipeline completed but no result was produced"
        except Exception as e:
            logger.error(f"Error in graph execution: {str(e)}")
            print(f"Error: {str(e)}")
            return f"Error: {str(e)}"

# Create a function to run RAG that can be imported by other modules
def run_rag(query=None, input_type="", input_url=""):
    """Run the RAG pipeline with the given query or from query.json"""
    # Create a new pipeline instance for each query to prevent caching issues
    pipeline = RAGPipeline()
    return pipeline.run(query, input_type, input_url)

# Run the script if it's the main module
if __name__ == "__main__":
    run_rag()
