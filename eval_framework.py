import os
import json
import time
import pandas as pd
import streamlit as st

# --- 1. Bootstrap Secrets for CLI Execution ---
openai_key = os.environ.get("OPENAI_API_KEY")

if not openai_key:
    # Manually parse secrets.toml to avoid external dependencies or StreamlitSecretNotFoundError
    paths = [
        ".streamlit/secrets.toml",
        "secrets.toml",
        os.path.expanduser("~/.streamlit/secrets.toml")
    ]
    for path in paths:
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    for line in f:
                        if "=" in line and not line.strip().startswith("#"):
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip('"').strip("'")
                            if k == "OPENAI_API_KEY":
                                openai_key = v
                                break
            except Exception:
                pass

if openai_key:
    os.environ["OPENAI_API_KEY"] = openai_key
    os.environ["STREAMLIT_OPENAI_API_KEY"] = openai_key
else:
    raise ValueError("⚠️ OPENAI_API_KEY not found in environment variables or secrets.toml.")

from extractor import extract_event_info, is_url, scrape_url

# --- 2. Curated Test Cases with Ground Truths ---
TEST_CASES = [
    {
        "id": "TC_1",
        "description": "General event with explicit start and end times",
        "input": "Photography workshop in Zurich on June 15, 6-9pm",
        "ground_truth": {
            "title": "Photography workshop",
            "start_time": "18:00",
            "end_time": "21:00",
            "category": "Social",
            "price": "Free",
            "location": "Zurich"
        }
    },
    {
        "id": "TC_2",
        "description": "Event missing end time (Should default to start + 2 hours)",
        "input": "test event today at 11pm",
        "ground_truth": {
            "title": "test event",
            "start_time": "23:00",
            "end_time": "01:00",  # Defaults to 2 hours later (next day rollover)
        }
    },
    {
        "id": "TC_3",
        "description": "Apartment viewing schedule parsing",
        "input": "Apartment visit scheduled for July 5th at 17:30 at Main Street 12, 8001 Zurich. Rent is 2500 CHF/month.",
        "ground_truth": {
            "title": "Apartment Viewing: Main Street 12",
            "start_time": "17:30",
            "end_time": "18:00",  # Defaults to 30 mins
            "category": "Apartment Viewing",
            "price": "2500 CHF/month",
            "location": "Main Street 12, 8001 Zurich",
            "available_from": None,
            "monthly_rent": "2500",
            "source": None
        }
    },
    {
        "id": "TC_4",
        "description": "Apartment viewing with source in text and availability date",
        "input": "Found an apartment on flatfox.ch! Visit is on Oct 12 at 10:00. Address: Bernstrasse 4, 3000 Bern. Monthly rent is 1850 CHF. Available from 2026-11-01.",
        "ground_truth": {
            "title": "Apartment Viewing: Bernstrasse 4",
            "start_time": "10:00",
            "end_time": "10:30",
            "category": "Apartment Viewing",
            "price": "1850 CHF",
            "location": "Bernstrasse 4, 3000 Bern",
            "available_from": "2026-11-01",
            "monthly_rent": "1850",
            "source": "Flatfox"
        }
    }
]

def run_evaluation(model_name: str = "gpt-4o-2024-08-06"):
    """Runs extraction for all test cases and evaluates them using RAGAS."""
    print(f"\n[INFO] Running evaluations using model: {model_name}...")
    
    questions = []
    contexts = []
    answers = []
    ground_truths = []
    
    for case in TEST_CASES:
        print(f"  Processing Case {case['id']}: {case['description']}...")
        
        # 1. Capture question & contexts
        lines = [ln.strip() for ln in case["input"].splitlines() if ln.strip()]
        urls = [ln for ln in lines if is_url(ln)]
        
        scraped_contents = []
        for url in urls:
            scraped = scrape_url(url)
            scraped_contents.append(scraped)
            
        context_text = case["input"]
        if scraped_contents:
            context_text += "\n\nScraped:\n" + "\n\n".join(scraped_contents)
            
        # 2. Run extraction
        try:
            extracted_list = extract_event_info(case["input"], model=model_name)
            # Serialize the extracted details to a clean format for evaluation
            extracted_data = [e.model_dump() for e in extracted_list]
            answer_str = json.dumps(extracted_data, indent=2)
        except Exception as e:
            answer_str = f"Error: {e}"
            
        questions.append(case["input"])
        contexts.append([context_text])
        answers.append(answer_str)
        ground_truths.append(json.dumps(case["ground_truth"], indent=2))
        
        # Avoid hitting API rate limits in rapid succession
        time.sleep(1)
        
    # --- 3. Evaluate using RAGAS ---
    try:
        from ragas import evaluate
        from datasets import Dataset
        from ragas.metrics import faithfulness, answer_relevance
        
        # Construct RAGAS dataset
        data_dict = {
            "question": questions,
            "contexts": contexts,
            "answer": answers,
            "ground_truth": ground_truths
        }
        dataset = Dataset.from_dict(data_dict)
        
        print("\n[INFO] Calling RAGAS judge to calculate metrics...")
        result = evaluate(
            dataset=dataset,
            metrics=[faithfulness, answer_relevance]
        )
        
        # Print final report
        df = result.to_pandas()
        print("\n=======================================================")
        print(f"RAGAS Evaluation Summary ({model_name})")
        print("=======================================================")
        print(df[["question", "faithfulness", "answer_relevance"]].to_string(index=False))
        print("-------------------------------------------------------")
        print(f"Mean Faithfulness:      {df['faithfulness'].mean():.4f}")
        print(f"Mean Answer Relevance:  {df['answer_relevance'].mean():.4f}")
        print("=======================================================")
        
        return df
    except ImportError:
        print("\n[WARNING] Ragas or Datasets is not installed. Here is the raw extracted output for manual comparison:")
        for q, a, gt in zip(questions, answers, ground_truths):
            print(f"\nPrompt: {q}")
            print(f"Extracted:\n{a}")
            print(f"Ground Truth:\n{gt}")
            print("-" * 50)
    except Exception as e:
        print(f"\n[ERROR] RAGAS evaluation failed: {e}")

if __name__ == "__main__":
    if not os.environ.get("OPENAI_API_KEY"):
        print("[WARNING] OPENAI_API_KEY environment variable or secrets.toml not found. Please configure it before running.")
    else:
        # Compare multiple models
        models = ["gpt-4o-mini", "gpt-4.1-nano"]
        for model in models:
            run_evaluation(model)
            print("\n" + "="*60 + "\n")
