# Grammar Manual Verification

Low-confidence grammar issues requiring human review.

Format (but don't add a codeblock for each item):

```markdown
- [ ] path/to/file.py:15-17 - "original text"
  Suggestion: "corrected text"
  Reason: brief explanation
```

---

<!-- Issues will be appended below by Claude Code -->

- [ ] docs/running_tests/test_formats/state_test.md:61 - "Mapping of lists of post for verification per fork"
  Suggestion: "Mapping of lists of `FixtureForkPost` for verification per fork" or "Mapping of lists for the `post` field for verification per fork"
  Reason: The word "post" without backticks is ambiguous - unclear if referring to the field name or a technical term
