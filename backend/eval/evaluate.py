import json
from rag.retriever import retrieve_chunks
from ingestion.filter import get_valid_files
from config import REPOS_DIR
from rag.llm_pipeline import detect_mode

def is_match(file_path, expected):
    file_path = file_path.lower()
    return any(exp.lower() in file_path for exp in expected)
        
def evaluate(repo_id: str):
    repo_path = REPOS_DIR / "7bff1db3e2a66f5c65235d0a0503274d"
    files = get_valid_files(repo_path)
    # Generic: count useful source files
    source_files = [
        f for f in files
        if "node_modules" not in str(f)
        and "test" not in str(f).lower()
        and "docs" not in str(f).lower()
    ]

    print(f"[INFO] Actual source files ingested: {len(source_files)}")
    for f in source_files:
            print(f)
    with open("eval/questions.json") as f:
        data = json.load(f)

    for item in data:
        question = item["question"]
        expected = item["expected_files"]

        # Detect mode same way the pipeline does
        mode = detect_mode(question)
        chunks = retrieve_chunks(question, repo_id, mode=mode)

        retrieved_files = [
            c["metadata"]["file_path"].lower()
            for c in chunks
        ]

    retrieval_hits = 0
    mrr_total = 0
    precision_total = 0
    recall_total = 0
    total = len(data)

    for item in data:
        question = item["question"]
        expected = item["expected_files"]
        mode = detect_mode(question)
        chunks = retrieve_chunks(question, repo_id, mode=mode)

        retrieved_files = list({
            c["metadata"]["file_path"].lower()
            for c in chunks
        })

        # Check if expected file is in retrieved

        hit = any(is_match(f, expected) for f in retrieved_files)
        
        if hit:
            retrieval_hits += 1
        rank = None
        for i, f in enumerate(retrieved_files):
            if is_match(f, expected):
                rank = i + 1
                break

        score = 1 / rank if rank else 0
        mrr_total += score

        # Precision & Recall
        relevant_retrieved = sum(
            1 for f in retrieved_files if is_match(f, expected)
        )

        precision = relevant_retrieved / len(retrieved_files) if retrieved_files else 0
        unique_matches = set()

        for f in retrieved_files:
            for exp in expected:
                if exp.lower() in f:
                    unique_matches.add(exp.lower())

        recall = len(unique_matches) / len(expected) if expected else 0
        precision_total += precision
        recall_total += recall

        print("\nQ:", question)
        print("Retrieved:", retrieved_files)
        print("Hit:", hit)

    print("\n=== RESULTS ===")
    print(f"Retrieval Accuracy: {retrieval_hits}/{total} = {retrieval_hits/total:.2f}")
    print(f"MRR: {mrr_total / total:.2f}")
    print(f"Precision@k: {precision_total / total:.2f}")
    print(f"Recall@k: {recall_total / total:.2f}")

if __name__ == "__main__":
    repo_id = "7bff1db3e2a66f5c65235d0a0503274d"
    evaluate(repo_id)