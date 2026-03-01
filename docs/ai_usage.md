# AI Tool Usage

This project was developed with assistance from AI tools as encouraged by the assignment guidelines.

## Tools Used

- **Claude Code (Anthropic)** — Used for architecture design, code generation, testing, and documentation

## Usage Approach

1. **Design Phase**: Used Claude Code to brainstorm and validate the 2-Agent architecture design (Planner + Executor), exploring multiple approaches before settling on the final design
2. **Implementation**: Generated code with AI assistance following TDD methodology, then reviewed and refined each component
3. **Testing**: AI-assisted test case generation with mocked external dependencies, ensuring comprehensive coverage of edge cases
4. **Documentation**: AI-assisted README, design document, and API documentation writing

## Prompts

Key prompts used during development:

- "Design a 2-Agent architecture for a web search chatbot that decides when to search"
- "Implement a FastAPI SSE streaming endpoint for chat responses"
- "Create a ChatGPT-style React UI with Tailwind CSS"
- "Write pytest tests for the Planner Agent with mocked OpenAI calls"
- "Create a useSSE hook for consuming Server-Sent Events in React"

All AI-generated code was reviewed, tested, and modified as needed to ensure correctness and quality.
