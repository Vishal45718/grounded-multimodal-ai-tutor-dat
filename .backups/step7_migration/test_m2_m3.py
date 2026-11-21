import argparse
import sys
from retrieval.retriever import TutorRetriever
from generation.answer import generate_grounded_answer
try:
    from llama_index.llms.openai import OpenAI
except ImportError:
    OpenAI = None

def main():
    parser = argparse.ArgumentParser(description="Test M2 and M3 (Retrieval and Generation)")
    parser.add_argument("--query", type=str, required=True, help="Question to ask the tutor")
    args = parser.parse_args()

    print("Loading active chunks and building indices (M2)...")
    try:
        retriever = TutorRetriever(use_dense=True, use_sparse=True)
    except Exception as e:
        print(f"Failed to initialize retriever: {e}")
        sys.exit(1)
        
    print("Retrieving evidence and generating grounded answer (M3)...")
    llm = OpenAI(model="gpt-4o-mini") if OpenAI else None
    try:
        answer, citations = generate_grounded_answer(args.query, retriever, llm)
    except Exception as e:
        print(f"Failed to generate answer: {e}")
        sys.exit(1)

    print("\n--- Answer ---")
    print(answer)
    print("\n--- Citations ---")
    for c in citations:
        if c['citation_label'] in answer:
            print(f"{c['citation_label']}: Source {c['source_id']} @ {c['start_sec']}s - {c['end_sec']}s ({c['modality']})")

if __name__ == "__main__":
    main()
