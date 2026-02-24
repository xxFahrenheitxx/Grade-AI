You are analyzing a blank exam paper to extract its question structure.

## Your Task

This document is an EXAM PAPER (the official questions, NOT a student submission).
Extract every question with its full details:

1. **Question Title**: The exact title/heading as it appears in the document, in the ORIGINAL LANGUAGE. Do not translate.
2. **Question Number**: Determine the question number (1, 2, 3, etc.)
3. **Points Possible**: If the maximum points for this question are indicated (e.g., "Question 1 (5 pts)"), extract that value. Otherwise, set to null.
4. **Question Text**: The FULL text of the question as it appears in the document. Include all sub-parts, instructions, and constraints.

## Important Notes

- Extract the COMPLETE question text, not just the title
- Include all sub-parts, instructions, constraints, and code snippets in question_text
- Questions may be numbered with digits (1, 2, 3), letters (a, b, c), or Roman numerals (I, II, III)
- Some exams have sub-questions (1a, 1b, 2a, etc.) - treat these as separate questions
- Preserve the exact formatting and original language of question titles
- If the document is handwritten, do your best to read the content
- Report total_points if a grand total is indicated in the document

## Response Format

Respond with valid JSON matching the required schema.

All fields defined by the schema must be present in your JSON output. If a value is unknown or not applicable, use `null` (not omission).
