# AI Tool Usage

This project was developed with assistance from AI tools as encouraged by the assignment guidelines.

## Tools Used

- **Claude Code (Anthropic)** — AI-powered CLI for code generation, testing, and documentation
- **Claude Code Superpowers Plugin** — A skill-based plugin system that enforces structured workflows on top of Claude Code. Key skills used:
  - `brainstorming` — Structured requirement exploration before implementation: clarifies user intent, identifies edge cases, evaluates trade-offs, and produces a design brief before any code is written
  - `writing-plans` — Generates detailed step-by-step implementation plans with file-level changes, reviewed and approved before execution
  - `executing-plans` — Executes approved plans with review checkpoints between steps
  - `systematic-debugging` — Root cause analysis workflow for bugs (e.g., mobile tooltip overflow, dual-element targeting)
  - `verification-before-completion` — Ensures build passes and behavior is verified before claiming completion
  - `requesting-code-review` — Post-implementation review against plan and coding standards

## Usage Approach

1. **Design Phase**: Used Claude Code with superpowers brainstorming skill for structured requirement exploration — clarifying user intent, defining scope, and evaluating multiple approaches before settling on the final design (e.g., 2-Agent architecture, onboarding tour UX)
2. **Planning**: Used Claude Code plan mode to produce detailed implementation plans with step-by-step file changes, then reviewed and approved before execution
3. **Implementation**: Generated code with AI assistance, then reviewed and refined each component
4. **Testing**: AI-assisted test case generation with mocked external dependencies, ensuring comprehensive coverage of edge cases
5. **Debugging**: Used iterative deploy-test-fix cycles with screenshot-based feedback for UI issues (e.g., mobile tooltip overflow, sidebar state management)
6. **Documentation**: AI-assisted README, design document, API documentation, and doc-vs-code consistency audits

## Prompts

Key prompts used during development:

**Core Architecture**
- "Design a 2-Agent architecture for a web search chatbot that decides when to search"
- "Implement a FastAPI SSE streaming endpoint for chat responses"
- "Create a ChatGPT-style React UI with Tailwind CSS"
- "Write pytest tests for the Planner Agent with mocked OpenAI calls"
- "Create a useSSE hook for consuming Server-Sent Events in React"

**Telegram Integration**
- "Add Telegram bot with bidirectional Web ↔ Telegram message sync"
- "Fix: Telegram bot only shows citation numbers but not source URLs"

**Onboarding Tour**
- "Implement a 4-step onboarding tour for first-time users with mobile sidebar handling"
- "Fix: tour tooltip buttons clipped on mobile and desktop when target is near screen edge"

**Quality & Docs**
- "Check all docs match current codebase and architecture"
- "Fix responsive design overflow on mobile (iPhone 12)"

All AI-generated code was reviewed, tested, and modified as needed to ensure correctness and quality.
