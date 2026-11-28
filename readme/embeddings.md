# Local embeddings

Back to the [main page](../README.md).

Only needed for `generate-rm --embeddings` or the **Local state embeddings** option of the web
page. FARM sends each state description to a local
[llama.cpp](https://github.com/ggml-org/llama.cpp) server that runs the `nomic-embed-text`
model. Without that server the embeddings stage fails with `Connection refused`.

## 1. Get `llama-server`

Download a ready-made binary from the
[llama.cpp releases](https://github.com/ggml-org/llama.cpp/releases), or build it. Leave out
`-DGGML_CUDA=ON` if you have no NVIDIA GPU:

```bash
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
cmake -B build -DGGML_CUDA=ON
cmake --build build --config Release -j
ls build/bin/llama-server
```

## 2. Get the model

Pull it with [Ollama](https://ollama.com/download):

```bash
ollama pull nomic-embed-text
```

Ollama keeps the model as a plain file that `llama-server` can read. The `FROM` line gives its
path:

```bash
ollama show nomic-embed-text --modelfile | grep '^FROM'
# FROM /usr/share/ollama/.ollama/models/blobs/sha256-970aa74c...
```

## 3. Fill in `.env`

```dotenv
LLAMA_SERVER_PORT=8934
LLAMA_SERVER_BIN=/path/to/llama.cpp/build/bin/llama-server
LLAMA_SERVER_MODEL=/usr/share/ollama/.ollama/models/blobs/sha256-970aa74c...
```

## 4. Start the server

`python app/app.py` prints the exact command when it starts, built from these values. Run it
in a second terminal and leave it open. To check that it answers:

```bash
curl -s localhost:8934/v1/embeddings -H 'Content-Type: application/json' \
  -d '{"model":"nomic-embed-text","input":"test"}' | head -c 100
```

Ollama only supplies the file. FARM never calls Ollama's own server.
