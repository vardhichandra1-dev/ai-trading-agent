from langgraph.graph import StateGraph
from state import GraphState

from nodes.query_node import generate_queries
from nodes.pdf_node import pdf_node
from nodes.search_node import search_node
from nodes.market_node import market_node
from nodes.reasoning_node import reasoning_node
from nodes.report_node import report_node

def build_graph():

    builder = StateGraph(GraphState)

    builder.add_node("query", generate_queries)
    builder.add_node("pdf", pdf_node)
    builder.add_node("search", search_node)
    builder.add_node("market", market_node)
    builder.add_node("reason", reasoning_node)
    builder.add_node("report", report_node)

    builder.set_entry_point("query")

    builder.add_edge("query", "pdf")
    builder.add_edge("pdf", "search")
    builder.add_edge("search", "market")
    builder.add_edge("market", "reason")
    builder.add_edge("reason", "report")

    return builder.compile()