from langgraph.graph import StateGraph
from state import GraphState

from nodes.pdf_node import pdf_node
from nodes.pdf_summary_node import pdf_summary_node
from nodes.signal_node import signal_node
from nodes.validation_node import validation_node
from nodes.report_node import report_node
from nodes.telegram_node import telegram_node

def build_graph():

    builder = StateGraph(GraphState)

    builder.add_node("pdf", pdf_node)
    builder.add_node("pdf_summary", pdf_summary_node)
    builder.add_node("signal", signal_node)
    builder.add_node("validate", validation_node)
    builder.add_node("report", report_node)
    builder.add_node("telegram", telegram_node)

    builder.set_entry_point("pdf")

    builder.add_edge("pdf", "pdf_summary")
    builder.add_edge("pdf_summary", "signal")
    builder.add_edge("signal", "validate")
    builder.add_edge("validate", "report")
    builder.add_edge("report", "telegram")

    return builder.compile()
