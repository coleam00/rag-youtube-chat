"""
Seed script — inserts 10 mock YouTube videos with transcripts.
Called automatically on first startup when the videos table is empty.

On first run (or when chunks are absent), the full pipeline is executed:
  1. Create video record
  2. Chunk transcript via Docling HybridChunker
  3. Embed chunks via OpenRouter
  4. Store chunks in DB

This ensures RAG retrieval works out-of-the-box.
"""
import asyncio
import logging

from backend.db import repository
from backend.rag.chunker import chunk_video
from backend.rag.embeddings import embed_batch

logger = logging.getLogger(__name__)

SEED_VIDEOS = [
    {
        "title": "Building AI Agents from Scratch",
        "description": "A deep dive into how autonomous AI agents work, covering agent loops, tool use, memory, and planning strategies.",
        "url": "https://www.youtube.com/watch?v=AgntBld001a",
        "transcript": """Welcome to this comprehensive tutorial on building AI agents from scratch. Today we're going to explore what autonomous agents really are and how you can build one yourself without relying on heavyweight frameworks.

At the core of every AI agent is what we call the agent loop. The agent loop is a simple but powerful pattern: perceive, think, act, and repeat. The agent receives observations from its environment, reasons about what to do next, executes an action, and then receives new observations. This cycle continues until the agent reaches its goal or decides to stop.

Tool use is one of the most exciting capabilities you can give an agent. Tools are just functions that the agent can call — things like searching the web, reading a file, writing code, or calling an external API. The key insight is that the language model doesn't actually run the tools itself. Instead, it outputs a structured call specifying which tool to invoke and with what arguments, and your orchestration layer handles the actual execution.

Planning is where things get really interesting. Simple agents just react to the immediate situation, but more sophisticated agents can create multi-step plans and execute them sequentially or in parallel. You can implement planning by giving the model a scratchpad where it reasons step by step before committing to an action. This is sometimes called chain-of-thought prompting applied to the agentic setting.

Memory is another critical component. Agents need both short-term working memory — the current context window — and long-term memory for storing facts, past interactions, and learned behaviors. You can implement long-term memory using a vector database or even a simple key-value store. The trick is deciding when to retrieve memories and how to integrate them into the current context without overwhelming the model.

Let's talk about error handling. Production agents need to handle failures gracefully. When a tool call fails, the agent should be able to retry, fall back to an alternative approach, or ask the user for clarification. Building robust error handling into your agent loop from the start will save you enormous debugging pain later.

Finally, evaluation. How do you know if your agent is actually working well? You need a suite of test cases covering common scenarios and edge cases. Track metrics like task completion rate, number of steps taken, and error frequency. A good agent should complete tasks reliably and efficiently, not just occasionally.

Building agents from scratch might seem daunting, but breaking it down into these components — the loop, tools, planning, memory, and evaluation — makes the problem very tractable. Start simple, get something working end to end, and then add capabilities incrementally.""",
    },
    {
        "title": "Understanding Retrieval-Augmented Generation",
        "description": "A complete guide to RAG architecture — how chunking, embedding, retrieval, and generation work together to ground LLMs in real data.",
        "url": "https://www.youtube.com/watch?v=RAGExplain2",
        "transcript": """Retrieval-Augmented Generation, or RAG, has become one of the most important patterns in applied AI. Today I want to give you a thorough understanding of how RAG actually works under the hood, so you can build and debug your own pipelines.

The fundamental problem RAG solves is that language models have a knowledge cutoff and a limited context window. They can't know about documents you wrote last week, and they can't fit an entire library into their context. RAG bridges this gap by retrieving relevant information at query time and injecting it into the prompt.

Let's start with chunking. Before you can retrieve anything, you need to break your documents into retrievable units called chunks. Chunking strategy has a huge impact on retrieval quality. Chunks that are too small lose context; chunks that are too large waste tokens and retrieve irrelevant material. A good chunking strategy respects document structure — breaking at paragraph or section boundaries rather than at arbitrary character counts.

Embedding is the next step. Each chunk is converted into a dense vector representation using an embedding model. These vectors capture the semantic meaning of the text in a high-dimensional space. Similar chunks end up near each other in this space, which is what makes semantic search possible. The embedding model you choose matters — different models have different strengths for different domains.

The retrieval step happens at query time. You embed the user's query using the same embedding model, then find the chunks whose embeddings are most similar to the query embedding. Cosine similarity is the standard metric for this comparison. You typically retrieve the top K chunks — often between 3 and 10 — and pass them to the language model as context.

Generation is where the LLM comes in. You construct a prompt that includes the retrieved chunks along with the user's question, and ask the model to answer based on the provided context. A good system prompt instructs the model to cite its sources and to acknowledge when the answer isn't in the context.

There are several common failure modes to watch for. Retrieval failures happen when the right chunk exists but isn't ranked highly enough. This can be due to vocabulary mismatch between the query and the document — a problem that hybrid search (combining dense and sparse retrieval) can address. Hallucination can still occur if the model extrapolates beyond what's in the retrieved context. Chunk boundary issues arise when a relevant passage is split across two chunks.

Advanced RAG techniques include re-ranking (using a cross-encoder to re-score the initial retrieval results), query expansion (generating multiple query variants to improve recall), and iterative retrieval (retrieving, generating a partial answer, then retrieving again based on what's still unknown).

The beauty of RAG is that it's modular. You can swap out the embedding model, the retrieval mechanism, or the generator independently. This makes it an excellent architecture for production systems where you need to iterate quickly.""",
    },
    {
        "title": "Fine-tuning vs. Prompting: When to Use Each",
        "description": "An honest comparison of fine-tuning and prompt engineering, helping you decide which approach is right for your use case.",
        "url": "https://www.youtube.com/watch?v=FineVsPrm03",
        "transcript": """One of the most common questions I get is: should I fine-tune my model or just engineer a better prompt? Today I want to give you a clear, practical framework for making this decision.

Let's start by being precise about what each approach actually is. Prompt engineering means crafting the input you give to the model — the system prompt, the examples, the instructions — to elicit the behavior you want without changing the model's weights. Fine-tuning means training the model on additional data, actually updating its parameters to specialize it for your task.

The case for prompt engineering is compelling in most situations. It's fast — you can iterate in minutes rather than hours or days. It's cheap — you only pay for inference, not training compute. It's reversible — a bad prompt can be fixed immediately. And for frontier models, prompt engineering can get you surprisingly far, often 80–90% of the way to your goal.

So when does fine-tuning make sense? There are a few clear signals. First, when you need consistent formatting or style that's hard to enforce through prompting alone. If you need the model to always output valid JSON in a specific schema, or always respond in a particular persona, fine-tuning can bake that in more reliably. Second, when you have a specialized domain with unusual vocabulary or reasoning patterns that the base model doesn't handle well. Medical, legal, or highly technical domains often benefit from fine-tuning on domain-specific text. Third, when you're making millions of calls and the token savings from shorter prompts matter economically — a fine-tuned model may need less scaffolding in the prompt.

But there are significant costs to fine-tuning that people often underestimate. You need training data — and good training data is expensive to create. You need to manage model versions as the base model evolves. You lose the ability to benefit from improvements to the base model without re-running fine-tuning. And debugging a fine-tuned model that behaves unexpectedly is much harder than tweaking a prompt.

My practical recommendation: always start with prompt engineering. Invest serious effort in crafting a good system prompt, few-shot examples, and chain-of-thought instructions. If you've genuinely hit the ceiling of what prompting can achieve for your specific task, then consider fine-tuning — but treat it as a last resort, not a first step.

There's also a hybrid approach worth considering: RAG combined with good prompting. Often what people think they need fine-tuning for is actually a knowledge problem — the model doesn't know about your specific data. RAG solves this more flexibly than fine-tuning.

The bottom line is that fine-tuning is a powerful tool but one that carries real costs. Use it when you have a clear need, good training data, and the infrastructure to support ongoing model management.""",
    },
    {
        "title": "Vector Databases Explained",
        "description": "A practical guide to vector databases — covering FAISS, Pinecone, pgvector, and how to choose the right solution for your scale.",
        "url": "https://www.youtube.com/watch?v=VectorDBs04",
        "transcript": """Vector databases are having a moment, and for good reason — they're the infrastructure layer that makes semantic search and RAG systems possible at scale. Today I'll walk you through the landscape of vector database options and help you understand which one to use when.

First, let's understand what a vector database actually does. At its core, it stores high-dimensional vectors — typically the embeddings of your text, images, or other data — and enables fast approximate nearest neighbor search. Given a query vector, it finds the most similar vectors in the database. The "approximate" part is important: exact nearest neighbor search in high dimensions is computationally prohibitive, so these systems use clever indexing structures to find very good answers very fast.

FAISS, or Facebook AI Similarity Search, is the foundational library that many vector stores are built on. It's open source, runs in memory or on disk, and supports multiple index types with different trade-offs between speed, memory usage, and accuracy. FAISS is excellent for experimentation and smaller-scale deployments, but it doesn't have built-in persistence, clustering, or a query API — you have to build those yourself.

Pinecone is a fully managed vector database service. You send it your vectors via API, and it handles indexing, scaling, and serving. The major advantage is operational simplicity — you don't manage any infrastructure. Pinecone also supports metadata filtering, so you can search within subsets of your data. The downside is cost and vendor lock-in. For high query volumes, Pinecone can get expensive quickly.

pgvector is a PostgreSQL extension that adds vector storage and similarity search to your existing Postgres database. This is an excellent choice if you're already running Postgres — you get vector search alongside your relational data without adding a new system to operate. The query performance is good for moderate scale, and you can combine vector search with SQL filters naturally. For most applications under a few million vectors, pgvector is my recommendation.

Weaviate, Qdrant, and Chroma are purpose-built vector databases with their own strengths. Weaviate has a strong GraphQL interface and built-in support for hybrid search. Qdrant is written in Rust and is very performant. Chroma is Python-native and designed for development ergonomics.

How do you choose? Start with your scale requirements. For development and small production deployments, FAISS or Chroma work fine. For medium scale where you want operational simplicity, pgvector is hard to beat. For large scale with complex requirements, a managed service like Pinecone or a self-hosted Qdrant or Weaviate makes sense.

Consider also your query patterns. Do you need metadata filtering? Do you need hybrid search combining keyword and semantic results? Do you have real-time write requirements? Each system has different strengths here.

The most important thing is not to over-engineer. Many production RAG applications work perfectly well with SQLite and cosine similarity computed in Python. Reach for a dedicated vector database when you actually need the scale or features it provides.""",
    },
    {
        "title": "How I Built a Coding Assistant in One Weekend",
        "description": "A personal walkthrough of building a functional AI coding assistant in a weekend — architecture decisions, lessons learned, and what I'd do differently.",
        "url": "https://www.youtube.com/watch?v=CodingAst05",
        "transcript": """This weekend I set out to build a coding assistant from scratch, and I want to share exactly what I built, how I built it, and what I learned along the way.

The goal was a tool that understands my codebase and can answer questions about it, suggest changes, and generate new code in the style of the existing project. Basically, a personalized coding copilot.

I started Friday evening with the indexing pipeline. The first challenge was getting the code into a retrievable format. Unlike prose text, code has structure — functions, classes, modules, imports — that matters for understanding. I ended up using Tree-sitter to parse the code into an AST, then extracting function and class definitions as individual chunks. Each chunk included its full source, the file path, and a brief docstring or inferred description.

Embedding code is different from embedding prose. I experimented with both general-purpose text embeddings and code-specific embedding models. The code-specific model was noticeably better at finding semantically similar code even when the variable names differed.

By Saturday morning I had a working retrieval system. I could query "how does authentication work" and get back the relevant functions from across the codebase. The accuracy was surprisingly good for a first pass.

Saturday afternoon was about the generation layer. I used a streaming API call with the retrieved code as context, asking the model to answer questions or suggest changes. I added a custom system prompt that instructed the model to follow the conventions visible in the retrieved code — things like error handling patterns, naming conventions, and docstring style.

The hardest part was handling large codebases. My personal project is only about 15,000 lines, but that's still too much to fit in context. Retrieval helps, but you sometimes need code that's not obviously related to the query — like understanding how a utility function is used across the codebase. I added a second retrieval pass that fetches callers and callees of the retrieved functions.

Sunday was polish and integration. I wrapped everything in a simple CLI and a minimal web interface. The CLI version actually ended up being my preferred way to use it — quick and keyboard-driven.

What would I do differently? I'd invest more in the chunking strategy upfront. My initial character-based chunking missed a lot of context. The Tree-sitter approach is much better but took longer to implement. I'd also add conversation memory from the start — each query being independent loses a lot of value in a coding workflow where context builds up.

The result is a tool I actually use daily now. It's not as polished as GitHub Copilot, but it knows my codebase specifically, which makes it more useful for deep questions about my own projects.""",
    },
    {
        "title": "The Future of LLM Tooling",
        "description": "An opinion piece on where the LLM developer ecosystem is heading — what will matter in two years and what's just hype.",
        "url": "https://www.youtube.com/watch?v=LLMToolng06",
        "transcript": """I want to share my perspective on where the LLM tooling ecosystem is heading, what I think will matter in two years, and what I suspect is noise.

The tooling landscape has exploded since 2023. There are frameworks for everything — agent orchestration, prompt management, evaluation, fine-tuning, deployment, monitoring. A lot of this tooling will consolidate or disappear. That's not cynicism, it's just how ecosystems mature.

What I believe will endure: evaluation infrastructure. The teams winning at AI products today are the ones running tight eval loops. They can measure whether a change actually improves model behavior, not just vibe-check it. Evals are hard to build well, which means good eval tooling has durable value. LLM-as-judge, human preference data pipelines, automated regression testing — these will be table stakes for production AI in two years.

Structured outputs are another durable trend. Getting models to reliably output valid JSON, fill in forms, or follow strict schemas is enormously valuable for integrating AI into existing systems. The model providers are improving this at the API level, but tooling for validation, retry, and schema management will remain important.

Observability and tracing are still immature but critically important. When your AI system does something wrong, how do you debug it? You need traces of every LLM call, every tool invocation, every retrieval step. This is analogous to distributed systems tracing — it's not glamorous, but it's essential for operating AI at scale.

What I'm skeptical of: most agent frameworks. The complexity of today's agent frameworks often exceeds the complexity of the problems they solve. Many teams would be better served by a simple loop and clear tool definitions than by a heavyweight framework with its own abstractions to learn and debug. As the models get better, the need for elaborate orchestration decreases.

Prompt management as a product is also in a weird place. Managing prompt versions in a database seems like a solved problem that doesn't need a dedicated SaaS product. Most teams I talk to end up just using version control for their prompts.

The platforms that enable experimentation — quickly spinning up different models, running A/B tests, switching providers — will win. Model diversity is increasing, not decreasing, and the teams that can evaluate and swap models efficiently have a real competitive advantage.

My core prediction: the AI stack will look much more like the data stack than like the ML stack. It'll be pipelines, schemas, observability, and APIs — familiar infrastructure patterns applied to a new kind of compute.""",
    },
    {
        "title": "Prompt Engineering Best Practices",
        "description": "Practical, battle-tested prompt engineering patterns and anti-patterns from real production deployments.",
        "url": "https://www.youtube.com/watch?v=PromptEng07",
        "transcript": """After writing prompts for dozens of production systems, I've developed a set of practices that reliably produce better results. Today I'm going to share the most important ones.

Start with a clear system prompt. The system prompt sets the model's persona, capabilities, and constraints. It should be specific about what the model is, what it should and shouldn't do, and what format its responses should take. Vague system prompts lead to unpredictable behavior. Spend real time on this — it's the foundation everything else builds on.

Use few-shot examples strategically. Showing the model examples of the input-output behavior you want is often more effective than describing it in words. But be careful about example selection — the model will generalize from your examples in ways you may not intend. Include examples that cover edge cases, not just the happy path. Three to five well-chosen examples typically outperforms dozens of mediocre ones.

Be explicit about format requirements. If you need JSON, say so, give a schema, and ideally show an example. If you need bullet points, specify the format. Models can follow detailed formatting instructions reliably, but they won't guess correctly if you leave it ambiguous.

Chain of thought dramatically improves reasoning quality. For tasks that require multi-step reasoning — math, logic, complex analysis — instructing the model to "think step by step" or including reasoning in your examples significantly improves accuracy. The model is more reliable when it shows its work, because errors in intermediate steps become visible and correctable.

Calibrate the level of instruction detail to the task complexity. For simple tasks, minimal prompts work fine. For complex tasks, detailed instructions help. But there's a point of diminishing returns where more instructions create confusion. If you're spending more than a few paragraphs on instructions, consider whether decomposing the task into simpler subtasks would be better.

Handle edge cases explicitly. What should the model do when it doesn't know the answer? When the input is malformed? When the request conflicts with the instructions? Specify these behaviors explicitly rather than hoping the model will handle them gracefully.

Test with adversarial inputs. Users will send things you don't expect. Prompt injection attempts, unusual languages, questions completely off topic — your prompt needs to handle these gracefully. Regular red-teaming of your prompts catches issues before they reach production.

Version control your prompts. Treat prompts like code. Use git, write commit messages that explain why you changed the prompt, and tag versions that correspond to production deployments. When something breaks, you need to be able to identify exactly what changed.

The most important practice is iteration. Good prompts are rarely written in a single pass. Write, test, observe failures, revise. A prompt that works well is the product of many cycles of this loop.""",
    },
    {
        "title": "Evaluating AI Outputs: Metrics That Matter",
        "description": "A practical guide to evaluating LLM outputs — covering automated metrics, LLM-as-judge, human evaluation, and building eval pipelines.",
        "url": "https://www.youtube.com/watch?v=AIEvalMtr08",
        "transcript": """Evaluation is the unsexy part of AI development that separates teams shipping reliable products from teams constantly surprised by their model's behavior. Today I want to give you a practical framework for evaluating LLM outputs.

Let's start with the types of evaluation and when to use each.

Exact match metrics — comparing the model's output to a ground truth answer — work well for tasks with objectively correct answers. Code generation, structured data extraction, classification. If you know the right answer, exact match is simple and reliable.

Semantic similarity metrics use embedding models to measure how similar the model's answer is to a reference answer, regardless of exact wording. This is useful for open-ended tasks where there are many valid phrasings of the correct answer. Cosine similarity between embeddings is a common choice, though it's far from perfect.

LLM-as-judge has become widely used because it scales easily and correlates reasonably well with human judgment for many tasks. You send the model's output (and optionally the input and reference answer) to a judge model — often a large, capable model like GPT-4 or Claude — and ask it to score the output on dimensions like correctness, helpfulness, and safety. The key insight is that judging is easier than generating, so even an imperfect judge provides useful signal.

Human evaluation remains the gold standard but doesn't scale well. Use it for calibrating your automated metrics, catching systematic failures that automated evals miss, and for high-stakes decisions like whether a new model version is ready to deploy.

When designing your eval suite, cover these dimensions. Correctness: does the model answer the question accurately? Relevance: does it stay on topic? Safety: does it refuse inappropriate requests and avoid harmful content? Format compliance: does it follow the output format you specified? Consistency: does it give similar answers to similar questions across runs?

The eval pipeline matters as much as the metrics. You want to be able to run evals automatically on every prompt change, every model version change, and on a regular schedule against production traffic samples. This requires investment in tooling — storing inputs and outputs, running judge models, aggregating scores, and alerting on regressions.

A common mistake is over-indexing on a single metric. Correctness alone misses safety issues. Safety filtering alone might be too aggressive and reduce helpfulness. Track a dashboard of metrics and watch for trade-offs when you make changes.

Start your eval suite small and grow it over time. Even 50 well-chosen test cases can catch the most common failure modes. Add cases whenever you find a production failure — this builds institutional knowledge of your system's failure modes.

The teams that ship reliable AI products are the ones that evaluate obsessively. Evaluation isn't optional — it's the foundation of trust.""",
    },
    {
        "title": "Local LLMs: A Practical Guide",
        "description": "Everything you need to know about running LLMs locally — covering Ollama, model quantization, hardware requirements, and practical use cases.",
        "url": "https://www.youtube.com/watch?v=LocalLLMsG9",
        "transcript": """Running large language models locally has become genuinely practical in the last year, thanks to better quantization techniques and tools like Ollama. Today I'll give you a practical guide to getting started and understanding what's actually possible.

Let's talk about hardware first. The most important factor is VRAM — the memory on your GPU. A 7 billion parameter model in 4-bit quantization needs roughly 4-5 GB of VRAM. A 13B model needs about 8 GB. A 70B model needs 40+ GB, which typically requires multiple consumer GPUs or a workstation GPU. If you don't have enough VRAM, the model will run on CPU, which is dramatically slower — often 10-50x slower.

Apple Silicon Macs are an excellent option for local LLMs. The unified memory architecture means the GPU can access all system RAM, so a Mac with 32 or 64 GB of RAM can run larger models efficiently. llama.cpp has excellent Metal support and performance on Apple Silicon is close to NVIDIA GPU performance per dollar.

Quantization is how you fit large models into limited memory. Instead of storing each model parameter as a 32-bit float, you use lower precision — 8-bit, 4-bit, or even 2-bit. GGUF format is the most widely used quantization format for local LLMs, and it's what Ollama uses under the hood. The quality-vs-size trade-off is surprisingly favorable — 4-bit quantization typically loses only a few percent on benchmarks while cutting memory requirements by 8x compared to float32.

Ollama is the easiest way to get started. Install it, run `ollama run llama3`, and you have a local LLM with a clean API. It handles model downloading, management, and serving. The API is OpenAI-compatible, so you can point any OpenAI SDK at your local Ollama instance with a one-line change.

What are local LLMs actually good for? Privacy-sensitive applications where you can't send data to an API. Offline or air-gapped environments. High-volume tasks where API costs are prohibitive. Development and experimentation where you want fast iteration without per-token costs.

Where do local models still fall short? Frontier capabilities. The best locally runnable models are roughly comparable to GPT-3.5 — good, but not at the level of the latest GPT-4 or Claude models. Complex reasoning, very long context, and instruction following are all still better in the frontier cloud models. For anything requiring cutting-edge capability, cloud APIs remain the better choice.

The practical recommendation: use local LLMs for development, experimentation, and privacy-sensitive use cases. Use cloud APIs for production applications where quality matters most. The two are complementary, not competitive.""",
    },
    {
        "title": "Building Production RAG Pipelines",
        "description": "Advanced techniques for production-grade RAG — covering chunking strategies, hybrid search, re-ranking, and monitoring in real deployments.",
        "url": "https://www.youtube.com/watch?v=ProdRagPip1",
        "transcript": """Building a RAG prototype is one thing; running it reliably in production is another. Today I want to share the advanced techniques and hard lessons from deploying RAG pipelines at scale.

Chunking strategy is where most production RAG systems fail. Naive chunking — splitting every 500 characters — produces terrible results. Semantic chunking splits at natural boundaries like paragraphs and sections. Structural chunking respects document structure like headers, lists, and code blocks. Hierarchical chunking stores both fine-grained chunks for precision and coarser chunks for context. The right strategy depends on your document types — a PDF of financial reports needs different chunking than a code repository or a customer support knowledge base.

Hybrid search combines dense vector retrieval with traditional sparse keyword search like BM25. Dense retrieval is excellent at semantic similarity but misses exact matches for specific product names, error codes, or technical terms. Sparse retrieval handles exact matches well but misses paraphrases. Combining them with a technique called Reciprocal Rank Fusion consistently outperforms either approach alone in production evaluations.

Re-ranking is a critical upgrade to basic retrieval. After getting the top 20 results from your initial retrieval, use a cross-encoder re-ranker to score each result against the query. Cross-encoders look at the query and document together, which is much more accurate than embedding similarity but too slow to apply to the entire corpus. Using it as a second-stage filter over the initial results combines speed and quality.

Query understanding is underrated. Before retrieving, analyze the query. Is it a factual question, a comparison, a procedural question? Does it reference a specific entity? This analysis should influence your retrieval strategy — factual questions benefit from different chunk types than procedural how-to questions.

Contextual compression improves the quality of the context you send to the generator. Instead of passing raw chunks, use a smaller model to extract just the sentences from each chunk that are relevant to the query. This reduces noise in the context and often improves answer quality.

Monitoring is essential in production. Track retrieval quality metrics like mean reciprocal rank. Track generation quality with automated evals. Log every query, retrieval result, and response so you can audit failures. Set up alerts for retrieval latency and error rates.

Caching is often overlooked. Many queries in production are similar or identical. Caching at the retrieval level or the full response level can dramatically reduce latency and cost. Semantic caching — finding cached responses for semantically similar queries — is especially effective for FAQ-type applications.

The most important thing I've learned from production RAG: iterate on your data and chunking strategy before you iterate on your retrieval or generation. The quality of what you put in determines the ceiling of what you can get out.""",
    },
]


async def _ingest_video(video: dict) -> int:
    """
    Full ingest pipeline for a single video:
      1. Create video record
      2. Chunk transcript
      3. Embed chunks (batched)
      4. Store chunks

    Returns the number of chunks created.
    """
    video_record = await repository.create_video(
        title=video["title"],
        description=video["description"],
        url=video["url"],
        transcript=video["transcript"],
    )
    video_id = video_record["id"]

    chunk_texts = chunk_video(video)
    if not chunk_texts:
        logger.warning("No chunks generated for '%s'", video["title"])
        return 0

    try:
        embeddings = embed_batch(chunk_texts)
    except Exception as exc:
        logger.error("Embedding failed for '%s': %s", video["title"], exc)
        return 0

    for idx, (text, embedding) in enumerate(zip(chunk_texts, embeddings)):
        await repository.create_chunk(
            video_id=video_id,
            content=text,
            embedding=embedding,
            chunk_index=idx,
        )

    return len(chunk_texts)


async def _chunk_existing_video(video_id: str, video: dict) -> int:
    """
    Run chunking + embedding for a video that already exists in the DB.
    Used when videos were seeded without chunks (e.g., from Sprint 1).
    Returns the number of chunks created.
    """
    chunk_texts = chunk_video(video)
    if not chunk_texts:
        logger.warning("No chunks generated for '%s'", video.get("title"))
        return 0

    try:
        embeddings = embed_batch(chunk_texts)
    except Exception as exc:
        logger.error("Embedding failed for '%s': %s", video.get("title"), exc)
        return 0

    for idx, (text, embedding) in enumerate(zip(chunk_texts, embeddings)):
        await repository.create_chunk(
            video_id=video_id,
            content=text,
            embedding=embedding,
            chunk_index=idx,
        )

    return len(chunk_texts)


async def run_seed() -> None:
    """Insert all 10 seed videos into the database with full chunking + embedding."""
    total = len(SEED_VIDEOS)
    total_chunks = 0
    failed_videos: list[str] = []
    for i, video in enumerate(SEED_VIDEOS, start=1):
        print(f"Seeding video {i}/{total}: {video['title']}")
        n = await _ingest_video(video)
        if n == 0:
            failed_videos.append(video["title"])
        total_chunks += n
        print(f"  -> {n} chunks created")
    if failed_videos:
        raise RuntimeError(
            f"Seed failed for {len(failed_videos)} videos: {failed_videos}. "
            "Check embedding API connectivity."
        )
    print(f"Seeding complete: {total} videos, {total_chunks} chunks inserted")


async def seed_if_empty() -> None:
    """
    Run seed only if needed:
    - If no videos: full seed (create videos + chunks)
    - If videos exist but no chunks: chunk+embed existing videos
    - If both exist: skip
    """
    video_count = await repository.count_videos()
    chunk_count = await repository.count_chunks()

    if chunk_count > 0:
        print(
            f"Seed data already present "
            f"({video_count} videos, {chunk_count} chunks), skipping seed"
        )
        return

    if video_count == 0:
        print("No videos found — running full seed pipeline...")
        await run_seed()
        return

    # Videos exist but no chunks — this happens when Sprint 1 seeded videos
    # without the embedding pipeline. Re-embed existing videos.
    print(
        f"Found {video_count} videos but no chunks — "
        "running chunking+embedding for existing videos..."
    )
    all_videos = await repository.list_videos()
    # list_videos doesn't return transcript, need full video records
    total_chunks = 0
    for i, v in enumerate(all_videos, start=1):
        full_video = await repository.get_video(v["id"])
        if not full_video:
            continue
        print(f"  Chunking video {i}/{len(all_videos)}: {full_video['title']}")
        n = await _chunk_existing_video(full_video["id"], full_video)
        total_chunks += n
        print(f"    -> {n} chunks created")
    print(f"Chunking complete: {total_chunks} chunks created for {len(all_videos)} videos")


if __name__ == "__main__":
    asyncio.run(seed_if_empty())
