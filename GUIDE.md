# Creating a Challenge Folder

A challenge folder is a git repo containing a `program.md` and the files needed to run the optimization.

## Structure

```
my-challenge/
├── program.md          # REQUIRED: config + problem description
├── target_file.ext     # the file being optimized
├── ref1.ext            # reference files (read-only context)
├── ref2.ext
└── council.yaml        # OPTIONAL: override default models/settings
```

## program.md Format

The file starts with YAML frontmatter (between `---` markers) followed by the problem description in markdown.

### Frontmatter (required fields)

```yaml
---
target_file: train.py                          # the file the agent modifies
reference_files:                               # read-only files for context
  - utils.py
  - config.py
validate: "python -c 'import train'"           # quick syntax/compile check
eval: "python train.py"                        # the scoring command
metric_regex: "val_loss: ([\\d.]+)"            # regex to extract score
direction: minimize                            # "maximize" or "minimize"
---
```

### Body

Write everything the models need to understand the problem:

1. **What the problem is** — plain English, assume the reader is a smart engineer seeing it for the first time
2. **How scoring works** — exactly what the metric means
3. **What can be modified** — which parts of the target file are fair game
4. **Constraints** — what's NOT allowed
5. **Key insights** — anything learned from prior attempts (helps avoid repeating failed experiments)

## Example

See `examples/amm-challenge/` for a complete working example.

## Tips

- Include ALL relevant context in the problem description. The models can't browse the internet or read files not listed in reference_files.
- Be specific about constraints. If there's a gas limit, memory limit, or time budget, state it.
- Include benchmark numbers (baseline score, known best scores) so models can calibrate their expectations.
- If you've already tried things, document them in the "Key Insights" section. This prevents the council from wasting rounds rediscovering what doesn't work.
