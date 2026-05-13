"""
Base prepare.py — data preparation script (AI should NOT modify this file).
One-time setup: download data, train tokenizer, prepare binary files.
"""

def main():
    print("[prepare.py] This script prepares the dataset.")
    print("[prepare.py] For demo purposes, train.py generates synthetic data if no data file exists.")
    print("[prepare.py] To use real data:")
    print("  1. Download TinyStories from HuggingFace:")
    print("     https://huggingface.co/datasets/karpathy/tinystories-gpt4-clean")
    print("  2. Tokenize and save as data/train_<vocab>_<seqlen>.bin")
    print("[prepare.py] Example: data/train_8192_256.bin")
    print("[prepare.py] Done.")


if __name__ == "__main__":
    main()
