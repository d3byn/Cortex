from langgraph.graph import END, StateGraph
from app.graph.nodes import check_groundedness, generate_answer, retrieve_chunks, rewrite_query
from app.graph.state import PipelineState

def build_pipeline():
    graph = StateGraph(PipelineState)
    graph.add_node("rewrite_query", rewrite_query)
    graph.add_node("retrieve_chunks", retrieve_chunks)
    graph.add_node("generate_answer", generate_answer)
    graph.add_node("check_groundedness", check_groundedness)
    graph.set_entry_point("rewrite_query")
    graph.add_edge("rewrite_query", "retrieve_chunks")
    graph.add_edge("retrieve_chunks", "generate_answer")
    graph.add_edge("generate_answer", "check_groundedness")
    graph.add_edge("check_groundedness", END)
    return graph.compile()

compiled_pipeline = build_pipeline()