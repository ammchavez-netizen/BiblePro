"""Local embedding models. Default: BAAI/bge-m3 (multilingual, runs offline).

Models are downloaded once from Hugging Face into  data/models/  and then
loaded from disk; nothing is sent to an embedding API.

Adding a model later = adding an entry to EMBEDDING_MODELS (any
sentence-transformers compatible Hugging Face model works).
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

DEFAULT_EMBEDDING_MODEL = "BAAI/bge-m3"


@dataclass(frozen=True)
class EmbeddingSpec:
    model_id: str
    display_name: str
    dim: int
    multilingual: bool
    approx_download_gb: float
    max_seq_length: int = 256           # verses are short; keeps indexing fast
    query_prefix: str = ""              # some models want "query: " etc.
    doc_prefix: str = ""
    kind: str = "sentence-transformers"


EMBEDDING_MODELS: dict[str, EmbeddingSpec] = {
    "BAAI/bge-m3": EmbeddingSpec("BAAI/bge-m3", "BGE-M3 (multilingual, 100+ languages)", 1024, True, 2.3),
    "intfloat/multilingual-e5-small": EmbeddingSpec(
        "intfloat/multilingual-e5-small", "Multilingual E5 Small (lighter, faster)", 384, True, 0.5,
        query_prefix="query: ", doc_prefix="passage: "),
    # Offline stand-in used by the automated tests; not meaningful for real use.
    "test/hashing": EmbeddingSpec("test/hashing", "Test only: keyword hashing", 256, False, 0.0, kind="hashing"),
}


class EmbeddingError(RuntimeError):
    pass


class Embedder:
    """Lazy wrapper: nothing heavy is imported until the model is first used."""

    def __init__(self, model_id: str, models_dir: Path, device: Optional[str] = None):
        if model_id not in EMBEDDING_MODELS:
            raise EmbeddingError(f"Unknown embedding model: {model_id}")
        self.spec = EMBEDDING_MODELS[model_id]
        self.models_dir = Path(models_dir)
        self.device = device
        self._model = None

    # ------------------------------------------------------------ files
    @property
    def local_dir(self) -> Path:
        return self.models_dir / self.spec.model_id.replace("/", "__")

    def is_downloaded(self) -> bool:
        if self.spec.kind == "hashing":
            return True
        has_weights = any(self.local_dir.glob("*.safetensors")) or any(self.local_dir.glob("pytorch_model*.bin"))
        return (self.local_dir / "config.json").exists() and has_weights

    def _downloaded_bytes(self) -> int:
        total = 0
        for f in self.local_dir.rglob("*"):
            try:
                if f.is_file():
                    total += f.stat().st_size
            except OSError:
                pass
        return total

    def download(self, progress: Callable[[str], None] = lambda m: None):
        """Download the model files (only once). Raises EmbeddingError on failure.

        Hugging Face models like BAAI/bge-m3 are public: no account or login is needed.
        """
        if self.spec.kind == "hashing" or self.is_downloaded():
            return
        import os
        import threading
        # Console progress bars crash when the app runs without a console (pythonw.exe).
        os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
        try:
            from huggingface_hub import snapshot_download
            try:
                from huggingface_hub.utils import disable_progress_bars
                disable_progress_bars()
            except ImportError:
                pass
        except ImportError as exc:
            raise EmbeddingError("Missing package 'huggingface_hub'. Run: pip install -r requirements-ai.txt") from exc

        total_gb = self.spec.approx_download_gb
        progress(f"Downloading {self.spec.model_id} (~{total_gb} GB) from Hugging Face…")
        done = threading.Event()

        def report():                       # show how much has arrived, every 2 seconds
            while not done.wait(2.0):
                gb = self._downloaded_bytes() / 1e9
                progress(f"Downloading {self.spec.model_id}: {gb:.2f} of ~{total_gb} GB")

        watcher = threading.Thread(target=report, daemon=True)
        watcher.start()
        try:
            snapshot_download(
                repo_id=self.spec.model_id, local_dir=str(self.local_dir),
                # ONNX copies and the ColBERT/sparse heads are not needed for dense vectors.
                ignore_patterns=["onnx/*", "*.onnx", "*.onnx_data", "colbert_linear.pt",
                                 "sparse_linear.pt", "imgs/*", "*.md"])
        except Exception as exc:
            raise EmbeddingError(f"Model download failed: {type(exc).__name__}: {exc}") from exc
        finally:
            done.set()
        if not self.is_downloaded():
            raise EmbeddingError("Model download finished but the model files are incomplete. Try again.")
        progress("Download complete.")

    # ------------------------------------------------------------ encode
    def load(self):
        if self._model is not None or self.spec.kind == "hashing":
            return
        if not self.is_downloaded():
            raise EmbeddingError(f"{self.spec.model_id} is not downloaded yet.")
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise EmbeddingError(
                "Missing packages for local embeddings. Run: pip install -r requirements-ai.txt") from exc
        try:
            self._model = SentenceTransformer(str(self.local_dir), device=self.device)
            self._model.max_seq_length = self.spec.max_seq_length
        except MemoryError as exc:
            raise EmbeddingError("Not enough memory to load the embedding model.") from exc

    def encode_documents(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        return self._encode([self.spec.doc_prefix + t for t in texts], batch_size)

    def encode_query(self, text: str) -> list[float]:
        return self._encode([self.spec.query_prefix + text], 1)[0]

    def _encode(self, texts, batch_size):
        if self.spec.kind == "hashing":
            return [_hash_vector(t, self.spec.dim) for t in texts]
        self.load()
        vecs = self._model.encode(texts, batch_size=batch_size, normalize_embeddings=True,
                                  convert_to_numpy=True, show_progress_bar=False)
        return vecs.tolist()


_TOKEN = re.compile(r"\w+", re.UNICODE)


def _hash_vector(text: str, dim: int) -> list[float]:
    v = [0.0] * dim
    for tok in _TOKEN.findall(text.casefold()):
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        v[h % dim] += 1.0 if (h >> 8) & 1 else -1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]
