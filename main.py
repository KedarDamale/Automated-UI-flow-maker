from src.config.Config import settings
from src.core.extras.visualize import visualize_graph
from src.config.Logger import logger
from src.core.crawler.crawl import UICrawler
from src.core.llm_enricher.llm_config import enrich_graph
import asyncio
import os
import json

async def main():
    
    logger.log(f"Starting crawl for {settings.CRAWL_URL}","info")
    logger.log(f"Max depth: {settings.MAX_DEPTH}","info")
    logger.log(f"Max nodes: {settings.MAX_NODES}","info")

    graph = await UICrawler().crawl()
    #LLM Enrichment
    if settings.LLM_ENRICH:#True or False if LLM enrichment is necessary then set to True

        #tasks are user defined goals 
        # eg. tasks = ["change password", "find invoice", "contact support"]
        #llm will upweight them
        heuristic_tasks=[]
        logger.log("Enriching graph with LLM","info")
        graph=enrich_graph(graph,heuristic_tasks)

    print(settings.AZURE_DEPLOYMENT_NAME)

    #Output

    os.makedirs(os.path.dirname(settings.OUTPUT_PATH) or ".", exist_ok=True)
    with open(settings.OUTPUT_PATH, "w") as f:
        json.dump(graph, f, indent=2)

    n = graph["meta"]["total_nodes"]
    e = graph["meta"]["total_edges"]
    print(f"\n✅  Done!  {n} nodes, {e} edges  →  {settings.OUTPUT_PATH}\n")

    logger.log(f"Visualizing the graph","info")
    visualize_graph("output/ui_flow.json")
    logger.log(f"Graph visualization saved to output/graph.html","info")



if __name__ == "__main__":
    asyncio.run(main())



