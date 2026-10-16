# Yug Native AI — Application Flow

This diagram describes the implemented application. GitHub renders the Mermaid code blocks directly in Markdown files.

## Complete flow

```mermaid
flowchart TD
    Start([Start]) --> Setup[Install Python and a model runtime]
    Setup --> Runtime{Choose backend}
    Runtime -->|Ollama| OpenOllama[Open Ollama]
    OpenOllama --> Pull[Download a model with ollama pull]
    Pull --> Disk[(Model files on disk)]
    Runtime -->|Compatible API| Configure[Configure API base URL and optional key]
    Configure --> External[Start compatible local server or use remote service]
    Disk --> Launch[Run python3 server.py]
    External --> Launch
    Launch --> Server[Python server listens on 127.0.0.1:8787]
    Server --> Browser[Open Yug in a browser]
    Browser --> Assets[Load HTML, CSS and JavaScript]
    Assets --> Providers[GET /api/providers]
    Providers --> SelectProvider[Choose provider]
    SelectProvider --> Discover[GET /api/models/provider]
    Discover --> Available{Provider reachable and models available?}
    Available -->|No| Error[Show connection or model error]
    Error --> Fix[Start backend, download model or fix configuration]
    Fix --> Discover
    Available -->|Yes| SelectModel[Choose AI model]
    SelectModel --> Input[Enter a question]
    Input --> Customize[Optional custom instructions and attachment]
    Customize --> Submit[Click Ask Yug]
    Submit --> Payload[Build request with text history and current attachment]
    Payload --> Chat[POST /api/chat to local Python gateway]
    Chat --> Validate[Check origin, request size, provider and message format]
    Validate --> Valid{Valid request?}
    Valid -->|No| RequestError[Display error and keep question for retry]
    RequestError --> Input
    Valid -->|Yes| Route{Selected provider}
    Route -->|Ollama| Native[POST /api/chat to configured Ollama server]
    Native --> Ollama[Ollama runs selected model with 8K context]
    Disk -.->|Model loaded into memory| Ollama
    Route -->|Compatible API| Compatible[POST /chat/completions to configured API base URL]
    Compatible --> Endpoint{Endpoint location}
    Endpoint -->|Local| Local[Local compatible inference server]
    Endpoint -->|Remote| Remote[Remote provider receives conversation and attachment]
    Ollama --> Result{Generation succeeded?}
    Local --> Result
    Remote --> Result
    Result -->|No| ProviderError[Show provider error and keep question for retry]
    ProviderError --> Input
    Result -->|Yes| Normalize[Gateway extracts answer text]
    Normalize --> Display[Display completed answer as plain text]
    Display --> History[Update in-memory conversation]
    History --> Remember{Remember conversation enabled?}
    Remember -->|Yes| Store[(Save text history in browser localStorage)]
    Remember -->|No| Session[Keep history in page memory only]
    Store --> Next{Next action}
    Session --> Next
    Next -->|Follow-up| Input
    Next -->|Copy answer| Clipboard[Copy latest answer to clipboard]
    Clipboard --> Next
    Next -->|New conversation or switch model/provider| Clear[Clear active text history]
    Clear --> Input
    Next -->|Stop server with Control+C| End([Stop])
```

## Architecture and data boundaries

```mermaid
flowchart LR
    Person[User]
    subgraph Device[User computer]
        UI[Browser UI]
        Memory[Active text conversation]
        Storage[(Optional browser localStorage)]
        Gateway[Python HTTP gateway]
        Settings[Provider URLs and API key in server environment]
        Ollama[Local Ollama server]
        Weights[(Downloaded model weights)]
        Model[Selected local model]
        Compatible[Optional local compatible server]
        UI <--> Memory
        UI <--> Storage
        UI <-->|Same-origin HTTP| Gateway
        Settings --> Gateway
        Gateway <-->|Ollama API| Ollama
        Ollama <--> Model
        Weights --> Model
        Gateway <-->|Compatible API| Compatible
    end
    Person <--> UI
    Registry[Model download service] -.->|Initial download and updates| Weights
    Gateway <-.->|Only when a remote endpoint is configured| Remote[Remote API service]
```

## Important implementation details

- **Default addresses:** Yug UI `http://127.0.0.1:8787`; Ollama `http://127.0.0.1:11434`. Both are configurable. Yug itself binds to loopback only.
- **Model discovery:** Ollama uses `GET /api/tags`; the compatible adapter uses `GET /models` relative to its configured base URL, normally ending in `/v1`.
- **Generation:** Requests use `stream: false`. The UI displays the completed answer; streaming is not implemented.
- **Conversation:** Each request includes custom instructions and prior text messages. History is capped at 18 exchanges after a successful response. Provider/model changes clear the active conversation.
- **Text attachments:** Files must be under 5 MB. Up to 24,000 characters are appended directly to the current question and become part of text history. This is not document indexing or retrieval.
- **Images:** One PNG, JPEG or WebP image is sent for the current question only. The model and provider must support vision. Images are not retained for follow-ups.
- **Persistence:** Optional saved text history lives in browser localStorage. The Python server has no chat database. Selected model and custom instructions are not restored after reload.
- **Credentials:** The optional compatible API key stays in the server environment; it is not returned to the UI.
- **Privacy:** Local inference stays on the computer when a local model and local endpoint are used. A remote endpoint receives submitted conversation data. Ollama cloud models also involve remote processing.
- **Separate lifecycle:** Stopping Yug does not stop Ollama or delete its downloaded models. Clear saved history separately from removing model files.

## Future extensions — not implemented

Web search, indexed document retrieval with citations, PDF parsing, voice, video processing, code execution, autonomous tool use, hardware-based model recommendations, and one-click packaged installation are possible extensions. They are not part of the current application flow.

See [README.md](README.md) for setup and usage.
