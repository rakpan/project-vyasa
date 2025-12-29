# System Architecture: The Fusion Engine

```mermaid
graph TD
    User((User))
    
    subgraph "Console (Next.js)"
        UI[Dashboard UI]
        Upload[Upload Zone]
        Viz[Graph Visualizer]
    end

    subgraph "Fusion Backend (Docker Network)"
        Cortex[<b>Cortex</b><br/>SGLang / Port 30000<br/><i>The Brain</i>]
        Drafter[<b>Drafter</b><br/>Ollama / Port 11434<br/><i>The Writer</i>]
        Embedder[<b>Embedder</b><br/>Sentence-Transformers<br/><i>The Vectorizer</i>]
        
        subgraph "Memory"
            GraphDB[(<b>Graph</b><br/>ArangoDB)]
            VectorDB[(<b>Qdrant</b><br/>Vector DB)]
        end
    end

    %% Flows
    User -->|Click| UI
    UI -->|Extract JSON| Cortex
    UI -->|Summarize| Drafter
    UI -->|Search| Embedder
    Embedder -->|Vectors| VectorDB
    Cortex -->|Triples| GraphDB
    
    %% Styling
    style Cortex fill:#f9f,stroke:#333,stroke-width:2px
    style GraphDB fill:#bbf,stroke:#333,stroke-width:2px