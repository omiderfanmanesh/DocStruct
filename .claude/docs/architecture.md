# Architecture Notes

- `domain` holds pure models and matching logic.
- `application` holds agents, ports, and orchestration use cases.
- `infrastructure` adapts filesystem and LLM providers.
- `interfaces` exposes the CLI entrypoint.
