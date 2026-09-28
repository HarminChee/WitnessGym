# Inject and transform prompt inputs

The construction pipeline is prompt-layered.

## Injection system prompt

Global constraints:

- introduce a real localized production-code bug
- keep a non-empty semantic git diff
- run the replay command verbatim
- do not claim success if the final failure is unrelated
- do not modify tests unless explicitly allowed
- do not change public or protected API signatures

## Injection task payload

Task-specific inputs:

- bug-pattern ID
- bug-pattern name and category
- bug-pattern description
- required elements
- forbidden elements
- expected failure signal hints
- trigger-condition hints
- execution-context summary
- candidate anchors
- allowed or preferred production-file scope

Task-level reporting fields:

- `ok`
- `pattern_id`
- `target_files`
- `target_symbols`
- `selected_anchor`
- `why_this_site`
- `expected_trigger_path`
- `stealth_rationale`
- `bug_mechanism`
- `preserved_prior_structure`
- `possible_risks`

## Transformation task payload

Task-specific inputs:

- internal transform ID
- paper-facing operator name
- operator description and intended effect
- applicability requirements
- forbidden edits
- must-preserve constraints
- post-conditions
- execution-context summary
- candidate anchors

Task-level reporting fields:

- `ok`
- `transform_id`
- `changed_files`
- `edit_sites`
- `what_was_added_or_wrapped`
- `what_was_preserved`
- `what_was_replaced_or_overwritten`
- `compatibility_with_previous_steps`
- `expected_effect_on_stealth`
- `expected_effect_on_trigger_depth`
