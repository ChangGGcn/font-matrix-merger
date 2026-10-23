# Technical documentation

**English** | [简体中文](README.zh-CN.md)

Technical reference for **v0.2.1**. Defaults and supported behavior follow the source code.

## Reading paths

Start with [usage](en/usage.md) for a runnable workflow. Use [merge-api](en/merge-api.md) for policy choices, [subsets and verification](en/subsets-and-verification.md) for webfont slices, and [limitations](en/limitations.md) before processing production inputs. Advanced APIs are separated from stable workflows.

| Topic | Contents |
| --- | --- |
| [Getting started and worked examples](en/usage.md) | CLI inputs, installation and complete workflows |
| [Merging API and policy parameters](en/merge-api.md) | Loading, high-level merging, defaults and answer keys |
| [Formatting, naming, layout and utility APIs](en/helper-api.md) | Format, naming, transforms, table/layout and save helpers |
| [Same-source subsets and verification](en/subsets-and-verification.md) | Slice labels, ownership, verification keywords and reports |
| [Axis mapping and variation composition](en/variation-model.md) | Coordinate spaces, support splitting, CFF2 and math APIs |
| [Merge pipelines and data invariants](en/architecture.md) | Dispatch matrix, copy paths, layout and finalization |
| [Module and script reference](en/script-reference.md) | All runtime, test and build files, plus CLI options |
| [Support boundaries and troubleshooting](en/limitations.md) | Unsupported cases, fallbacks, evidence and diagnostics |
| [Complete source signature index](en/parameter-index.md) | 69 source files and 613 callable definitions |

## Scope and evidence

- Each API page states argument defaults, units, return values and ownership. The signature index also lists internal helpers; their presence does not make them stable public APIs.
- Source links describe the repository layout. The runtime ZIP includes this documentation and the library, but excludes repository-only tests and build tools.
- Historical validation results are identified as such. Successful fontTools serialization is not a claim about every text engine, axis position or Windows rasterizer.
- Prose follows the [Academic Humanizer](https://github.com/AIScientists-Dev/academic-humanizer) guidance: precise terms, short evidence-bound statements and no promotional guarantees.

[Project README](../README.md) · [Version history](../CHANGELOG.md) · [License](../LICENSE)
