from src.config.Config import settings
from src.config.Logger import logger
from src.core.crawler.crawl import UICrawler
from src.core.llm_enricher import enrich_graph
from src.config.Config import settings

async def main():
    
    login_steps = []#list of dicts of loggin steps

    logger.log(f"Starting crawl for {settings.CRAWL_URL}","info")
    logger.log(f"Max depth: {settings.MAX_DEPTH}","info")
    logger.log(f"Max nodes: {settings.MAX_NODES}","info")
    
    #LLM Enrichment
    if settings.LLM_ENRICH:
        tasks=[]
        logger.log("Enriching graph with LLM","info")
        graph=enrich_graph(graph,tasks)

    crawler = UICrawler(cfg)
    graph = await crawler.crawl()   

    #Output
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(graph, f, indent=2 if cfg.pretty_print else None)

    n = graph["meta"]["total_nodes"]
    e = graph["meta"]["total_edges"]
    print(f"\n✅  Done!  {n} nodes, {e} edges  →  {args.output}\n")


if __name__ == "__main__":
    asyncio.run(main())



