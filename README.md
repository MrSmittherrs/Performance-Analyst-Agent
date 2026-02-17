# WAT Framework

A practical architecture for AI automation that separates probabilistic reasoning (AI) from deterministic execution (Python scripts).

## What is WAT?

**W**orkflows **A**gents **T**ools - A three-layer architecture:

1. **Workflows** - Markdown SOPs that define what to do
2. **Agents** - AI coordination layer (Claude) that makes decisions
3. **Tools** - Python scripts that execute deterministically

This separation ensures reliability: when AI handles only reasoning and delegates execution to tested scripts, the system stays accurate even as complexity grows.

## Quick Start

### 1. Setup Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Credentials

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your actual API keys
# (Use notepad, vim, or your preferred editor)
```

For Google OAuth:
- Place `credentials.json` in the project root
- First run will generate `token.json` automatically

### 3. Create Your First Workflow

See [workflows/template_workflow.md](workflows/template_workflow.md) for the structure. Workflows should define:
- **Objective**: What this workflow accomplishes
- **Required Inputs**: What information is needed
- **Tools Used**: Which scripts to execute
- **Expected Outputs**: What gets delivered
- **Edge Cases**: How to handle failures

### 4. Create Corresponding Tools

See [tools/example_tool.py](tools/example_tool.py) for the pattern. Tools should:
- Load credentials from `.env`
- Accept clear input parameters
- Return structured output or save to cloud services
- Include error handling and logging
- Be testable independently

## Directory Structure

```
.tmp/           # Temporary files (regenerated as needed, gitignored)
tools/          # Python scripts for deterministic execution
workflows/      # Markdown SOPs defining processes
.env            # API keys and secrets (gitignored, copy from .env.example)
CLAUDE.md       # Agent instructions for Claude
```

## Usage Pattern

1. Write a workflow in `workflows/` that describes the process
2. Create or identify tools in `tools/` that execute each step
3. Ask Claude to execute the workflow
4. Claude reads the workflow, runs tools in sequence, handles errors
5. Final outputs are delivered to cloud services (Google Sheets, etc.)

## Philosophy

- **Local files are for processing only** - Deliverables live in cloud services
- **Workflows evolve** - Update them when you learn better approaches
- **Tools are deterministic** - They should do one thing consistently
- **AI coordinates** - It reads workflows, executes tools, handles edge cases

## Self-Improvement Loop

1. Identify what broke
2. Fix the tool
3. Verify the fix
4. Update the workflow with lessons learned
5. Move forward with a more robust system

## Contributing

When adding new workflows or tools:
- Follow the template patterns
- Document edge cases you discover
- Keep tools focused and testable
- Update this README if you add new capabilities

## License

[Your license here]
