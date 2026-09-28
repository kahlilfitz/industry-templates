# Step 0 guard for client-status-qbr. Each skill runs it as the first command of every call:
#   export SKILL_DIR="<loader base dir>" RUN_DIR="<working folder>" && sh "$SKILL_DIR/scripts/step0.sh" <version> <skill> && ...
# Silent with exit 0 only when SKILL_DIR is the <skill> folder of this plugin at <version> and RUN_DIR exists.
# Any failure prints one STEP 0 FAILED line and exits 1, so the && chain stops.
# Since 1.5.1 it also verifies the shared files (contract, rules, validate_payload.py, step0.sh,
# VERSION) against scripts/SHARED.sha256, and that manifest against the plugin-root copy, so a
# drifted or tampered copy fails Step 0 instead of passing silently.
# Since 1.6.0 the manifest also covers the two engines (variance_calc.py, item_age.py), which is
# where the RAG thresholds actually live; each skill verifies its own engine.
# Maintainers: after changing any shared file or engine, regenerate the manifest from the plugin
# root with
#   sha256sum contracts/ps.client-status-qbr.v1.json references/status-reporting-rules.md \
#     scripts/validate_payload.py scripts/step0.sh scripts/VERSION \
#     skills/variance-calc/scripts/variance_calc.py \
#     skills/risk-summarize/scripts/item_age.py > scripts/SHARED.sha256
# and copy the shared files plus SHARED.sha256 identically into every skills/<name>/ folder.

stop_plugin() {
  echo "STEP 0 FAILED: $1 - stop and ask the user for the plugin folder. Do not search the filesystem for it, do not skip this check, and do not compute anything by hand."
  exit 1
}

want="$1"
skill="$2"
[ -n "$want" ] || stop_plugin "no expected version was passed to step0.sh"
[ -n "$skill" ] || stop_plugin "no skill name was passed to step0.sh"
case "$SKILL_DIR" in
  /*) ;;
  *) stop_plugin "SKILL_DIR is not an absolute path ('$SKILL_DIR')" ;;
esac
[ -f "$SKILL_DIR/scripts/validate_payload.py" ] || stop_plugin "SKILL_DIR has no scripts/validate_payload.py"
[ -f "$SKILL_DIR/scripts/VERSION" ] || stop_plugin "SKILL_DIR has no scripts/VERSION, so it is not client-status-qbr $want"
tr -d '\r' < "$SKILL_DIR/scripts/VERSION" | grep -qxF "$want" ||
  stop_plugin "SKILL_DIR holds version $(head -n 1 "$SKILL_DIR/scripts/VERSION" | tr -d '\r') but this SKILL.md is $want - it is a stale or different copy"
[ -f "$SKILL_DIR/SKILL.md" ] && tr -d '\r' < "$SKILL_DIR/SKILL.md" | grep -qxF "name: $skill" ||
  stop_plugin "SKILL_DIR is not the $skill skill folder - it points at a different skill"
case "$skill" in
  variance-calc) [ -f "$SKILL_DIR/scripts/variance_calc.py" ] || stop_plugin "SKILL_DIR has no scripts/variance_calc.py" ;;
  risk-summarize) [ -f "$SKILL_DIR/scripts/item_age.py" ] || stop_plugin "SKILL_DIR has no scripts/item_age.py" ;;
esac
sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | cut -d ' ' -f 1
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | cut -d ' ' -f 1
  elif command -v python3 >/dev/null 2>&1; then
    python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$1"
  elif command -v python >/dev/null 2>&1; then
    python -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$1"
  else
    return 1
  fi
}
shared="$SKILL_DIR/scripts/SHARED.sha256"
[ -f "$shared" ] || stop_plugin "SKILL_DIR has no scripts/SHARED.sha256, so its shared files cannot be verified"
for rel in contracts/ps.client-status-qbr.v1.json references/status-reporting-rules.md scripts/validate_payload.py scripts/step0.sh scripts/VERSION; do
  expect=$(tr -d '\r' < "$shared" | awk -v p="$rel" '$2 == p { print $1; exit }')
  [ -n "$expect" ] || stop_plugin "scripts/SHARED.sha256 has no entry for $rel"
  [ -f "$SKILL_DIR/$rel" ] || stop_plugin "SKILL_DIR is missing the shared file $rel"
  got=$(sha256_of "$SKILL_DIR/$rel") || stop_plugin "no SHA-256 tool (sha256sum, shasum or python) is available to verify $rel"
  [ "$got" = "$expect" ] || stop_plugin "the shared file $rel in SKILL_DIR does not match scripts/SHARED.sha256 - this copy has drifted or been edited"
done
root_shared="$SKILL_DIR/../../scripts/SHARED.sha256"
if [ -f "$SKILL_DIR/../../.claude-plugin/plugin.json" ] && [ -f "$root_shared" ]; then
  [ "$(sha256_of "$root_shared")" = "$(sha256_of "$shared")" ] ||
    stop_plugin "this skill's scripts/SHARED.sha256 differs from the plugin-root copy - the shared files have drifted between skills"
fi

# The engines are not mirrored, so the manifest keys them by their path from the plugin root and
# each skill verifies only its own. Without this the integrity check covered every shared file but
# not the code that computes the RAG thresholds.
engine_rel=""
engine_key=""
case "$skill" in
  variance-calc)
    engine_rel="scripts/variance_calc.py"
    engine_key="skills/variance-calc/scripts/variance_calc.py"
    ;;
  risk-summarize)
    engine_rel="scripts/item_age.py"
    engine_key="skills/risk-summarize/scripts/item_age.py"
    ;;
esac
if [ -n "$engine_key" ]; then
  expect=$(tr -d '\r' < "$shared" | awk -v p="$engine_key" '$2 == p { print $1; exit }')
  [ -n "$expect" ] || stop_plugin "scripts/SHARED.sha256 has no entry for $engine_key"
  got=$(sha256_of "$SKILL_DIR/$engine_rel") || stop_plugin "no SHA-256 tool (sha256sum, shasum or python) is available to verify $engine_rel"
  [ "$got" = "$expect" ] || stop_plugin "the engine $engine_rel in SKILL_DIR does not match scripts/SHARED.sha256 - this copy has drifted or been edited"
fi

manifest="$SKILL_DIR/../../.claude-plugin/plugin.json"
if [ -f "$manifest" ]; then
  grep -q '"name"[[:space:]]*:[[:space:]]*"client-status-qbr"' "$manifest" ||
    stop_plugin "the plugin.json above SKILL_DIR is not client-status-qbr"
fi

if [ -z "$RUN_DIR" ] || [ ! -d "$RUN_DIR" ]; then
  echo "STEP 0 FAILED: the working folder RUN_DIR ('$RUN_DIR') does not exist - create it with mkdir -p, or ask the user which folder to use. Do not continue until it exists."
  exit 1
fi
exit 0
