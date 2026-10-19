# 24 — Runtime Compatibility Matrix

**Status:** design only — architecture ratification. **Classifies** the runtimes Nexus must
support against the taxonomy (`21`) and shows each is reachable through the **same** adapter
contract (`03`) with, at most, an optional transport (`23`). This is a **classification, not
a ranking** — no runtime is judged better or worse; each is placed. Modifies no ADR,
contract, or invariant.

Legend: **Host / Service / Gateway / Embedded** = taxonomy category (`21`); ✓ = yes,
— = no. "Needs Adapter" is ✓ for every runtime by construction (`03`: the one contract).
"Needs Transport" = whether a protocol sub-layer (`23`) is present.

---

## 1. The matrix

| Runtime | Host | Service | Gateway | Embedded | Needs Adapter | Needs Transport |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Claude Code** | ✓ | — | — | — | ✓ | — |
| **Gemini CLI** | ✓ | — | — | — | ✓ | — |
| **Shell** | ✓ | — | — | — | ✓ | — |
| **Docker** | ✓ | — | — | — | ✓ | —¹ |
| **Python** | ✓ | — | — | — | ✓ | — |
| **Browser** | ✓ | — | — | — | ✓ | —² |
| **OpenAI** | — | ✓ | — | — | ✓ | ✓ |
| **Anthropic** | — | ✓ | — | — | ✓ | ✓ |
| **OpenRouter** | — | ✓ | —³ | — | ✓ | ✓ |
| **OmniRoute** | — | —⁴ | ✓ | — | ✓ | ✓ (multiplexing) |
| **Ollama** | — | — | — | ✓ | ✓ | ✓ (loopback)⁵ |
| **LM Studio** | — | — | — | ✓ | ✓ | ✓ (loopback)⁵ |

**Every row needs an adapter; that is the invariant** (`03`: one contract, satisfied by all).
The only columns that vary are the *category* and *whether a transport is present* — exactly
the two things `21`/`23` say may vary.

## 2. Classification notes

¹ **Docker** — the Docker daemon is reached over a local socket/API, but that is
**adapter-internal host mechanics**, not a Nexus Transport (`23` §5): the execution locus is
the local machine and the artifact/isolation model is Host (`21` §2). If Docker is driven on
a *remote* host, that remote hop **is** a transport — the same runtime, reclassified by
deployment, absorbed by the adapter with no RM change (`19`).

² **Browser** — the driver protocol (CDP/WebDriver) is a local control channel, treated as
adapter-internal host mechanics, not a Nexus Transport, when the browser runs locally. A
remote browser grid adds a transport, same as Docker.

³ **OpenRouter** — it is itself a *hosted gateway/router*, but Nexus consumes it **as a
Service**: its routing is remote and opaque behind one endpoint, and Nexus holds one
credential and one URL. The gateway-ness is not Nexus's transport concern (contrast
OmniRoute, a *local* gateway Nexus operates). Placed as **Service**; the parenthetical
Gateway mark denotes its internal nature, not its Nexus classification.

⁴ **OmniRoute** — a **local, Nexus-operated multiplexing transport** fronting Service
backends. It is a **Gateway**; it executes nothing (`21` §4). Its execution locus is
whichever Service ultimately answers. "Needs Transport" is ✓ because **it *is* the
transport** (`23` §3). Full worked analysis in `docs/runtime/assessment/`.

⁵ **Ollama / LM Studio** — **Embedded** (on-device inference) reached through a **loopback**
HTTP transport (`23` §5). The transport is local and network-free-of-egress — a privacy
*positive* (`21` §5). A purely in-process embedded runtime (llama.cpp/ExecuTorch/GGUF
linked) would be **Embedded with Needs Transport = —** (Start = load model into memory).

## 3. Reading the matrix by category

- **Host (6):** Claude Code, Gemini CLI, Shell, Docker, Python, Browser — local execution,
  file artifacts, strongest isolation (`17` §2), usually no transport. Full lifecycle weight.
- **Service (3):** OpenAI, Anthropic, OpenRouter — remote execution, result+usage artifacts,
  always transport, credential-by-`.env`-reference. Lifecycle collapses toward execution
  states.
- **Gateway (1):** OmniRoute — multiplexing transport, no execution locus of its own, must
  not become a second secret store (`17` §1). Downgrades recorded as metadata.
- **Embedded (2):** Ollama, LM Studio — on-device inference, result+usage artifacts, no
  external network, usually no credential; loopback transport for the server sub-form.

## 4. What the matrix proves

1. **Uniform reachability.** Every listed runtime — and the four categories they span — is
   reachable through the *single* adapter contract (`03`). No runtime needs a bespoke RM
   path.
2. **Transport is the only structural variable.** The difference between a Shell and OpenAI,
   or between OpenAI and OmniRoute, reduces to *category + presence of transport* — both
   absorbed behind the adapter boundary (`22` §4, §5).
3. **Reclassification is a deployment detail, not a redesign.** Local Docker (Host) vs
   remote Docker (Host + transport), or in-process vs server Embedded, are handled by the
   adapter/transport without touching RM core, the lifecycle, the events, or upstream
   (`19`).
4. **Future providers slot in.** A new provider is a new row: pick a category, author an
   adapter (+ transport if Service/Gateway/server-Embedded), register a descriptor. Nothing
   above RM core changes (`19` §5). Azure OpenAI / Vertex AI → Service rows; LiteLLM → a
   Gateway row; a future WASM sandbox → a Host row; ExecuTorch → an in-process Embedded row.

## 5. Cross-references

`21` (taxonomy definitions) · `22` (layering & per-category weight) · `23` (transport,
when present/absent) · `03`/`19` (one contract, open-closed extension) · `17` (per-category
isolation & secrets) · `docs/runtime/assessment/` (OmniRoute gateway example).
