# Source this. It scopes Hermes to a repo-local home (./.hermes-home, gitignored) so nothing here touches ~/.hermes/config.yaml,
# and points that home at the local Ollama endpoint (cloud models proxy through it once `ollama signin` has linked this Mac).
export PATH="$HOME/.local/bin:$PATH"
export HERMES_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.hermes-home"
if [ ! -f "$HERMES_HOME/.configured" ]; then
    mkdir -p "$HERMES_HOME"
    hermes config set model.provider custom >/dev/null
    hermes config set model.base_url http://127.0.0.1:11434/v1 >/dev/null
    hermes config set model.api_key ollama-local >/dev/null
    hermes config set model.context_length 131072 >/dev/null
    hermes config set agent.reasoning_effort none >/dev/null          # the llama control rejects a thinking parameter; GLM ignores none
    hermes config set agent.disabled_toolsets "web,search,vision,image_gen" >/dev/null   # with -t safe this leaves the model no tools
    touch "$HERMES_HOME/.configured"
fi
