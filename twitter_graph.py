from langgraph.graph import StateGraph

from twitter_state import TwitterState
from nodes.tweet_collector_node import tweet_collector_node
from nodes.noise_filter_node import noise_filter_node
from nodes.dedup_node import dedup_node
from nodes.stock_detector_node import stock_detector_node
from nodes.twitter_telegram_node import twitter_telegram_node


def build_twitter_graph():
    builder = StateGraph(TwitterState)

    builder.add_node("collect", tweet_collector_node)
    builder.add_node("filter", noise_filter_node)
    builder.add_node("dedup", dedup_node)
    builder.add_node("detect", stock_detector_node)
    builder.add_node("alert", twitter_telegram_node)

    builder.set_entry_point("collect")

    builder.add_edge("collect", "filter")
    builder.add_edge("filter", "dedup")
    builder.add_edge("dedup", "detect")
    builder.add_edge("detect", "alert")

    return builder.compile()
