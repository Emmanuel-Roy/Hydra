AI tools will use this folder as a generic scratchpad for thoughts and memories. Research Data will be here. Bug data and resolutions will be kept in a running folder here.

```
agentic/
  research_notes/<topic>/   raw notes from a research pass, one file per subtopic, every claim sourced
  reports/<topic>.md        the synthesised report for that pass
  bugs/                     every bug found and how it was resolved
  observations/<topic>.md   data measured on our own tools and builds: numbers, what was run, where the run's report is
```

A research pass never edits an earlier one's notes or report; a follow-up gets
its own topic name. Decisions taken from a report go to `docs/`, citing it.

Observations hold measurements only. The code that produced them lives with
the test (for example `Tools/Verification/calibration/`), never here.
