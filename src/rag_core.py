from langchain_community.embeddings import HuggingFaceBgeEmbeddings

def initialize_embeddings():
    print("🚀 Loading local Embedding model on GPU...")
    
    # Using BGE-M3 because it excels in technical texts and hybrid search
    model_name = "BAAI/bge-m3" 
    
    # Directing the workload to the GPU (CUDA) for speed
    model_kwargs = {'device': 'cuda'} 
    encode_kwargs = {'normalize_embeddings': True}
    
    embeddings = HuggingFaceBgeEmbeddings(
        model_name=model_name,
        model_kwargs=model_kwargs,
        encode_kwargs=encode_kwargs
    )
    
    return embeddings

# For standalone testing
if __name__ == "__main__":
    emb = initialize_embeddings()
    print("✅ Successfully initialized! GPU is ready for heavy lifting.")