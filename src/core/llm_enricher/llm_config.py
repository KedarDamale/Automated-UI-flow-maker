import json
from openai import AzureOpenAI
from src.config.Config import settings
from src.config.Logger import logger

llm = AzureOpenAI(
  azure_endpoint = f"https://{settings.AZURE_OPENAI_ENDPOINT}/openai/deployments/{settings.AZURE_DEPLOYMENT_NAME}",
  api_key=settings.AZURE_OPENAI_API_KEY,
  api_version=settings.AZURE_OPENAI_API_VERSION
)

def batch_nodes(nodes: dict) -> list[list]:
    batches, current, count = [], [], 0
    for node_id, node in nodes.items():
        chunk = f"{node_id}: {json.dumps(node)}\n"
        if count + len(chunk) > settings.CHAR_LIMIT:
            batches.append(current)
            current, count = [], 0
        current.append((node_id, node))
        count += len(chunk)
    if current:
        batches.append(current)
    return batches


def enrich_graph(graph: dict, heuristic_tasks: list[str] | None = None) -> dict:

    if not settings.LLM_ENRICH:
        logger.log("[llm_enricher] LLM enrichment is disabled — skipping.", "warn")
        return graph

    tasks = heuristic_tasks or []
    if tasks:
        logger.log(f"Heuristic tasks: {tasks}", "info")
    else:
        logger.log("No heuristic tasks provided, using default tasks", "warn")

    nodes = graph.get("nodes", {})
    batches = batch_nodes(nodes)

    logger.log(f"Enriching {len(nodes)} nodes in {len(batches)} LLM call(s)", "info")

    for i, batch in enumerate(batches):
        nodes_block = "\n".join(
            f'- id: {nid}\n  url: {n.get("url","")}\n  name: {n.get("name","")}\n  tags: {n.get("tags",[])}'
            for nid, n in batch
        )
        prompt = f"""
                  Enrich the following UI screen nodes.
                  Heuristic tasks to score: {tasks}

                  Nodes:
                  {nodes_block}

                  Return a JSON object keyed by node id, each with: name, tags, heuristics.
                  Return JSON only.
        """

        try:
            resp = llm.chat.completions.create(
                model=settings.AZURE_DEPLOYMENT_NAME,
                messages=[
                    {"role": "system", "content": settings.SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt},
                ],
            )
            text = resp.choices[0].message.content.strip()

            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            data = json.loads(text)

            for node_id, node in batch:
                enriched = data.get(node_id, {})
                if "name" in enriched:
                    nodes[node_id]["name"] = enriched["name"]
                if "tags" in enriched:
                    nodes[node_id]["tags"] = list(set(node.get("tags", []) + enriched["tags"]))
                if "heuristics" in enriched:
                    nodes[node_id]["heuristics"] = enriched["heuristics"]

        except Exception as e:
            logger.log(f"[llm_enricher] Batch {i+1} failed: {e}", "error")

    return graph

