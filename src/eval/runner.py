import json
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from src.core.config import Settings
from src.main import create_app

KEYS = {"C-01": "demo-c01", "C-02": "demo-c02"}
REFUSAL_INTENTS = {"unsafe", "out_of_scope"}
HERE = Path(__file__).parent


class EvalRunner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @staticmethod
    def refused(resp: dict) -> bool:
        return resp["intent"] in REFUSAL_INTENTS or "entitlement_denied" in resp["flags"]

    def check(self, client_id: str, expect: dict, resp: dict, entitled: set[str]) -> list[str]:
        failures = []
        text = resp["answer"].lower()
        cited = {c["report_id"] for c in resp["citations"] if c["report_id"]}
        if "refuse" in expect and self.refused(resp) != expect["refuse"]:
            failures.append(f"refusal expected={expect['refuse']} got={self.refused(resp)}")
        if "intent" in expect and resp["intent"] != expect["intent"]:
            failures.append(f"intent expected={expect['intent']} got={resp['intent']}")
        if "conflict" in expect and bool(resp["conflicts"]) != expect["conflict"]:
            failures.append(f"conflict expected={expect['conflict']} got={bool(resp['conflicts'])}")
        if "derived" in expect and bool(resp["derived_values"]) != expect["derived"]:
            failures.append(f"derived expected={expect['derived']} got={bool(resp['derived_values'])}")
        if "escalated" in expect and resp["escalated"] != expect["escalated"]:
            failures.append(f"escalated expected={expect['escalated']} got={resp['escalated']}")
        if "flag" in expect and expect["flag"] not in resp["flags"]:
            failures.append(f"missing flag {expect['flag']}")
        if expect.get("sql") and not resp["sql_queries"]:
            failures.append("no SQL query reported")
        failures += [f"answer missing '{s}'" for s in expect.get("contains", []) if s.lower() not in text]
        failures += [f"answer must not contain '{s}'" for s in expect.get("absent", []) if s.lower() in text]
        failures += [f"missing citation {r}" for r in expect.get("cites", []) if r not in cited]
        failures += [f"forbidden citation {r}" for r in expect.get("no_cite", []) if r in cited]
        failures += [f"cited non-entitled report {r}" for r in cited - entitled]
        return failures

    def run(self) -> dict:
        questions = json.loads((HERE / "questions.json").read_text())
        results = []
        with TestClient(create_app(self.settings)) as client:
            container = client.app.state.container
            for q in questions:
                conversation = None
                for earlier in q.get("after", []):
                    first = client.post("/chat", json={"client_id": q["client"], "message": earlier, "conversation_id": conversation}, headers={"X-API-Key": KEYS[q["client"]]}).json()
                    conversation = first["conversation_id"]
                resp = client.post("/chat", json={"client_id": q["client"], "message": q["q"], "conversation_id": conversation}, headers={"X-API-Key": KEYS[q["client"]]})
                body = resp.json()
                entitled = set(container.entitlement.entitled_ids(q["client"]))
                failures = [f"HTTP {resp.status_code}"] if resp.status_code != 200 else self.check(q["client"], q["expect"], body, entitled)
                results.append({**q, "failures": failures, "answer": body.get("answer", ""), "confidence": body.get("confidence"), "intent": body.get("intent")})
        return self.summarise(results)

    @staticmethod
    def summarise(results: list[dict]) -> dict:
        def rate(items: list[dict]) -> str:
            ok = sum(1 for r in items if not r["failures"])
            return f"{ok}/{len(items)} ({100 * ok / len(items):.0f}%)" if items else "n/a"

        subsets = {
            "Overall correctness": results,
            "Citation accuracy": [r for r in results if "cites" in r["expect"] or "no_cite" in r["expect"]],
            "Refusal accuracy": [r for r in results if "refuse" in r["expect"]],
            "Conflict detection": [r for r in results if "conflict" in r["expect"]],
            "Escalation behaviour": [r for r in results if "escalated" in r["expect"]],
            "Derived-value labelling": [r for r in results if "derived" in r["expect"]],
        }
        return {"metrics": {name: rate(items) for name, items in subsets.items()}, "results": results}

    def write(self, summary: dict) -> None:
        (HERE / "results.json").write_text(json.dumps(summary, indent=2))
        lines = ["# Evaluation report", "", f"Questions: {len(summary['results'])}", "", "| Metric | Result |", "|---|---|"]
        lines += [f"| {k} | {v} |" for k, v in summary["metrics"].items()]
        failed = [r for r in summary["results"] if r["failures"]]
        lines += ["", f"## Failures ({len(failed)})", ""]
        for r in failed:
            lines += [f"### Q{r['id']} [{r['client']}] {r['q']}", "", *[f"- {f}" for f in r["failures"]], "", "Answer given:", "", "```", r["answer"][:600], "```", ""]
        (HERE / "REPORT.md").write_text("\n".join(lines))


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        env_file = ".env" if "--llm" in sys.argv else None
        settings = Settings(db_path=f"{tmp}/atlas.db", chroma_path=f"{tmp}/chroma", api_keys="demo-c01:C-01,demo-c02:C-02", _env_file=env_file)
        runner = EvalRunner(settings)
        summary = runner.run()
        runner.write(summary)
    for name, value in summary["metrics"].items():
        print(f"{name}: {value}")
    for r in summary["results"]:
        if r["failures"]:
            print(f"FAIL Q{r['id']}: {r['q']} -> {r['failures']}")


if __name__ == "__main__":
    main()
