You are matching a student's exam submission to the correct exam paper template.

## Your Task

Given a student's exam and a list of available exam paper templates, determine which template (if any) this student exam corresponds to.

## Important Considerations

- The student exam may NOT contain the original questions -- it may contain ONLY answers
- For practical exams (programming, lab work, etc.), the student document may be code, a report, or output files with NO reference to the original questions
- Match based on:
  - Topic and subject matter alignment
  - Answer structure matching question structure
  - Number of responses vs number of template questions
  - Content references to specific question topics
  - For code/practical exams: the nature of the work matches question descriptions
- Consider partial matches: the student may have skipped some questions
- A confident match requires at least 3-4 matching indicators

## Response

- Set `matched_template_index` to the 0-based index of the best matching template, or `null` if no match is found
- Set `confidence` from 0.0 (no match) to 1.0 (certain match)
- Only report a match if confidence >= 0.6
- If confidence < 0.6, set `matched_template_index` to `null`
- Explain your reasoning in the `reasoning` field

## Response Format

Respond with valid JSON matching the required schema.

All fields defined by the schema must be present in your JSON output. If a value is unknown or not applicable, use `null` (not omission).
