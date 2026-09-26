Model Selection
Chosen model: Gemini Flash (Google AI Studio)

We selected Gemini Flash as the foundation model for the SME Procurement Support Agent for four reasons:

1.Generous free tier — 1M-token context window and a high daily token quota, with no credit card required. This satisfies our "free APIs only" constraint while allowing us to ingest full synthetic inventory and quotation CSVs without truncation.

2.Native function calling and structured JSON output — essential for Week 4, where the agent must call tools such as get_inventory_status() and compare_supplier_quotes() and return schema-compliant arguments.

3.Low latency — stable response times suitable for a multi-step agent loop running on the mobile hotspot connections typical of our project environment.

4.Large context window — supports RAG-style grounding (Week 3) by allowing retrieved history and stock data to be passed in a single call.

Rejected alternatives: GPT-4o mini has no sustainable free tier; Groq (Llama 3.3) is faster but offers a smaller context window and less mature structured-output enforcement for our CSV-heavy workload.

Problem and mitigation: Google's free-tier documentation states that submitted data may be used to improve their products. We therefore use mainly synthetic data. This aligns with the data boundary already defined in our Project Charter.

