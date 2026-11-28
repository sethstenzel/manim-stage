# DNS spoofing (cache poisoning), animated

A graphical explainer of how DNS cache poisoning works. It's a concept diagram only, with no attack code. Boxes stand for the browser, the recursive resolver (with its cache), the authoritative name server, the real web server and an attacker. DNS messages are cards that travel between them.

| Chapter | What it shows |
|---|---|
| Normal lookup | The resolver asks, checks the reply's transaction ID and caches the answer for its TTL. The browser reaches the real server over HTTPS. |
| Cache poisoning | The record expires. An attacker triggers a new lookup and races the real reply with forged ones, each guessing the 16-bit ID. The first match is cached. |
| Victim redirected | Later users get the poisoned answer from the cache and land on a look-alike site. HTTPS certificate checks still expose it. |
| Defenses | Random IDs and source ports, DNSSEC, DNS over TLS/HTTPS, HTTPS certificates. |

Addresses come from the RFC 5737 documentation ranges, and `example.com` is reserved for examples. Colours come from `.manim-stage/project.json`.

```bash
manim-stage studio dns_spoofing.py DnsSpoofing              # preview, drag the cues
manim-stage web dns_spoofing.py DnsSpoofing -q medium_quality   # player with chapters
manim -qm dns_spoofing.py DnsSpoofing                       # plain Manim render
```

Walkthrough: [`docs/kb/tutorials/dns-spoofing.md`](../../docs/kb/tutorials/dns-spoofing.md).
