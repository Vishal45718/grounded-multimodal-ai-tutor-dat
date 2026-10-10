from llama_index.core.llms import ChatMessage
# Assuming the user has openai or another LLM configured in LlamaIndex.
from llama_index.llms.openai import OpenAI
from retrieval.retriever import TutorRetriever

def generate_grounded_answer(query: str, retriever: TutorRetriever, llm=None):
    if llm is None:
        llm = OpenAI(model="gpt-4o-mini")

    nodes = retriever.retrieve(query, fusion=True)
    if not nodes:
        return "I abstain from answering because no relevant material was found.", []

    context_str = "\n\n".join([
        f"--- Evidence {i+1} ---\n"
        f"Source: {n.metadata.get('source_id')}\n"
        f"Modality: {n.metadata.get('modality')}\n"
        f"Timestamp: {n.metadata.get('start_sec')} - {n.metadata.get('end_sec')}\n"
        f"Text: {n.get_content()}"
        for i, n in enumerate(nodes)
    ])

    prompt = f"""You are an AI tutor. You must answer the user's query ONLY using the provided evidence. 
If the evidence does not support answering the query, explicitly abstain by saying "I abstain...".
When making a claim, you MUST cite the exact evidence number [Evidence X] inline.

Query: {query}

Evidence Context:
{context_str}

Answer:"""

    response = llm.complete(prompt)
    
    # Extract citations
    citations = []
    for i, n in enumerate(nodes):
        citations.append({
            "citation_label": f"[Evidence {i+1}]",
            "source_id": n.metadata.get('source_id'),
            "modality": n.metadata.get('modality'),
            "start_sec": n.metadata.get('start_sec'),
            "end_sec": n.metadata.get('end_sec'),
            "image_path": n.metadata.get('image_path')
        })

    return response.text, citations

