# Document Forensics & Tampering Detection

**Tags:** #forensics #computer-vision #ai #tampering #sih2026  #module3
**Deliverable:** Module 3 of PS26188 (Core AI Innovation)

---

## 1. Overview & Objectives

Fraudulent identity documents presented at border checkpoints typically exhibit physical or digital modifications. The goal of this module is to combine **classical computer vision heuristics** with **deep neural forensic models** to detect:
1. Photo Replacement / Splicing
2. Text & Date Alteration
3. Counterfeit / Cloned Immigration Stamps
4. Digital Image & Metadata Manipulation

---

## 2. Multi-Layered Forensic Techniques

### Layer 1: Error Level Analysis (ELA)
* **Principle:** Digital JPEG compression saves images at a specific compression quality. When a document image is tampered with (e.g. replacing a face photo or modifying a birth year in Photoshop), the modified pixels degrade at a different rate when re-saved compared to untouched regions.
* **Mechanism:** 
  1. Re-compress the incoming document at a fixed quality (e.g., 90-95%).
  2. Compute pixel-wise absolute difference between original and re-compressed version.
  3. Scale differences to produce an ELA heatmap.
* **Result:** Spliced photos or altered text shine brightly in the ELA map, signaling distinct compression heritage.

### Layer 2: Copy-Move Forgery Detection (CMFD)
* **Principle:** Fraudsters often copy legitimate security patterns, background Guilloche textures, or stamps from one section of a document to cover up altered regions.
* **Mechanism:**
  1. Extract dense feature keypoints using SIFT / ORB / AKAZE.
  2. Perform spatial nearest-neighbor matching across non-overlapping patches.
  3. Flag duplicate keypoint clusters that indicate cloned textures.

### Layer 3: Font Alignment & Kerning Variance
* **Principle:** Government security documents (passports, visas, national IDs) use strict typographic standards: fixed character spacing, precise baseline alignment, and uniform font weights.
* **Mechanism:**
  1. Extract word and character bounding boxes from high-resolution scan.
  2. Calculate baseline deviation ($\Delta y$) across consecutive characters in names and ID numbers.
  3. Measure stroke width and kerning distribution.
* **Result:** Manually substituted numbers or letters (e.g., changing `1998` to `1990`) reveal noticeable baseline or font-thickness variance.

### Layer 4: Stamp Authenticity & Feature Matching
* **Principle:** Immigration stamps and issuing seals have standardized geometries, official crests, and date bands.
* **Mechanism:**
  1. Detect circular, rectangular, or oval stamp contours using Hough transforms.
  2. Compute keypoint descriptors against a library of authentic SSB / Bureau of Immigration stamp templates.
  3. Evaluate homography and geometric deformation.
* **Result:** Distorted, low-resolution printed, or synthetic stamps fail geometric validation.

### Layer 5: Metadata & EXIF Analysis
* **Principle:** Raw scans or camera captures have consistent EXIF tags, color profiles, and camera sensor noise (PRNU).
* **Checks:**
  - Presence of image editing software signatures (`Photoshop`, `GIMP`, `Canva`, `Apple Photos`).
  - Discrepancy between internal EXIF modification timestamp and creation timestamp.
  - Stripped EXIF metadata flags requiring deeper physical scrutiny.

---

## 3. Forensic Output & Risk Scoring

Each forensic layer outputs a normalized confidence score between `0.0` (clean) and `1.0` (high risk of forgery):

| Layer                  | Technique                       | Output Format            | Weight in Final Score |
| :--------------------- | :------------------------------ | :----------------------- | :-------------------- |
| **Photo Integrity**    | ELA + Boundary Splice Detection | Heatmap + Anomaly Score  | 35%                   |
| **Text Manipulation**  | Baseline & Kerning Deviation    | Coordinate Flags + Score | 30%                   |
| **Stamp Authenticity** | SIFT Keypoint Template Match    | Homography Score         | 20%                   |
| **Metadata Integrity** | EXIF & Software Trace Parser    | Boolean Flags + Score    | 15%                   |

---

## Related Notes
* [[Deterministic-Validation-ICAO-MRZ-and-Regional-IDs]]
* [[Explainable-AI-and-Incident-Dossier]]
* [[PS26188_Problem_Analysis]]
