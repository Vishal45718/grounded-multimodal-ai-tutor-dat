# Benchmark Dataset

This directory contains the first 20 validated benchmark QA cases for the multimodal tutor prototype.
The benchmark is constructed to test the system on real course material from CS50 Lecture 1.

## Schema

Each line in `cases.jsonl` is a JSON object with the following fields:

- `id`: A unique string identifier for the case.
- `question`: The user's query.
- `category`: The type of question (e.g., exact terminology, conceptual/paraphrased, visual, cross-modal, partially supported, unanswerable/off-corpus).
- `expected_answer`: The correct response based strictly on the approved course materials.
- `expected_evidence_ids`: An array of chunk IDs that represent the gold evidence for this answer.
- `expected_source_id`: The ID of the source video/material (e.g., `cs50-lec01`).
- `expected_version_id`: The version ID of the source (e.g., `2024`).
- `answerability`: Indicates if the question is fully answerable (`answerable`), partially answerable (`partial`), or out of scope (`unanswerable`).
- `visual_required`: Boolean. `true` if answering the question requires information that is ONLY present visually (e.g., in a diagram, visual layout, or specific on-screen code that is not read out in the transcript).
- `adversarial_type`: Used for adversarial test cases (currently `null`).
- `notes`: Any context or explanation for the case, mandatory for visual cases to explain why the visual component is essential.

## Labelling Policy

1. **No Fabrication**: All questions, answers, and expected evidence IDs correspond strictly to verified parts of the actual course materials and database.
2. **Visual Cases**: For a case to have `visual_required: true`, the necessary information must *not* be present in the audio transcript. It must be something visual such as a diagram layout, formula on screen, or UI element that is not explicitly described in spoken words.
3. **Off-corpus**: Unanswerable questions have an empty `expected_evidence_ids` array and an `answerability` of `unanswerable`. The expected model behaviour is to abstain.
4. **Partial Support**: Questions where the provided material only partially answers the query are marked `partial`, and the expected answer must distinguish what is supported from what is not.

## Validation

Run `python validate.py` to ensure the dataset meets the schema constraints and references valid database entries.
