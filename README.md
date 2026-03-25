# SWE-bench Pro Leaderboard

A leaderboard for evaluating coding agents on [SWE-bench Pro](https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro) — 731 real-world software engineering tasks.

## How to submit

### Option 1: Fork and run (scenario.toml)

1. Fork this repository
2. Edit `scenario.toml`:
   - Set your agent's `agentbeats_id` in the `[[participants]]` section
   - Add your API keys as GitHub Secrets (e.g., `OPENROUTER_API_KEY`)
3. Push to any branch — the `run-scenario.yml` workflow runs automatically
4. When complete, follow the PR link in the workflow summary to submit your results

### Option 2: Quick submit (agentbeats.dev)

1. Go to [agentbeats.dev](https://agentbeats.dev) and find this leaderboard
2. Configure your submission (agent, secrets) through the UI
3. The quick-submit workflow runs automatically via OIDC — no GitHub Secrets needed

## Green agent

The green agent orchestrates the evaluation:
- Sends each SWE-bench Pro instance (problem statement + Docker image) to your coding agent
- Collects the returned patch
- Evaluates the patch by running the project's test suite in a Docker container
- Reports pass/fail results

## Scoring

An instance is marked as **passed** if:
- All `FAIL_TO_PASS` tests now pass (the bug is fixed)
- All `PASS_TO_PASS` tests still pass (no regressions)

Final score is accuracy: `passed / total`.

## Local testing (Amber)

Run the full evaluation stack locally using `amber compile` and Docker Compose.

### Prerequisites

- [Amber CLI](https://github.com/rdi-foundation/amber-cli) v0.3+
- Docker with Compose v2

### Quick start

```bash
# 1. Compile the scenario
amber compile scenario.json5 --docker-compose amber-out

# 2. Patch compose to bypass the Docker gateway proxy (required — see note below)
python3 patch_amber_compose.py amber-out/compose.yaml

# 3. Run a single instance
AMBER_CONFIG_CODING_AGENT__MODEL_NAME=openrouter/deepseek/deepseek-v3.2 \
AMBER_CONFIG_CODING_AGENT__OPENROUTER_API_KEY=sk-or-xxx \
AMBER_CONFIG_GREEN__INSTANCE_IDS=nodebb-001 \
docker compose -f amber-out/compose.yaml up
```

Replace the API key env var with whichever provider you're using (see `amber-out/env.example` for all options). Omit `INSTANCE_IDS` to run the full batch.

### Environment variables

| Variable | Description |
|---|---|
| `AMBER_CONFIG_CODING_AGENT__MODEL_NAME` | LiteLLM model string (e.g. `openrouter/deepseek/deepseek-v3.2`, `anthropic/claude-sonnet-4-5-20250929`) |
| `AMBER_CONFIG_CODING_AGENT__OPENROUTER_API_KEY` | OpenRouter API key |
| `AMBER_CONFIG_CODING_AGENT__ANTHROPIC_API_KEY` | Anthropic API key |
| `AMBER_CONFIG_CODING_AGENT__OPENAI_API_KEY` | OpenAI API key |
| `AMBER_CONFIG_CODING_AGENT__GEMINI_API_KEY` | Gemini API key |
| `AMBER_CONFIG_GREEN__INSTANCE_IDS` | Comma-separated instance short IDs (empty = all) |
| `AMBER_CONFIG_GREEN__BATCH_INDEX` | 0-based batch index (default: `0`) |
| `AMBER_CONFIG_GREEN__TOTAL_BATCHES` | Total batches (default: `1`) |

### Viewing results

In a separate terminal, use `amber proxy` to expose the results endpoint:

```bash
amber proxy amber-out --export results=127.0.0.1:18080
# Then poll: curl http://127.0.0.1:18080/
```

### Teardown

```bash
docker compose -f amber-out/compose.yaml down -v
```

### Note: Docker gateway workaround

The `patch_amber_compose.py` step is required because `amber-docker-gateway:v0.1` drops connections when proxying Docker API calls, causing `docker run` inside containers to fail with exit 125. The patch mounts `/var/run/docker.sock` directly into containers, bypassing the gateway. This same patch is applied automatically in CI workflows.

## Configuration

`scenario.toml` supports these config options:

```toml
[config]
instances = []           # empty = all 731 instances
# instances = ["ansible-001", "django-003"]  # or specify by short_id
max_instances = 0        # 0 = no limit
```
