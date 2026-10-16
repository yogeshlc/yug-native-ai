# Third-party components and model licenses

The MIT license in this repository applies to Yug Native AI Framework's source
code and documentation. It does not relicense external runtimes, models,
services or their outputs. No model weights or runtimes are bundled here.

| Component | Relationship to this project | License / reference |
| --- | --- | --- |
| Python | Separately installed runtime; framework uses its standard library | Python license: https://docs.python.org/3/license.html |
| Ollama | Separately installed model server, accessed over HTTP | MIT; see upstream license: https://github.com/ollama/ollama/blob/main/LICENSE |
| Qwen3.5-35B-A3B | Optional, separately downloaded model | Apache 2.0; official model repository: https://huggingface.co/Qwen/Qwen3.5-35B-A3B |
| Other models and compatible providers | Optional integrations chosen by the user | Each model's license and each provider's terms apply separately |
| Brave Leo | Optional alternative interface described in earlier setup guidance; not a dependency of this app | Refer to Brave's own licenses and service terms: https://brave.com/ |

Check the exact artifact and version you download. Model quantizations and
fine-tuned variants may carry additional notices. If you distribute external
components, retain and satisfy their applicable notices and license terms.
