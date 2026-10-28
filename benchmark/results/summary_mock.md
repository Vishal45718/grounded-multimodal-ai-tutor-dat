# Modality and Perturbation Evaluation Report

- **Execution Mode**: `mock`
- **Vision Backend**: `mock`
- **Total Visual Cases**: 5
- **Modality Conditions Evaluated**: Transcript-only, OCR-only, Visual-input
- **Perturbation Tests Evaluated**: Correct image, Removed image, Swapped image

## 1. Modality Breakdown

| Condition | Cases Tested | Correct | Abstained | Incorrect |
|-----------|--------------|---------|-----------|-----------|
| transcript_only | 5 | 0 | 5 | 0 |
| ocr_only | 5 | 0 | 5 | 0 |
| visual_input | 5 | 5 | 0 | 0 |

## 2. Image Perturbation Results

| Perturbation Test | Cases Tested | Safe Abstention / Rejection | Silent False Acceptance |
|-------------------|--------------|-----------------------------|-------------------------|
| correct_image | 5 | 5 | 0 |
| removed_image | 5 | 5 | 0 |
| swapped_image | 5 | 5 | 0 |
