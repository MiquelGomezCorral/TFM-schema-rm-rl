# Reward Machines: Exploiting Reward Function Structure in Reinforcement Learning

*Rodrigo Toro Icarte, Toryn Q. Klassen, Richard Valenzano, and Sheila A. McIlraith*  
*Journal of Artificial Intelligence Research 73 (2022), 173-208. Submitted October 2020; published January 2022.*

## Combined Extraction

This edition uses the GLM extraction as its body because it preserves the paper's prose, tables, references, and algorithm updates more faithfully. The corrections below recover details that are clearer in the Firered extraction or directly visible in the PDF.

![[RMs-Paper-GLM]]

## PDF-Verified Corrections

### Document Structure

- Treat the numbered section titles in the embedded text as Markdown headings:
  - `# 1. Introduction`
  - `# 2. Reinforcement Learning`
  - `# 3. Reward Machines`
  - `# 4. Exploiting the RM Structure in Reinforcement Learning`
  - `# 5. Experimental Evaluation`
  - `# 6. Related Work`
  - `# 7. Concluding Remarks`
- Treat numbered subsections as level-two headings.
- Remove horizontal rules caused only by PDF page breaks.

### Office Gridworld Symbols

In Figure 1 and its surrounding discussion:

- coffee event: coffee-cup glyph
- mail event: envelope glyph
- decoration event: asterisk glyph
- office event: `o`
- marked locations: `A`, `B`, `C`, and `D`

Therefore, the proposition set is the coffee event, the mail event, `o`, the decoration event, and `A`, `B`, `C`, and `D`. The GLM placeholder `\text{box}` must not be read as either coffee or mail.

### Equations And Algorithms

- Use Firered's display-math layout and equation labels where present, except for its corrupted CRM Algorithm 2 updates.
- In Section 2.3, write the target-network updates as `\theta' \xleftarrow{\tau} \theta` and `\mu' \xleftarrow{\tau} \mu`; use `\arg\max_a \tilde q_\theta(s,a)` for the actor target and `\pi_\mu(s')` in the critic target.
- Use `\mathcal{M}` for the MDP tuple in Section 2.
- In Algorithm 2, lines 12 and 14 use the learning-rate update operator `\xleftarrow{\alpha}`, not `\frac{\alpha}{\bar r}`.
- The paper consistently uses `MDPRM`, never `MDPRAM`, `MDPRLM`, or `MDP-RL`.
- In Algorithm 3, line 15 compares the counterfactual next state with `\bar u`, not `u`.

### Known OCR Defects To Ignore

- Firered's `\blacksquare` substitutions for coffee and mail, plus its `\times` decoration symbol, are unreliable.
- Firered's chart-derived HTML tables are not source tables and should be ignored.
- GLM has one prose typo in Section 5.3: “CRM also performs well, completing around 6 laps” should read “HRM also performs well, completing around 6 laps.”
- GLM's reference entry “partiallyatisfiable” should read “partially satisfiable.”
