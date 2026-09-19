# Text Line Segmentation & Dynamic Baseline Clustering

**Tags:** #ocr #layout-analysis #computer-vision #algorithms #sih2026 #module1
**Status:** Architecture Design
**Extracted from:** Brainstorm in `Current Ideas` (Dynamic vertical pixel transition thresholding)

---

## 1. The Core Problem: Why Exact Y-Coordinates Fail

When extracting fields from scanned identity documents (e.g. associating `FIRST NAME` with `LAST NAME`, or `MOHAMMED` with `SHAAN`), naive matching using `y1 == y2` fails almost 100% of the time due to:
1. **Micro-skew / Document Tilt:** Even a $0.5^\circ - 1.5^\circ$ tilt causes words on the same line to drift vertically by 10–30 pixels across the page width.
2. **Ascenders and Descenders:** Letters with ascenders (`b, d, h, k, t`) push bounding-box tops higher, while descenders (`g, j, p, q, y`) push bottoms lower.
3. **OCR Bounding Box Jitter:** Engines like Tesseract or PaddleOCR produce slight bounding box boundary noise between adjacent words.

---

## 2. The First-Principles Intuition: Dynamic Vertical Edge Profiling

Instead of guessing a hardcoded vertical pixel tolerance (which breaks when image resolution changes from 72 DPI to 300 DPI), we derive the threshold dynamically from the document's own typography:

### The Mechanism:
1. **Vertical Transition Scanning (Gradient Edges):**
   * Scan vertically across pixel columns in a text band.
   * Background (White) $\to$ Ink (Black): Record start edge $y_{\text{start}}$.
   * Ink (Black) $\to$ Background (White): Record end edge $y_{\text{end}}$.
2. **Line Height / Threshold Extraction:**
   * Stroke span $\Delta y = y_{\text{end}} - y_{\text{start}}$ represents the character height.
   * Averaging $\Delta y$ across a candidate region yields the document's intrinsic font scale (x-height $\bar{h}$).
3. **Dynamic Band Condition:**
   Two words $W_A$ and $W_B$ belong to the **same line / field** if their vertical distance satisfies:
   $$|y_{c, A} - y_{c, B}| \le \alpha \cdot \bar{h}$$
   *(where $y_c$ is the box vertical center, and $\alpha \approx 0.3 - 0.5$).*

---

## 3. Classical Computer Vision Equivalents

This first-principles concept directly aligns with established document processing algorithms:

### A. Horizontal Projection Profile (HPP)
Summing binarized ink pixels row-by-row across the document produces a 1D histogram:
* **Valleys (Zeros):** Inter-line spacing (white gutters between text lines).
* **Peaks (High ink density):** Text lines.
* The peak width gives the exact dynamic threshold for line clustering, naturally immune to font size variations.

```text
Row Pixels      Horizontal Projection
[   INK   ]  ──► ████████████████  (Peak = Line 1)
[  WHITE  ]  ──►                   (Valley = Line Gap)
[   INK   ]  ──► ██████████████    (Peak = Line 2)
```

### B. Vertical 1D-IoU (Intersection-over-Union on Y-Axis)
For pre-extracted OCR bounding boxes $B_1(y_{\text{top1}}, y_{\text{bot1}})$ and $B_2(y_{\text{top2}}, y_{\text{bot2}})$:
$$\text{Overlap}_y = \frac{\max(0, \min(y_{\text{bot1}}, y_{\text{bot2}}) - \max(y_{\text{top1}}, y_{\text{top2}}))}{\min(h_1, h_2)}$$
* If $\text{Overlap}_y \ge 0.50$, both words belong to the exact same text baseline band.

---

## 4. Production Python Implementation for Back-end

Here is the lightweight clustering algorithm to group OCR word tokens into unified lines:

```python
from typing import List, Dict

def cluster_words_into_lines(words: List[Dict], vertical_iou_threshold: float = 0.5) -> List[List[Dict]]:
    """
    Groups OCR word bounding boxes into coherent text lines using dynamic vertical overlap.
    
    words: list of dicts with keys: 'text', 'box' -> [x_min, y_min, x_max, y_max]
    """
    if not words:
        return []

    # Sort words primarily top-to-bottom, secondarily left-to-right
    sorted_words = sorted(words, key=lambda w: (w['box'][1], w['box'][0]))
    
    lines = []
    
    for word in sorted_words:
        w_box = word['box']
        w_top, w_bot = w_box[1], w_box[3]
        w_height = max(1, w_bot - w_top)
        
        matched_line = None
        for line in lines:
            # Compare with average vertical span of the current line
            line_top = min(item['box'][1] for item in line)
            line_bot = max(item['box'][3] for item in line)
            line_height = max(1, line_bot - line_top)
            
            # Calculate 1D Vertical Overlap
            intersection = max(0, min(w_bot, line_bot) - max(w_top, line_top))
            min_height = min(w_height, line_height)
            overlap_ratio = intersection / min_height
            
            if overlap_ratio >= vertical_iou_threshold:
                matched_line = line
                break
                
        if matched_line is not None:
            matched_line.append(word)
        else:
            lines.append([word])
            
    # Sort words within each line left-to-right
    for line in lines:
        line.sort(key=lambda w: w['box'][0])
        
    return lines
```

---

## 5. Integration with the Screening Pipeline

1. **Pre-Processing (Deskew):** Run Hough Line Transform or Min-Area Rect on the document before clustering to eliminate skew angle $\theta$.
2. **Field Reconstruction:** Feed clustered lines into the deterministic normalizer in [[ocr-pipeline-prototype]] to reconstruct split fields (e.g. `SHAAN` + `MOHAMMAD`).
3. **Forensics Link:** If two words on the same printed line have wildly different baseline offsets, flag as potential **Text Manipulation** in [[Document-Forensics-and-Tampering-Detection]].

---

## Related Notes
* [[ocr-pipeline-prototype]]
* [[Document-Forensics-and-Tampering-Detection]]
* [[Deterministic-Validation-ICAO-MRZ-and-Regional-IDs]]
