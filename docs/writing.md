# Writing guide

Issues, pull requests, documentation, release notes and reports follow this guide,
whether a person or a coding agent writes them. The
[submission format](../CONTRIBUTING.md#issues-and-pull-requests) sets the sections and
length of issues and pull requests, and
[AGENTS.md](../AGENTS.md#state-compatibility-and-performance-precisely) sets how to state
compatibility and performance claims.

## Write for the reader

- Identify the reader, the purpose and the requested scope. Read enough of the surrounding
  material to keep its voice, terms and notation.
- Put the result, decision or problem first. Follow it with the evidence, assumptions and
  consequences that change how the reader interprets it. Define a term or symbol before
  relying on it.
- Give each paragraph one main point. Explain reasoning in prose, because bullets drop the
  connections between steps. Use descriptive headings for navigation, numbered lists for
  ordered steps and tables for exact comparisons. Reserve bold for defined terms and
  warnings. Label units, and put commands and code in code fences.
- Keep precise technical terms and the qualifications that change meaning. Keep claims
  within the evidence, and distinguish measured results, derived results, hypotheses and
  examples. Do not supply a citation, number or result that was not provided or verified;
  name the gap instead.

## Edit for directness

- Cut generic openings, recaps, closing remarks and repeated caveats.
- Match length to content. A five-line fix needs a few sentences, and every sentence should
  carry a fact, a decision or a step in the reasoning.
- Replace promotional language, slogans and strained metaphors with specific actions or
  results.
- State a limitation once, concretely, beside the claim it limits. Do not restate it in a
  summary or disclaim what nobody claimed.
- Replace vague attribution such as "reviews found" with the source and the claim it
  supports: an issue, a pull request, a commit-pinned file or a measurement.
- Vary sentence openings and length where a repeated pattern distracts, and keep useful
  parallelism. Such patterns are editorial cues, never evidence of who wrote the text.

| Before | After |
|---|---|
| This highlights the importance of caching, which avoids three repeated parses. | Caching avoids three repeated parses. |
| The difference may seem surprising. This bound applies only to prediction error. | This bound applies only to prediction error. |
| This could potentially suggest that the model may be overfitting. | The model may be overfitting. |
| The robust, seamless cache cuts latency by 40%. | The cache cuts latency by 40%. |
| This does not claim general pattern matching or a release-wide speedup. | Delete it, and state the supported patterns where they are described. |

## Format for where the text is read

GitHub renders each newline in an issue, pull request, comment or release body as a line
break. Write every paragraph and list item there on a single line, and let the browser wrap
it. Repository Markdown files may wrap at about 90 columns, because GitHub joins those
lines when it renders a file. The submission check flags hard-wrapped issue and pull
request bodies, and the release workflow unwraps release notes before publishing them.

Text read outside the repository, such as issues, pull requests and release notes, needs
absolute links. Pin links to evidence to a tag or commit, so they still resolve after the
file changes. Links between repository documents stay relative.

## Fit the document

| Document | What the reader needs |
|---|---|
| Issue | The problem, a small reproducer or example with its limits, and the condition for closing it. |
| Pull request | The problem, the change and its limits, and the commands and results that validate it, including checks that failed or did not run. |
| Documentation | The task or contract, its constraints, and concrete steps or consequences. Follow the file's terms and structure; superseded history belongs in Git and commit-pinned links. |
| Release notes | What changed for users, how to use it, its limits and where to read more ([below](#release-notes)). |
| Benchmark or experiment report | The workload, baseline, setup, metric and units, results, sample size, variability and limits. Mark missing information where it affects interpretation. |
| Research note | The question or claim, definitions and assumptions, the method, and the evidence and limits of the conclusion. |

### Release notes

Release notes serve someone deciding whether to install or upgrade. Each version's notes
live in `docs/releases/VERSION.md`; the [release procedure](releasing.md) publishes them.

1. Open with a short paragraph, without a title: what the version is for and its main
   changes. The workflow titles the release.
2. Describe each user-visible change under a descriptive `##` heading or as a list item:
   what now works, a short example when it helps, its limits stated once, and links to
   the pull request and the reference documentation. Group small fixes into one list.
3. Mention CI, release tooling and refactors only when they change what users can rely on.
4. End with known limits and supported platforms. The workflow appends the release assets,
   Docker image, checksums and source commit.

`python3 tools/release_notes.py check docs/releases/VERSION.md` enforces the mechanical
rules: no title, `##` and `###` headings only, absolute links pinned to a tag or commit,
at most 80 words per paragraph or list item, and at most 700 words outside tables and
code. CI runs it on the current version, and the Release workflow runs it before building.

## Check before publishing

Reread the text as its intended reader and cut each sentence that reader would not miss.
Confirm that numbers carry units and trace to the cited evidence, that links resolve and
that the formatting matches the surrounding document. When asked to review rather than
edit, report problems in order of impact, each with its location and a suggested fix,
and leave the text unchanged unless a rewrite was requested.
