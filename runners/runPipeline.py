import _bootstrap  # noqa: F401  (puts src/ and graphTraversal/ on sys.path, chdir to repo root)
import subprocess
import sys

from config import (
    CHUNKER_TYPE, GRAPH_ROUTE, GRAPH_EXTRACT_BACKEND,
    EXTRACT_DIR, CORPUS_NAME, SYNONYM_THRESHOLD, COMMUNITY_RESOLUTION,
    NER_STRATEGY,
)

# Consolidated orchestrator. Each stage is just its standalone per-stage runner
# invoked as a subprocess — runPipeline owns ordering + the Route 1/2 branch only,
# never the stage logic. Every runner already does its own skip-if-exists and reads
# the same config knobs, so re-runs are cheap and the two entry points can't drift.


def runStage(script, *args):
    print(f"\n=== {script} {' '.join(args)} ===", flush=True)
    # -u: child runs unbuffered so its per-doc progress prints stream live (inherited
    # stdout is block-buffered otherwise when this is piped/redirected, not a TTY).
    subprocess.run([sys.executable, "-u", script, *args], check=True)


if __name__ == '__main__':
    print("=" * 70)
    print(f"Gazelle pipeline | Route {GRAPH_ROUTE} | chunker={CHUNKER_TYPE} | ner={NER_STRATEGY} | extract={EXTRACT_DIR} | corpus={CORPUS_NAME}")
    print("=" * 70)

    # prep (skip-if-exists, fixed folders)
    runStage("runners/runOcr.py")
    runStage("runners/runParser.py")
    runStage("runners/runChunker.py")

    # graph construction — Chunk + Entity (+ RELATED on Route 2)
    if GRAPH_ROUTE == '2':
        runStage("runners/runGraphExtract.py")
        runStage("runners/runGraphBuild.py")
    else:
        if NER_STRATEGY == 'classical':
            runStage("runners/runNerPipeline.py")
        else:
            runStage("runners/runGliner.py")
        runStage("runners/runKgBuild.py")

    # post-graph retrieval layers
    runStage("runners/runEmbed.py")                                   # c.embedding on the chunks just created
    runStage("runners/runEntityEmbed.py")                            # e.embedding for seeding + synonyms
    runStage("graphTraversal/runSynonyms.py", str(SYNONYM_THRESHOLD))  # SYNONYM edges

    # global arm — Route 2 only (needs descriptions on RELATED edges)
    if GRAPH_ROUTE == '2':
        runStage("graphTraversal/runCommunities.py", "ALL", str(COMMUNITY_RESOLUTION), CORPUS_NAME)
        runStage("runners/runCommunitySummary.py", CORPUS_NAME, GRAPH_EXTRACT_BACKEND)
    else:
        print("\n[skip] communities + summaries (Route 1 has no descriptions; global arm needs Route 2)")

    print("\n=== Done ===")
