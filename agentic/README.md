AI tools will use this folder as a generic scratchpad for thoughts and memories. Research Data will be here. Bug data and resolutions will be kept in a running folder here.

```
agentic/
  research_notes/<topic>/   raw notes from a research pass, one file per subtopic, every claim sourced
  reports/<topic>.md        the synthesised report for that pass
  bugs/                     every bug found and how it was resolved
```

A research pass never edits an earlier one's notes or report; a follow-up gets
its own topic name. Decisions taken from a report go to `docs/`, citing it.
