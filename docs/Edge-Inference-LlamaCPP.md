# Local Edge Inference via llama.cpp

**Tags:** #ai #edge #performance #optimization #sih2026 
**Status:** In Progress
**Extracted from:** Initial brainstorm in `Current Ideas`

---

## 1. Core Problem & Concept

Standard LLM/VLM serving frameworks like **Ollama** run background daemons with substantial memory footprints and generic abstraction layers. On edge devices (border checkpoint rugged laptops, mini-PCs, or portable field kits), resources like RAM and VRAM are strictly constrained.

### The Solution: Direct Native Inference via `llama.cpp`
* **Direct Execution:** Replace daemon abstractions with raw `llama.cpp` (or `llama-cpp-python` / C++ native bindings) using quantized GGUF models.
* **On-Demand Lifecycle (Load-Run-Kill):**
  1. Keep model unloaded or in a cold state while idle.
  2. Load model into memory on-demand when a document scan arrives.
  3. Execute inference for field normalization or visual anomaly check.
  4. Promptly unload/free VRAM or transition to low-power idle.
* **Benefits:**
  - Zero background daemon memory leak.
  - Sub-second cold starts with mmap.
  - Lower thermal throttling and battery consumption on edge hardware.

---

## 2. Quantization & Hardware Target Profile

The backend pipeline is architected to run on any device supporting Python 3.10+, with **Raspberry Pi 4 / Pi 5 (ARM64, 4GB/8GB RAM) as the target lower-bound hardware**. On ARM Cortex-A72/A76, `llama.cpp` compiles with ARM NEON vector instructions for accelerated integer math:

| Model Candidate | Quantization | RAM Footprint | Performance Profile | Best Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **SmolVLM-500M / 2B** | Q4_K_M | ~1.2 GB - 2.5 GB | ~3–6 tok/s on Pi 5 | Ultra-fast document layout verification & stamp check |
| **Qwen2.5-VL-3B-Instruct** | Q4_K_M (GGUF) | ~2.6 GB | Fast on x86, workable on Pi 5 | Visual inspection, multi-lingual OCR, stamp/photo analysis |
| **Qwen2.5-3B-Instruct** | Q4_K_M (GGUF) | ~2.0 GB | ~4–8 tok/s on Pi 5 | Pure text normalization and ambiguous JSON repair |
| **Llama-3.2-3B-Instruct** | Q4_K_M (GGUF) | ~2.1 GB | ~4–7 tok/s on Pi 5 | Schema compliance and fallback verification |

---

## 3. Architecture & Execution Flow

```text
[ Document Image Captured ]
             │
             ▼
   [ Fast OCR / Math Checks ] ────── (Clean Match?) ──► [ Output JSON ]
             │ (Ambiguity / Anomaly Flagged)
             ▼
   [ Load GGUF via llama.cpp ]
             │
             ▼
   [ Run Quantized Inference ]
             │
             ▼
   [ Free Memory / Unload ]
             │
             ▼
   [ Structured Output ]
```

---

## 4. Implementation Steps for Back-end / AI Team

1. **Setup Environment:** Install `llama-cpp-python` with hardware acceleration enabled (CUDA for NVIDIA or OpenBLAS/Vulkan for generic hardware).
2. **Model Storage:** Store `.gguf` weights locally on NVMe storage to maximize memory-mapping speed.
3. **Warm/Cold Cache Management:** Implement a timeout eviction policy (e.g., if no document is scanned within 60 seconds, purge model context from memory).

---

## Related Notes
* [[Vision-Language-Models-VLM-Architecture]]
* [[Offline-First-Store-and-Forward]]
* [[ocr-pipeline-prototype]]
