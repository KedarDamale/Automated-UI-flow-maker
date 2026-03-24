import json
from pyvis.network import Network


def visualize_graph(json_path: str = "output/ui_flow.json", output_path: str = "output/graph.html"):
    with open(json_path) as f:
        graph = json.load(f)

    net = Network(height="900px", width="100%", directed=True, notebook=False)
    net.barnes_hut(spring_length=100, spring_strength=0.05, damping=0.9)

    nodes = graph.get("nodes", {})
    adjacency = graph.get("adjacency_list", {})
    start = graph.get("start_node")

    for node_id, node in nodes.items():
        label = node.get("name", node_id)
        label = label[:20] + "..." if len(label) > 20 else label
        tags = ", ".join(node.get("tags", []))
        tooltip = f"{node_id}\n{node.get('url','')}\ntags: {tags}"
        color = "#D96C6C" if node_id == start else "#6C9FD9"
        net.add_node(
            node_id,
            label=label,
            title=tooltip,
            color=color,
            size=30,
            font={"size": 12, "vadjust": 0},
        )

    for src, edges in adjacency.items():
        for edge in edges:
            dst = edge.get("to")
            action = edge.get("action", {})

            interaction = action.get("interaction", "click")
            raw_label = action.get("label", "")
            label = f"{interaction}: {raw_label}"
            label = label[:22] + "..." if len(label) > 22 else label
            tooltip = f"{interaction}: {raw_label}\nselector: {action.get('selector','')}"

            net.add_edge(src, dst, label=label, title=tooltip, length=120)

    net.show(output_path, notebook=False)
    print(f"Graph saved to {output_path} — open it in your browser")

