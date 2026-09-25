# Step 0 guard for client-status-qbr. Each skill runs it as the first command of every call:
#   export SKILL_DIR="<loader base dir>" RUN_DIR="<working folder>" && sh "$SKILL_DIR/scripts/step0.sh" <version> <skill> && ...
# Silent with exit 0 only when SKILL_DIR is the <skill> folder of this plugin at <version> and RUN_DIR exists.
# Any failure prints one STEP 0 FAILED line and exits 1, so the && chain stops.

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
