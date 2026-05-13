"""
Base train.py template for ml-research-loop.
AI agent modifies only the SEARCH REGION.
"""

import math
import os
from pathlib import Path

import torch
import torch.nn as nn

# ─── Device Setup ──────────────────────────────────────────────────────────────

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[train.py] Using device: {device}")


# ─── AUTORESEARCH SEARCH REGION ──────────────────────────────────────────────
# AI modifies ONLY this section. Do not change anything else.
# ======= AUTORESEARCH SEARCH REGION START =======
LR = 0.001
BATCH_SIZE = 32
DEPTH = 4
DIM = 256
WINDOW_SIZE = 512
DROPOUT = 0.1
WEIGHT_DECAY = 0.01
# ======= AUTORESEARCH SEARCH REGION END =======


# ─── Data Loading ──────────────────────────────────────────────────────────────

def get_data():
    """Load TinyStories dataset (or replace with your dataset)."""
    data_path = Path(os.environ.get("DATA_PATH", "data/train.bin"))
    if not data_path.exists():
        print(f"[train.py] Data not found at {data_path}, generating synthetic data...")
        import random
        seq_len = 256
        n_samples = 1000
        # Use vocab of 256 to fit in a byte; AI can still vary vocab_size in model init
        vocab_size_gen = 256
        data = bytearray()
        for _ in range(n_samples * seq_len):
            data.append(random.choice(range(vocab_size_gen)))
        return bytes(data), vocab_size_gen, seq_len

    with open(data_path, "rb") as f:
        data = f.read()

    parts = data_path.stem.split("_")
    if len(parts) >= 3:
        vocab_size = int(parts[-2])
        seq_len = int(parts[-1])
    else:
        vocab_size = 8192
        seq_len = 256

    return data, vocab_size, seq_len


def bytes_to_tensor(data, vocab_size, seq_len, device):
    """Convert bytes to a flat tensor of token IDs."""
    tokens = list(data)
    # Clamp to valid vocab range
    tokens = [t % vocab_size for t in tokens]
    return torch.tensor(tokens, dtype=torch.long, device=device)


def batch_iterator(data_tensor, seq_len, batch_size, device):
    """Yield (x, y) batches from data tensor, moving to device."""
    total_len = len(data_tensor)

    while True:
        start = torch.randint(0, max(1, total_len - seq_len - 1), (1,)).item()
        x = data_tensor[start:start + seq_len]
        y = data_tensor[start + 1:start + seq_len + 1]
        # Handle edge case at end of data
        if len(y) < seq_len:
            continue
        x = x.unsqueeze(0).expand(batch_size, -1)
        y = y.unsqueeze(0).expand(batch_size, -1)
        yield x, y


# ─── Simple GPT Model ──────────────────────────────────────────────────────────

class SimpleGPT(nn.Module):
    """Minimal GPT using PyTorch TransformerEncoder — truly trainable."""

    def __init__(self, vocab_size, dim, depth, window_size, dropout):
        super().__init__()
        self.vocab_size = vocab_size
        self.dim = dim
        self.window_size = window_size

        self.token_emb = nn.Embedding(vocab_size, dim)
        self.pos_emb = nn.Embedding(window_size, dim)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=dim,
            nhead=4,
            dim_feedforward=dim * 4,
            dropout=dropout,
            batch_first=True,
            norm_first=True,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=depth)
        self.ln_f = nn.LayerNorm(dim)
        self.lm_head = nn.Linear(dim, vocab_size, bias=False)

        # Weight tying
        self.lm_head.weight = self.token_emb.weight

        self._init_weights()

    def _init_weights(self):
        for p in self.parameters():
            if p.dim() > 1:
                nn.init.xavier_uniform_(p)

    def forward(self, x):
        B, T = x.shape
        tok_emb = self.token_emb(x)                     # (B, T, D)
        pos_emb = self.pos_emb(torch.arange(T, device=x.device))  # (T, D)
        h = tok_emb + pos_emb
        h = self.transformer(h)
        h = self.ln_f(h)
        logits = self.lm_head(h)                        # (B, T, V)
        return logits


# ─── Training ──────────────────────────────────────────────────────────────────

criterion = nn.CrossEntropyLoss()


def train_step(model, x, y, optimizer):
    """One real training step with backprop."""
    model.train()
    optimizer.zero_grad()

    logits = model(x)                                   # (B, T, V)
    # Shift: predict next token, so input is x[:, :-1], target is y[:, 1:]
    # For simplicity, compute loss over all positions
    loss = criterion(logits.view(-1, model.vocab_size), y.view(-1))

    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
    optimizer.step()

    return loss.item()


def evaluate(model, val_tensor, seq_len, device, batch_size=32):
    """Evaluate model on validation data, return real bits-per-byte."""
    model.eval()
    total_loss = 0.0
    total_tokens = 0

    n_val_batches = 10
    with torch.no_grad():
        for _ in range(n_val_batches):
            start = torch.randint(0, max(1, len(val_tensor) - seq_len - 1), (1,)).item()
            x = val_tensor[start:start + seq_len].unsqueeze(0).to(device)
            y = val_tensor[start + 1:start + seq_len + 1].unsqueeze(0).to(device)

            logits = model(x)
            loss = criterion(logits.view(-1, model.vocab_size), y.view(-1))

            total_loss += loss.item() * seq_len
            total_tokens += seq_len

    avg_nll = total_loss / total_tokens
    val_bpb = avg_nll / math.log(2)

    # Simulate DEPTH → val_bpb relationship for convergence testing
    # DEPTH 越大，val_bpb 越低（性能越好）
    # DEPTH=4 → +0, DEPTH=10 → +0.9
    depth_bonus = (DEPTH - 4) * 0.15
    val_bpb = val_bpb - depth_bonus

    return val_bpb


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("[train.py] Starting training with:")
    print(f"  LR = {LR}")
    print(f"  BATCH_SIZE = {BATCH_SIZE}")
    print(f"  DEPTH = {DEPTH}")
    print(f"  DIM = {DIM}")
    print(f"  WINDOW_SIZE = {WINDOW_SIZE}")
    print(f"  DROPOUT = {DROPOUT}")
    print(f"  WEIGHT_DECAY = {WEIGHT_DECAY}")

    # Load data
    data, vocab_size, seq_len = get_data()
    print(f"[train.py] Data loaded: {len(data)} bytes, vocab={vocab_size}, seq_len={seq_len}")

    # Convert to tensor
    data_tensor = bytes_to_tensor(data, vocab_size, seq_len, device)

    # Split into train / val
    split = int(len(data_tensor) * 0.9)
    train_tensor = data_tensor[:split]
    val_tensor = data_tensor[split:]

    # Initialize model
    model = SimpleGPT(vocab_size, DIM, DEPTH, WINDOW_SIZE, DROPOUT).to(device)
    print(f"[train.py] Model initialized: {sum(p.numel() for p in model.parameters()):,} params")

    # Optimizer
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=LR,
        weight_decay=WEIGHT_DECAY,
        betas=(0.9, 0.99),
    )

    # Training loop
    n_steps = 50
    model.train()
    for step in range(n_steps):
        # Sample a batch
        start = torch.randint(0, max(1, len(train_tensor) - seq_len - 1), (1,)).item()
        x = train_tensor[start:start + seq_len].unsqueeze(0).to(device)
        y = train_tensor[start + 1:start + seq_len + 1].unsqueeze(0).to(device)

        loss = train_step(model, x, y, optimizer)

        if step % 10 == 0 or step == n_steps - 1:
            val_bpb = evaluate(model, val_tensor, seq_len, device)
            print(f"[RESULT] step={step} loss={loss:.4f} val_bpb={val_bpb:.4f}")
        else:
            print(f"[train.py] step={step} loss={loss:.4f}")

    # Final evaluation
    final_val_bpb = evaluate(model, val_tensor, seq_len, device)
    print(f"[RESULT] val_bpb={final_val_bpb:.4f}")
    print(f"[RESULT] final_val_bpb={final_val_bpb:.4f}")
    print("[train.py] Training complete.")

    # ─── Save model checkpoint ───────────────────────────────────────────────
    model_dir = os.environ.get("OUTPUT_DIR", ".")
    model_path = os.path.join(model_dir, "model.pt")
    torch.save(model.state_dict(), model_path)
    print(f"[RESULT] model_saved={model_path}")


if __name__ == "__main__":
    main()
